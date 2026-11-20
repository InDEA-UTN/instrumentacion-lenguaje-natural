"""Adaptadores de protocolo (chat, chat_audio, transcripciones) contra un servidor HTTP simulado.

Sin red y sin claves: verifican lo que el adaptador arma y cómo reacciona a cada respuesta. Si un
modelo real interpreta bien lo prueba el contrato (tests/contrato/, con -m integracion).
"""

import base64
import json

import httpx
import pytest

from servidor.clientes import ClienteHTTP
from servidor.dominio.errores import ModeloNoDisponible, RespuestaInvalida
from servidor.dominio.modelos import Contexto, Grabacion, ModeloInfo, TipoIntencion, Transcripcion
from servidor.interpretacion.chat import Chat, extraer_json
from servidor.transcripcion.chat_audio import ChatAudio
from servidor.transcripcion.transcripciones import Transcripciones

URL = "https://api.ejemplo/v1"
INFO = ModeloInfo(nombre="m", proveedor="ejemplo", version="m", ubicacion="nube")
ASR = ModeloInfo(nombre="test", proveedor="test", version="0", ubicacion="local")
TEXTO = "poné el canal uno en quinientos milivoltios por división"
INTENCION = {"tipo": "accion", "accion": "configurar_escala_vertical",
             "parametros": {"canal": 1, "valor": 0.5}, "confianza": 0.95}


class Simulador:
    """Responde con las funciones de `respuestas`, en orden, y guarda los pedidos."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.pedidos: list[httpx.Request] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        return self.respuestas.pop(0)(pedido)

    def cuerpo(self, i: int) -> dict:
        return json.loads(self.pedidos[i].content)

    def cliente(self, **kw) -> ClienteHTTP:
        return ClienteHTTP(**{"url": URL, "etiqueta": "Ejemplo", "api_key": "clave", "nombre_clave": "CLAVE",
                              "transporte": httpx.MockTransport(self), **kw})


def chat(contenido) -> callable:
    return lambda _: httpx.Response(200, json={"choices": [{"message": {"content": contenido}}]})


def error(estado: int, mensaje: str = "no") -> callable:
    return lambda _: httpx.Response(estado, json={"error": {"code": estado, "message": mensaje}})


def _t(texto=TEXTO) -> Transcripcion:
    return Transcripcion(texto=texto, modelo=ASR)


def _chat(sim: Simulador, **kw) -> Chat:
    cliente_kw = {k: kw.pop(k) for k in list(kw) if k in ("cabeceras", "cabecera_sesion", "api_key", "nombre_clave")}
    return Chat(sim.cliente(**cliente_kw), "m", INFO, **kw)


# -- chat ---------------------------------------------------------------------------------------


async def test_interpreta_con_salida_estructurada(catalogo):
    sim = Simulador(chat(json.dumps(INTENCION)))
    i = await _chat(sim).interpretar(_t(), catalogo, Contexto())

    assert i.tipo == TipoIntencion.ACCION and i.accion == "configurar_escala_vertical"
    assert i.parametros == {"canal": 1, "valor": 0.5}
    assert i.modelo == INFO
    pedido = sim.pedidos[0]
    assert str(pedido.url) == f"{URL}/chat/completions"
    assert pedido.headers["authorization"] == "Bearer clave"
    assert pedido.headers["user-agent"].startswith("instrumentacion-lenguaje-natural")
    cuerpo = sim.cuerpo(0)
    assert cuerpo["model"] == "m" and cuerpo["temperature"] == 0
    assert cuerpo["response_format"]["type"] == "json_schema"
    assert "strict" not in cuerpo["response_format"]["json_schema"]
    assert TEXTO in cuerpo["messages"][1]["content"]


async def test_esquema_estricto_y_parametros_del_proveedor(catalogo):
    # Lo que proveedores.yaml declara para OpenRouter.
    sim = Simulador(chat(json.dumps(INTENCION)))
    await _chat(sim, esquema_estricto=True, parametros={"provider": {"require_parameters": True}}).interpretar(
        _t(), catalogo, Contexto())
    cuerpo = sim.cuerpo(0)
    assert cuerpo["response_format"]["json_schema"]["strict"] is True
    assert cuerpo["provider"] == {"require_parameters": True}


async def test_cabeceras_del_proveedor(catalogo):
    sim = Simulador(chat(json.dumps(INTENCION)))
    await _chat(sim, cabeceras={"X-OpenRouter-Title": "lab"}, cabecera_sesion="x-opencode-session").interpretar(
        _t(), catalogo, Contexto())
    assert sim.pedidos[0].headers["x-openrouter-title"] == "lab"
    assert sim.pedidos[0].headers["x-opencode-session"]


async def test_sin_clave_declarada_no_manda_autorizacion(catalogo):
    # llama.cpp local: el proveedor no declara clave.
    sim = Simulador(chat(json.dumps(INTENCION)))
    await _chat(sim, api_key=None, nombre_clave=None).interpretar(_t(), catalogo, Contexto())
    assert "authorization" not in sim.pedidos[0].headers


async def test_sin_salida_estructurada_reintenta_sin_esquema_y_lo_recuerda(catalogo):
    sim = Simulador(error(400), chat("```json\n" + json.dumps(INTENCION) + "\n```"), chat(json.dumps(INTENCION)))
    interprete = _chat(sim)
    i = await interprete.interpretar(_t(), catalogo, Contexto())
    assert i.accion == "configurar_escala_vertical"
    assert "response_format" in sim.cuerpo(0) and "response_format" not in sim.cuerpo(1)
    await interprete.interpretar(_t(), catalogo, Contexto())
    assert len(sim.pedidos) == 3 and "response_format" not in sim.cuerpo(2)


async def test_un_400_que_no_es_por_el_esquema_no_apaga_el_esquema(catalogo):
    # Bitácora 2026-11-20: DeepSeek en OpenCode, sin la región Global habilitada, responde 400 a todo.
    sim = Simulador(error(400), error(400), chat(json.dumps(INTENCION)))
    interprete = _chat(sim)
    with pytest.raises(ModeloNoDisponible, match="400"):
        await interprete.interpretar(_t(), catalogo, Contexto())
    await interprete.interpretar(_t(), catalogo, Contexto())
    assert "response_format" in sim.cuerpo(2)


@pytest.mark.parametrize("estado", [401, 402, 429, 500])
async def test_otros_errores_no_se_reintentan_y_muestran_el_mensaje(catalogo, estado):
    sim = Simulador(error(estado, "Insufficient credits"))
    with pytest.raises(ModeloNoDisponible, match=f"{estado}: Insufficient credits"):
        await _chat(sim).interpretar(_t(), catalogo, Contexto())
    assert len(sim.pedidos) == 1


@pytest.mark.parametrize("cuerpo", [
    {"error": {"code": 502, "message": "Provider returned error"}},
    {"choices": [{"error": {"code": 503, "message": "overloaded"}, "message": {"content": None}}]},
])
async def test_error_con_estado_200(catalogo, cuerpo):
    # OpenRouter puede responder 200 con el error en el cuerpo.
    sim = Simulador(lambda _: httpx.Response(200, json=cuerpo))
    with pytest.raises(ModeloNoDisponible, match="50[23]"):
        await _chat(sim).interpretar(_t(), catalogo, Contexto())


async def test_respuesta_que_no_es_json_es_invalida(catalogo):
    sim = Simulador(chat("Claro, pongo el canal uno en 0,5 V."))
    with pytest.raises(RespuestaInvalida):
        await _chat(sim).interpretar(_t(), catalogo, Contexto())


async def test_respuesta_sin_contenido_es_invalida(catalogo):
    sim = Simulador(chat(None))
    with pytest.raises(RespuestaInvalida):
        await _chat(sim).interpretar(_t(), catalogo, Contexto())


async def test_falta_la_clave_y_no_sale_ningun_pedido(catalogo):
    sim = Simulador()
    interprete = _chat(sim, api_key=None, nombre_clave="OPENROUTER_API_KEY")
    assert not await interprete.salud()
    with pytest.raises(ModeloNoDisponible, match="OPENROUTER_API_KEY"):
        await interprete.interpretar(_t(), catalogo, Contexto())
    assert sim.pedidos == []


@pytest.mark.parametrize("listado, listo", [
    ({"data": [{"id": "otro"}, {"id": "m"}]}, True),
    ([{"id": "m"}], True),
    ({"data": [{"id": "otro"}]}, False),
])
async def test_salud_por_listado(listado, listo):
    sim = Simulador(lambda _: httpx.Response(200, json=listado))
    cliente = sim.cliente(modelos_url=f"{URL}/models")
    assert await Chat(cliente, "m", INFO).salud() is listo
    assert str(sim.pedidos[0].url) == f"{URL}/models"


@pytest.mark.parametrize("estado, listo", [(200, True), (503, False)])
async def test_salud_por_url(estado, listo):
    # llama.cpp: /health responde 503 mientras carga el modelo.
    sim = Simulador(lambda _: httpx.Response(estado, json={}))
    assert await Chat(sim.cliente(salud_url="http://llm/health"), "m", INFO).salud() is listo


@pytest.mark.parametrize("texto, esperado", [
    ('{"tipo": "accion"}', '{"tipo": "accion"}'),
    ('```json\n{"tipo": "accion"}\n```', '{"tipo": "accion"}'),
    ('Acá va: {"tipo": "accion"} listo.', '{"tipo": "accion"}'),
    ("sin llaves", "sin llaves"),
])
def test_extraer_json(texto, esperado):
    assert extraer_json(texto) == esperado


# -- chat_audio ---------------------------------------------------------------------------------


async def test_chat_audio_manda_el_audio_y_devuelve_el_texto():
    sim = Simulador(chat(f'"{TEXTO}"\n'))
    asr = ChatAudio(sim.cliente(), "mimo", INFO, parametros={"reasoning_effort": "none"})
    t = await asr.transcribir(Grabacion(contenido=b"RIFF-datos", formato="wav"))
    assert t.texto == TEXTO and t.modelo == INFO
    cuerpo = sim.cuerpo(0)
    assert cuerpo["reasoning_effort"] == "none"
    audio = next(p for p in cuerpo["messages"][1]["content"] if p["type"] == "input_audio")["input_audio"]
    assert audio["format"] == "wav" and base64.b64decode(audio["data"]) == b"RIFF-datos"


@pytest.mark.parametrize("respuesta", ["[inaudible]", " [Inaudible] ", ""])
async def test_chat_audio_inaudible_es_texto_vacio(respuesta):
    sim = Simulador(chat(respuesta))
    t = await ChatAudio(sim.cliente(), "mimo", INFO).transcribir(Grabacion(contenido=b"x"))
    assert t.texto == ""


async def test_chat_audio_caido_es_modelo_no_disponible():
    def caido(_):
        raise httpx.ConnectError("sin red")

    with pytest.raises(ModeloNoDisponible):
        await ChatAudio(Simulador(caido).cliente(), "mimo", INFO).transcribir(Grabacion(contenido=b"x"))


# -- transcripciones ----------------------------------------------------------------------------


async def test_transcripciones_manda_el_archivo_por_multipart():
    sim = Simulador(lambda _: httpx.Response(200, json={"text": f" {TEXTO}\n", "usage": {"seconds": 5}}))
    asr = Transcripciones(sim.cliente(), "openai/whisper-large-v3-turbo", INFO, parametros={"prompt": "osciloscopio"})
    t = await asr.transcribir(Grabacion(contenido=b"RIFF-datos", nombre="a.wav", formato="wav"))

    assert t.texto == TEXTO and t.idioma == "es" and t.modelo == INFO
    pedido = sim.pedidos[0]
    assert str(pedido.url) == f"{URL}/audio/transcriptions"
    assert pedido.headers["content-type"].startswith("multipart/form-data")
    contenido = pedido.content
    for campo in (b'name="model"', b"openai/whisper-large-v3-turbo", b'name="language"', b"es",
                  b'name="prompt"', b"osciloscopio", b'filename="a.wav"', b"RIFF-datos"):
        assert campo in contenido


async def test_transcripciones_sin_credito():
    sim = Simulador(error(402, "This request requires at least $0.50 in balance for audio"))
    with pytest.raises(ModeloNoDisponible, match=r"402: .*\$0.50"):
        await Transcripciones(sim.cliente(), "w", INFO).transcribir(Grabacion(contenido=b"x"))


async def test_transcripciones_sin_texto_es_invalida():
    sim = Simulador(lambda _: httpx.Response(200, json={"segments": []}))
    with pytest.raises(RespuestaInvalida):
        await Transcripciones(sim.cliente(), "w", INFO).transcribir(Grabacion(contenido=b"x"))


async def test_parametro_en_null_no_se_manda(catalogo):
    sim = Simulador(chat(json.dumps(INTENCION)))
    await _chat(sim, parametros={"temperature": None, "max_tokens": 4096}).interpretar(_t(), catalogo, Contexto())
    assert "temperature" not in sim.cuerpo(0) and sim.cuerpo(0)["max_tokens"] == 4096


@pytest.mark.parametrize("crudo, limpio", [
    (" [MÚSICA]\n", ""),
    ("[Sonido de la ventana]", ""),
    ("(ruido de fondo) *tos*", ""),
    (" pone el canal 1 a 500 milivoltios por división\n", "pone el canal 1 a 500 milivoltios por división"),
    ("[Música] pone el canal 1 [risas] a 500", "pone el canal 1 a 500"),
])
def test_whisper_cpp_borra_las_anotaciones(crudo, limpio):
    from servidor.transcripcion.whisper_cpp import limpiar
    assert limpiar(crudo) == limpio
