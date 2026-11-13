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
    assert instrumento.historial == ["CH1:SCAle 0.5", "CH1:SCAle?"]
    assert i.resultado.lectura == "0.5"
    assert i.transcripcion.modelo.nombre == "asr-fake"
    assert i.intencion.modelo.nombre == "interprete-fake"


async def test_consulta(catalogo, instrumento):
    i = await _pipeline(catalogo, instrumento, "¿En cuánto está la escala del canal dos?").procesar(AUDIO, Contexto())
    assert i.estado == EstadoInteraccion.CONSULTADA
    assert instrumento.historial == ["CH2:SCAle?"]


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
    p = _pipeline(catalogo, instrumento, "hacé un autoset")
    i = await p.procesar(AUDIO, Contexto())
    assert i.estado == EstadoInteraccion.CONFIRMACION_PENDIENTE
    assert instrumento.historial == []
    hecha = await p.confirmar(i.id, aceptar=True)
    assert hecha.estado == EstadoInteraccion.EJECUTADA and hecha.id == i.id
    assert instrumento.historial == ["AUTOSet EXECute"]


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


async def test_opcion_se_ejecuta_como_la_declara_el_catalogo(catalogo, instrumento):
    i = await _pipeline(catalogo, instrumento, "pasá el canal uno a acoplamiento alterna").procesar(AUDIO, Contexto())
    assert i.estado == EstadoInteraccion.EJECUTADA
    assert instrumento.historial == ["CH1:COUPling AC", "CH1:COUPling?"]
    assert str(i.comando.parametros["acoplamiento"]) == "AC"


async def test_medicion_consultada_elige_que_medir(catalogo, instrumento):
    # Una consulta solo emite la verificación: tiene que llevar la fuente y el tipo de medición.
    i = await _pipeline(catalogo, instrumento, "cuál es la frecuencia del canal uno").procesar(AUDIO, Contexto())
    assert i.estado == EstadoInteraccion.CONSULTADA
    assert instrumento.historial == ["MEASUrement:IMMed:SOUrce CH1;TYPe FREQuency;VALue?"]


def test_esquema_de_una_opcion(catalogo):
    herramientas = {h["nombre"]: h for h in a_json_schema(catalogo)}
    acoplamiento = herramientas["configurar_acoplamiento"]["parametros"]["properties"]["acoplamiento"]
    assert acoplamiento == {"type": "string", "enum": ["AC", "DC", "GND"]}


def test_esquema_derivado_del_catalogo(catalogo):
    herramientas = {h["nombre"]: h for h in a_json_schema(catalogo)}
    escala = herramientas["configurar_escala_vertical"]["parametros"]
    assert escala["required"] == ["canal", "valor"]
    assert escala["properties"]["canal"] == {"type": "integer", "minimum": 1, "maximum": 2}


async def test_rechazo_no_cambia_el_contexto(catalogo, instrumento):
    guion = {"canal siete a un volt": {
        "tipo": "accion", "accion": "configurar_escala_vertical", "parametros": {"canal": 7, "valor": 1.0},
    }}
    p = _pipeline(catalogo, instrumento, "canal siete a un volt", interprete=InterpreteFake(guion))
    previo = actualizar_contexto(Contexto(), await _pipeline(catalogo, instrumento, "subí la escala").procesar(AUDIO, Contexto()))
    i = await p.procesar(AUDIO, previo)
    assert i.estado == EstadoInteraccion.RECHAZADA
    # Ni el canal 7 pasa a ser el activo, ni se pierde la aclaración que seguía pendiente.
    assert actualizar_contexto(previo, i) == previo


async def test_pendiente_no_cambia_el_contexto_y_cancelar_cierra_la_aclaracion(catalogo, instrumento):
    previo = Contexto(canal_activo=2, aclaracion_pendiente=None)
    p = _pipeline(catalogo, instrumento, "hacé un autoset")
    pendiente = await p.procesar(AUDIO, previo)
    assert actualizar_contexto(previo, pendiente) == previo

    con_aclaracion = previo.model_copy(update={"aclaracion_pendiente": pendiente.intencion})
    cancelada = await p.confirmar(pendiente.id, aceptar=False)
    despues = actualizar_contexto(con_aclaracion, cancelada)
    assert despues.aclaracion_pendiente is None
    assert despues.ultima_intencion == previo.ultima_intencion
