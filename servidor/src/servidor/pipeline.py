"""Orquestador de la cascada: grabación → transcripción → intención → validación → ejecución.

Recibe los modelos por sus puertos: no sabe cuál está detrás de cada uno. Cada pedido puede elegir
otros (el selector del front); si no, se usan los predeterminados.
"""

import asyncio

from .dominio.errores import InteraccionInexistente, ModeloNoDisponible, RechazoDelInstrumento
from .dominio.modelos import (
    CatalogoInstrumento,
    ComandoSCPI,
    Contexto,
    EstadoInteraccion,
    Grabacion,
    Interaccion,
    Rechazo,
    TipoIntencion,
    Transcripcion,
)
from .dominio.puertos import Interprete, MotorASR
from .ejecucion import Ejecutor
from .validacion import validar


class ProcesarPedido:
    def __init__(
        self,
        asr: MotorASR,
        interprete: Interprete,
        catalogo: CatalogoInstrumento,
        ejecutor: Ejecutor,
        umbral_confianza: float = 0.7,
    ):
        self.asr = asr
        self.interprete = interprete
        self.catalogo = catalogo
        self.ejecutor = ejecutor
        self._umbral = umbral_confianza
        self._pendientes: dict[str, Interaccion] = {}

    async def procesar(
        self, grabacion: Grabacion, contexto: Contexto,
        asr: MotorASR | None = None, interprete: Interprete | None = None,
    ) -> Interaccion:
        asr = asr or self.asr
        try:
            transcripcion = await asr.transcribir(grabacion)
        except ModeloNoDisponible as e:
            # El respaldo es manual: el mensaje dice qué etapa cambiar.
            raise ModeloNoDisponible(f"Transcripción ({asr.info().proveedor}): {e}") from e
        return await self.procesar_transcripcion(transcripcion, contexto, interprete)

    async def procesar_transcripcion(
        self, transcripcion: Transcripcion, contexto: Contexto, interprete: Interprete | None = None,
    ) -> Interaccion:
        if not transcripcion.texto.strip():
            # Sin texto no hay nada que interpretar: un modelo de lenguaje podría inventar un pedido.
            return Interaccion(
                transcripcion=transcripcion, estado=EstadoInteraccion.RECHAZADA,
                mensaje="No se entendió el audio. Repetí el pedido.",
            )
        interprete = interprete or self.interprete
        try:
            intencion = await interprete.interpretar(transcripcion, self.catalogo, contexto)
        except ModeloNoDisponible as e:
            raise ModeloNoDisponible(f"Intérprete ({interprete.info().proveedor}): {e}") from e
        base = {"transcripcion": transcripcion, "intencion": intencion}

        if intencion.tipo == TipoIntencion.FUERA_DE_ALCANCE:
            return Interaccion(
                **base, estado=EstadoInteraccion.RECHAZADA,
                mensaje="No puedo hacer eso: no está en el catálogo de este instrumento.",
            )
        if intencion.tipo == TipoIntencion.ACLARACION:
            return Interaccion(
                **base, estado=EstadoInteraccion.ACLARACION,
                mensaje=intencion.pregunta or "Me falta un dato para hacer eso.",
            )

        validado = validar(intencion, self.catalogo)
        if isinstance(validado, Rechazo):
            return Interaccion(**base, estado=EstadoInteraccion.RECHAZADA, mensaje=validado.motivo, rechazo=validado)

        if validado.sensible or intencion.confianza < self._umbral:
            pendiente = Interaccion(
                **base, comando=validado, estado=EstadoInteraccion.CONFIRMACION_PENDIENTE,
                mensaje=f"¿Confirmás? {_describir(validado)}",
            )
            self._pendientes[pendiente.id] = pendiente
            return pendiente

        return await self._ejecutar(Interaccion(**base, comando=validado, estado=EstadoInteraccion.EJECUTADA, mensaje=""))

    async def confirmar(self, interaccion_id: str, aceptar: bool) -> Interaccion:
        pendiente = self._pendientes.pop(interaccion_id, None)
        if pendiente is None:
            raise InteraccionInexistente(interaccion_id)
        if not aceptar:
            return pendiente.model_copy(update={"estado": EstadoInteraccion.CANCELADA, "mensaje": "Cancelado."})
        return await self._ejecutar(pendiente)

    async def _ejecutar(self, interaccion: Interaccion) -> Interaccion:
        comando = interaccion.comando
        try:
            resultado = await asyncio.to_thread(self.ejecutor.ejecutar, comando)
        except RechazoDelInstrumento as e:
            # El validador lo dejó pasar pero el equipo no: se informa como rechazo, con su motivo.
            # InstrumentoNoDisponible no se atrapa acá: no es una respuesta del equipo (API: 503).
            rechazo = Rechazo(motivo=str(e))
            return interaccion.model_copy(update={
                "estado": EstadoInteraccion.RECHAZADA, "mensaje": rechazo.motivo, "rechazo": rechazo,
            })
        consulta = comando.escritura is None
        lectura = f" El instrumento responde: {resultado.lectura}." if resultado.lectura is not None else ""
        return interaccion.model_copy(update={
            "estado": EstadoInteraccion.CONSULTADA if consulta else EstadoInteraccion.EJECUTADA,
            "mensaje": f"{'Consultado' if consulta else 'Hecho'}: {_describir(comando)}.{lectura}",
            "resultado": resultado,
        })


def actualizar_contexto(contexto: Contexto, interaccion: Interaccion) -> Contexto:
    """El contexto guarda lo que se entendió y se hizo, no lo que se descartó.

    - Rechazada: no cambia nada. Un canal fuera de rango no pasa a ser el canal activo, y una
      aclaración pendiente sigue pendiente para que el usuario pueda volver a responderla.
    - Pendiente de confirmación: todavía no pasó nada; el contexto se actualiza al confirmar.
    - Cancelada: el pedido se cerró sin efecto; solo se descarta la aclaración que lo originó.
    """
    intencion = interaccion.intencion
    if intencion is None or interaccion.estado in (
        EstadoInteraccion.RECHAZADA, EstadoInteraccion.CONFIRMACION_PENDIENTE
    ):
        return contexto
    if interaccion.estado == EstadoInteraccion.CANCELADA:
        return contexto.model_copy(update={"aclaracion_pendiente": None})
    canal = intencion.parametros.get("canal", contexto.canal_activo)
    return contexto.model_copy(update={
        "ultima_intencion": intencion,
        "canal_activo": canal if isinstance(canal, int) else contexto.canal_activo,
        "aclaracion_pendiente": intencion if interaccion.estado == EstadoInteraccion.ACLARACION else None,
    })


def _describir(comando: ComandoSCPI) -> str:
    parametros = ", ".join(f"{k} = {v}" for k, v in comando.parametros.items())
    return f"{comando.accion}({parametros})"
