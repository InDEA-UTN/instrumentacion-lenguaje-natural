import pytest

from servidor.catalogo import a_json_schema
from servidor.dominio.modelos import Contexto, EstadoInteraccion, Grabacion
from servidor.ejecucion import Ejecutor, InstrumentoFake
from servidor.interpretacion.fake import InterpreteFake
from servidor.pipeline import ProcesarPedido, actualizar_contexto
from servidor.transcripcion.fake import ASRFake

AUDIO = Grabacion(contenido=b"")


@pytest.fixture
def instrumento():
    return InstrumentoFake()


def _pipeline(catalogo, instrumento, texto, interprete=None):
    return ProcesarPedido(
        asr=ASRFake(texto), interprete=interprete or InterpreteFake(),
        catalogo=catalogo, ejecutor=Ejecutor(instrumento),
    )


async def test_ejecuta_y_lee_el_instrumento(catalogo, instrumento):
    p = _pipeline(catalogo, instrumento, "poné el canal uno en quinientos milivoltios por división")
    i = await p.procesar(AUDIO, Contexto())
    assert i.estado == EstadoInteraccion.EJECUTADA
    assert instrumento.historial == [":CHANnel1:SCALe 0.5", ":CHANnel1:SCALe?"]
    assert i.resultado.lectura == "0.5"
    assert i.transcripcion.modelo.nombre == "asr-fake"
    assert i.intencion.modelo.nombre == "interprete-fake"


async def test_consulta(catalogo, instrumento):
    i = await _pipeline(catalogo, instrumento, "¿En cuánto está la escala del canal dos?").procesar(AUDIO, Contexto())
    assert i.estado == EstadoInteraccion.CONSULTADA
    assert instrumento.historial == [":CHANnel2:SCALe?"]


async def test_fuera_de_alcance_no_toca_el_instrumento(catalogo, instrumento):
    i = await _pipeline(catalogo, instrumento, "prendé la cafetera").procesar(AUDIO, Contexto())
    assert i.estado == EstadoInteraccion.RECHAZADA
    assert instrumento.historial == []


async def test_aclaracion_queda_en_el_contexto(catalogo, instrumento):
    i = await _pipeline(catalogo, instrumento, "subí la escala").procesar(AUDIO, Contexto())
    assert i.estado == EstadoInteraccion.ACLARACION
    assert i.mensaje == "¿De qué canal?"
    assert actualizar_contexto(Contexto(), i).aclaracion_pendiente == i.intencion


async def test_sensible_espera_confirmacion(catalogo, instrumento):
    p = _pipeline(catalogo, instrumento, "reiniciá el osciloscopio")
    i = await p.procesar(AUDIO, Contexto())
    assert i.estado == EstadoInteraccion.CONFIRMACION_PENDIENTE
    assert instrumento.historial == []
    hecha = await p.confirmar(i.id, aceptar=True)
    assert hecha.estado == EstadoInteraccion.EJECUTADA and hecha.id == i.id
    assert instrumento.historial == ["*RST"]


async def test_baja_confianza_espera_confirmacion(catalogo, instrumento):
    class Dudoso(InterpreteFake):
        async def interpretar(self, *args):
            return (await super().interpretar(*args)).model_copy(update={"confianza": 0.3})

    p = _pipeline(catalogo, instrumento, "canal 1 a 50 milivolt", interprete=Dudoso())
    i = await p.procesar(AUDIO, Contexto())
    assert i.estado == EstadoInteraccion.CONFIRMACION_PENDIENTE
    cancelada = await p.confirmar(i.id, aceptar=False)
    assert cancelada.estado == EstadoInteraccion.CANCELADA
    assert instrumento.historial == []


def test_esquema_derivado_del_catalogo(catalogo):
    herramientas = {h["nombre"]: h for h in a_json_schema(catalogo)}
    escala = herramientas["configurar_escala_vertical"]["parametros"]
    assert escala["required"] == ["canal", "valor"]
    assert escala["properties"]["canal"] == {"type": "integer", "minimum": 1, "maximum": 4}
