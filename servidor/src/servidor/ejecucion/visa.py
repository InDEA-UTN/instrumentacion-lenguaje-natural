"""Conexión con un instrumento real por PyVISA (docs/scpi.md, sección 2).

Tres reglas:

- **Nunca hablar con el equipo equivocado.** Al conectar se pide `*IDN?` y se exige que la respuesta
  nombre el modelo del catálogo. Un catálogo del TBS1072B no le manda comandos a otro instrumento.
- **Lo que el equipo rechaza no pasa como hecho.** Después de cada mensaje se lee `*ESR?` (IEEE
  488.2). Si el equipo marcó un error de comando, de ejecución, del dispositivo o de consulta, se
  lanza RechazoDelInstrumento con el detalle que el equipo informa.
- **Un pedido a la vez.** PyVISA no es seguro entre hilos y la API atiende pedidos en paralelo:
  todo acceso al equipo pasa por un candado.

La conexión se abre recién con el primer uso y se reabre sola después de un error de E/S. Así el
servidor arranca aunque el osciloscopio esté desenchufado, y sobrevive a que lo desenchufen.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence

from ..dominio.errores import InstrumentoNoDisponible, RechazoDelInstrumento

log = logging.getLogger(__name__)

# Bits de error del Standard Event Status Register (IEEE 488.2, *ESR?).
_BITS_DE_ERROR = {
    0x20: "error de comando (sintaxis o comando desconocido)",
    0x10: "error de ejecución (valor no admitido en el estado actual)",
    0x08: "error del dispositivo",
    0x04: "error de consulta",
}
# SCPI devuelve 9.9E37 (9.91E37 es NaN) cuando no hay dato: por ejemplo, medir un canal apagado.
_SIN_DATO = 9.9e37


class ConexionVisa:
    def __init__(
        self,
        modelo: str,
        recurso: str | None = None,
        backend: str = "@py",
        timeout_ms: int = 10_000,
        al_conectar: Sequence[str] = ("HEADer OFF",),
        consulta_eventos: str | None = "ALLEv?",
    ):
        """
        modelo: lo que tiene que aparecer en la respuesta a `*IDN?` (el `modelo` del catálogo).
        recurso: cadena VISA. Si es None, se busca entre los instrumentos USB el que sea `modelo`.
        backend: "@py" (pyvisa-py, sin drivers del fabricante), "" (NI-VISA) o "archivo.yaml@sim".
        al_conectar: comandos que se envían al abrir. En los Tektronix, HEADer OFF hace que una
            consulta devuelva solo el valor ("1.0E0") y no el comando entero ("CH1:SCALE 1.0E0").
        consulta_eventos: consulta que describe el último error. Es propia de cada fabricante.
        """
        self._modelo = modelo
        self._recurso = recurso
        self._backend = backend
        self._timeout_ms = timeout_ms
        self._al_conectar = tuple(al_conectar)
        self._consulta_eventos = consulta_eventos
        self._candado = threading.Lock()
        self._rm = None
        self._inst = None
        self.idn: str | None = None
        self.recurso: str | None = recurso

    # -- Puerto ConexionInstrumento -------------------------------------------------------------

    def escribir(self, comando: str) -> None:
        with self._candado:
            inst = self._conectado()
            self._es(lambda: inst.write(comando))
            self._verificar_errores(inst, comando)

    def consultar(self, comando: str) -> str:
        with self._candado:
            inst = self._conectado()
            try:
                respuesta = inst.query(comando).strip()
            except Exception as e:
                # Una consulta mal formada no tiene respuesta y termina en timeout: si el equipo la
                # registró como error, es un rechazo y no una desconexión.
                self._verificar_errores(inst, comando)
                self._desconectar()
                raise InstrumentoNoDisponible(f"El instrumento no respondió a '{comando}': {e}") from e
            self._verificar_errores(inst, comando)
        if _sin_dato(respuesta):
            raise RechazoDelInstrumento(
                f"El instrumento no pudo medir ('{comando}' devolvió {respuesta}). "
                "Revisá que el canal esté visible y tenga señal."
            )
        return respuesta

    def salud(self) -> bool:
        """True si el equipo responde a `*IDN?`. No lanza excepciones."""
        with self._candado:
            try:
                inst = self._conectado()
                self._es(lambda: inst.query("*IDN?"))
                return True
            except InstrumentoNoDisponible as e:
                log.info("Instrumento no disponible: %s", e)
                return False

    def cerrar(self) -> None:
        with self._candado:
            self._desconectar()
            if self._rm is not None:
                self._rm.close()
                self._rm = None

    # -- Conexión -------------------------------------------------------------------------------

    def _conectado(self):
        if self._inst is None:
            self._abrir()
        return self._inst

    def _abrir(self) -> None:
        pyvisa = _importar_pyvisa()
        try:
            if self._rm is None:
                self._rm = pyvisa.ResourceManager(self._backend)
            recurso = self._recurso or self._buscar()
            inst = self._configurar(self._rm.open_resource(recurso))
            idn = inst.query("*IDN?").strip()
        except InstrumentoNoDisponible:
            raise
        except Exception as e:  # pyvisa.Error, usb.core.USBError, OSError, ValueError...
            raise InstrumentoNoDisponible(f"No se pudo abrir el instrumento: {e}") from e

        if self._modelo.upper() not in idn.upper():
            inst.close()
            raise InstrumentoNoDisponible(
                f"En {recurso} responde '{idn}', pero el catálogo es del {self._modelo}."
            )
        try:
            inst.write("*CLS")  # que un error viejo no se atribuya al primer comando
            for comando in self._al_conectar:
                inst.write(comando)
            inst.query("*ESR?")  # limpia también el registro de eventos
        except Exception as e:
            inst.close()
            raise InstrumentoNoDisponible(f"No se pudo preparar el instrumento: {e}") from e
        self._inst, self.idn, self.recurso = inst, idn, recurso
        log.info("Conectado a %s en %s", idn, recurso)

    def _buscar(self) -> str:
        """El primer instrumento USB cuya respuesta a `*IDN?` nombre el modelo del catálogo."""
        candidatos = self._rm.list_resources("USB?*::INSTR")
        vistos = []
        for recurso in candidatos:
            try:
                inst = self._configurar(self._rm.open_resource(recurso))
                idn = inst.query("*IDN?").strip()
                inst.close()
            except Exception as e:
                vistos.append(f"{recurso} (no responde: {e})")
                continue
            if self._modelo.upper() in idn.upper():
                return recurso
            vistos.append(f"{recurso} ({idn})")
        detalle = "; ".join(vistos) if vistos else "no hay ningún instrumento USB conectado"
        raise InstrumentoNoDisponible(f"No se encontró un {self._modelo}: {detalle}.")

    def _configurar(self, inst):
        inst.timeout = self._timeout_ms
        inst.read_termination = "\n"
        inst.write_termination = "\n"
        return inst

    def _desconectar(self) -> None:
        if self._inst is not None:
            try:
                self._inst.close()
            except Exception:
                pass
            self._inst = None

    def _es(self, operacion):
        """Ejecuta una operación de E/S; si falla, cierra para reconectar en el próximo uso."""
        try:
            return operacion()
        except Exception as e:
            self._desconectar()
            raise InstrumentoNoDisponible(f"Se perdió la comunicación con el instrumento: {e}") from e

    def _verificar_errores(self, inst, comando: str) -> None:
        crudo = self._es(lambda: inst.query("*ESR?")).strip()
        try:
            esr = int(float(crudo))
        except ValueError:
            # Un equipo que no reconoce el comando puede responder un texto de error en lugar del
            # registro (lo hace pyvisa-sim). Ya se leyó, así que el canal queda limpio.
            raise RechazoDelInstrumento(
                f"El instrumento no reconoció '{comando}' (a *ESR? respondió {crudo!r})."
            ) from None
        motivos = [texto for bit, texto in _BITS_DE_ERROR.items() if esr & bit]
        if not motivos:
            return
        detalle = ""
        if self._consulta_eventos:
            try:
                detalle = f" El equipo informa: {inst.query(self._consulta_eventos).strip()}."
            except Exception:
                pass
        raise RechazoDelInstrumento(f"El instrumento rechazó '{comando}': {', '.join(motivos)}.{detalle}")


def _sin_dato(respuesta: str) -> bool:
    try:
        return abs(float(respuesta)) >= _SIN_DATO
    except ValueError:
        return False


def _importar_pyvisa():
    try:
        import pyvisa
    except ImportError as e:
        raise InstrumentoNoDisponible(
            "PyVISA no está instalado: pip install -e '.[visa]' (o INSTRUMENTO=fake)."
        ) from e
    return pyvisa
