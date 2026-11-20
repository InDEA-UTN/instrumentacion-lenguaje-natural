"""La conexión PyVISA, sin el equipo: contra pyvisa-sim y contra un recurso de prueba."""

import pytest

from servidor.config import Configuracion
from servidor.dominio.errores import InstrumentoNoDisponible, RechazoDelInstrumento
from servidor.dominio.modelos import ComandoSCPI, Contexto, EstadoInteraccion, Grabacion, Intencion, TipoIntencion
from servidor.ejecucion import ConexionVisa, Ejecutor
from servidor.interpretacion.fake import InterpreteFake
from servidor.pipeline import ProcesarPedido
from servidor.registro import construir_pipeline
from servidor.transcripcion.fake import ASRFake
from servidor.validacion import validar

pytest.importorskip("pyvisa_sim")

import servidor  # noqa: E402

SIMULADOR = f"{servidor.__path__[0]}/simuladores/tektronix_tbs1072b.yaml@sim"
OTRO = "USB0::0x0699::0x0363::C020002::INSTR"


@pytest.fixture
def conexion():
    c = ConexionVisa(modelo="TBS1072B", backend=SIMULADOR)
    yield c
    c.cerrar()


# -- Contra el simulador ---------------------------------------------------------------------


def test_busca_el_modelo_del_catalogo_entre_los_usb(conexion):
    # En el bus simulado hay un TDS2012C antes que el TBS1072B: no tiene que elegirlo.
    assert conexion.salud()
    assert "TBS1072B" in conexion.idn
    assert "C010001" in conexion.recurso


def test_no_habla_con_otro_modelo():
    c = ConexionVisa(modelo="TBS1072B", recurso=OTRO, backend=SIMULADOR)
    assert not c.salud()
    with pytest.raises(InstrumentoNoDisponible, match="TDS2012C.*catálogo es del TBS1072B"):
        c.escribir("CH1:SCAle 0.5")


def test_sin_instrumento_no_esta_listo():
    c = ConexionVisa(modelo="TBS2000", backend=SIMULADOR)
    assert not c.salud()
    with pytest.raises(InstrumentoNoDisponible, match="No se encontró un TBS2000"):
        c.consultar("*IDN?")


def test_al_conectar_apaga_los_encabezados(conexion):
    assert conexion.consultar("HEADer?") == "OFF"


@pytest.mark.parametrize("accion, parametros, lectura", [
    ("configurar_escala_vertical", {"canal": 1, "valor": 0.5}, "5.0E-01"),
    ("configurar_acoplamiento", {"canal": 2, "acoplamiento": "AC"}, "AC"),
    ("configurar_atenuacion_sonda", {"canal": 1, "atenuacion": "1"}, "1"),
    ("mostrar_canal", {"canal": 2, "visible": "ON"}, "ON"),
    ("configurar_base_tiempo", {"valor": 0.001}, "1.0E-03"),
    ("configurar_nivel_disparo", {"valor": -0.2}, "-2.00E-01"),
    ("configurar_fuente_disparo", {"fuente": "CH2"}, "CH2"),
    ("controlar_adquisicion", {"adquisicion": "STOP"}, "STOP"),
    ("medir", {"canal": 1, "magnitud": "FREQuency"}, "1.0E3"),
    ("autoescala", {}, None),
])
def test_las_diez_acciones_del_catalogo(catalogo, conexion, accion, parametros, lectura):
    comando = validar(Intencion(tipo=TipoIntencion.ACCION, accion=accion, parametros=parametros, enunciado=""), catalogo)
    assert isinstance(comando, ComandoSCPI), comando
    assert Ejecutor(conexion).ejecutar(comando).lectura == lectura


async def test_medicion_sin_dato_se_informa_como_rechazo(catalogo, conexion):
    # De fábrica el canal 2 está apagado: el equipo responde 9.9E37 y eso no es una lectura.
    guion = {"frecuencia del canal dos": {
        "tipo": "consulta", "accion": "medir", "parametros": {"canal": 2, "magnitud": "FREQuency"},
    }}
    p = ProcesarPedido(asr=ASRFake("frecuencia del canal dos"), interprete=InterpreteFake(guion),
                       catalogo=catalogo, ejecutor=Ejecutor(conexion))
    i = await p.procesar(Grabacion(contenido=b""), Contexto())
    assert i.estado == EstadoInteraccion.RECHAZADA
    assert "no pudo medir" in i.mensaje and "9.9E37" in i.mensaje


def test_el_registro_arma_la_conexion_visa(monkeypatch):
    monkeypatch.setenv("INSTRUMENTO", "visa")
    monkeypatch.setenv("VISA_BACKEND", SIMULADOR)
    conexion = construir_pipeline(Configuracion(interprete="fake")).ejecutor.conexion
    assert isinstance(conexion, ConexionVisa) and conexion.salud()
    conexion.cerrar()


# -- Contra un recurso de prueba: lo que el simulador no imita --------------------------------


class Recurso:
    """Imita un recurso de PyVISA con un *ESR? programable y fallas de E/S a pedido."""

    def __init__(self, esr="0", eventos='113,"Undefined header"', falla_en=None):
        self.esr, self.eventos, self.falla_en = esr, eventos, falla_en
        self.escrito: list[str] = []
        self.cerrado = False

    def write(self, comando):
        if comando == self.falla_en:
            raise OSError("USB desconectado")
        self.escrito.append(comando)

    def query(self, comando):
        if comando == self.falla_en:
            raise OSError("timeout")
        return {"*IDN?": "TEKTRONIX,TBS1072B,C010001,CF:91.1CT FV:v4.03", "*ESR?": self.esr,
                "ALLEv?": self.eventos}.get(comando, "1.0E0")

    def close(self):
        self.cerrado = True


class Administrador:
    def __init__(self, *recursos):
        self.recursos, self.abiertos = list(recursos), 0

    def list_resources(self, consulta):
        return ("USB0::0x0699::0x0368::C010001::INSTR",)

    def open_resource(self, recurso):
        self.abiertos += 1
        return self.recursos.pop(0)

    def close(self):
        pass


def _con(*recursos):
    c = ConexionVisa(modelo="TBS1072B")
    c._rm = Administrador(*recursos)
    return c


def test_al_conectar_limpia_errores_viejos_y_apaga_encabezados():
    recurso = Recurso()
    c = _con(Recurso(), recurso)  # el primero lo usa la búsqueda y se cierra
    c.escribir("CH1:SCAle 0.5")
    assert recurso.escrito == ["*CLS", "HEADer OFF", "CH1:SCAle 0.5"]


def test_un_comando_rechazado_por_el_equipo_no_pasa_como_hecho():
    c = _con(Recurso(), Recurso(esr="32"))
    with pytest.raises(RechazoDelInstrumento, match="error de comando.*Undefined header"):
        c.escribir("CH1:SCAle 0.5")


def test_se_reconecta_despues_de_perder_la_comunicacion():
    c = ConexionVisa(modelo="TBS1072B", recurso="USB0::0x0699::0x0368::C010001::INSTR")
    c._rm = Administrador(Recurso(falla_en="CH1:SCAle 0.5"), Recurso())
    with pytest.raises(InstrumentoNoDisponible, match="USB desconectado"):
        c.escribir("CH1:SCAle 0.5")
    c.escribir("CH1:SCAle 0.5")  # abre de nuevo, sin reiniciar el servidor
    assert c._rm.abiertos == 2
