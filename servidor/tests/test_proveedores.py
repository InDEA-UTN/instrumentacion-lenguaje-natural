"""Registro de modelos (proveedores.py) y el proveedores.yaml real. Sin red."""

import pytest

from servidor.config import PROVEEDORES
from servidor.interpretacion.chat import Chat
from servidor.interpretacion.fake import InterpreteFake
from servidor.proveedores import (
    ModeloDesconocido,
    ProveedoresInvalidos,
    RegistroModelos,
    cargar_proveedores,
)
from servidor.transcripcion.chat_audio import ChatAudio
from servidor.transcripcion.transcripciones import Transcripciones
from servidor.transcripcion.whisper_cpp import WhisperCpp

ENTORNO = {"OPENCODE_API_KEY": "oc", "OPENROUTER_API_KEY": "or"}


@pytest.fixture
def registro():
    return RegistroModelos(PROVEEDORES, ENTORNO)


def test_el_yaml_real_carga_y_tiene_los_tres_proveedores_visibles(registro):
    visibles = {i.partition("/")[0] for etapa in ("asr", "interprete") for i in registro.ids(etapa)}
    assert visibles == {"local", "opencode-go", "openrouter"}


@pytest.mark.parametrize("etapa", ["asr", "interprete"])
def test_todo_modelo_declarado_arma_su_adaptador(registro, etapa):
    for id_ in registro.ids(etapa, visibles=False):
        adaptador = registro.asr(id_) if etapa == "asr" else registro.interprete(id_)
        if not id_.startswith("prueba/"):  # los fakes conservan su identidad: los tests la miran
            assert adaptador.info().proveedor == id_.partition("/")[0]


@pytest.mark.parametrize("etapa, nombre, esperado", [
    ("asr", "local/whisper-small", "local/whisper-small"),
    ("interprete", "openrouter", "openrouter/z-ai/glm-5.3-flash"),  # predeterminado del proveedor
    ("asr", "openrouter/openai/whisper-large-v3-turbo", "openrouter/openai/whisper-large-v3-turbo"),
    # Nombres de antes del registro: siguen andando.
    ("asr", "whisper_cpp", "local/whisper-small"),
    ("interprete", "llama_cpp", "local/qwen3.5-4b"),
    ("interprete", "opencode", "opencode-go/glm-5.3-flash"),
    ("asr", "opencode", "opencode-go/mimo-v2.6-flash"),
    ("interprete", "gemini", "google/gemini-3.8-flash"),
    ("interprete", "fake", "prueba/fake"),
])
def test_resolver(registro, etapa, nombre, esperado):
    assert registro.resolver(etapa, nombre) == esperado


@pytest.mark.parametrize("etapa, nombre", [
    ("interprete", "nadie/modelo"),
    ("interprete", "openrouter/no-declarado"),
    ("asr", "opencode-go/glm-5.3-flash"),  # existe, pero es un intérprete
    ("asr", "google"),  # no tiene ASR
])
def test_resolver_rechaza_lo_no_declarado(registro, etapa, nombre):
    with pytest.raises(ModeloDesconocido):
        registro.resolver(etapa, nombre)


def test_protocolos_y_configuracion_de_cada_proveedor(registro):
    assert isinstance(registro.asr("local/whisper-small"), WhisperCpp)
    assert isinstance(registro.asr("opencode-go/mimo-v2.6-flash"), ChatAudio)
    assert isinstance(registro.asr("openrouter/openai/whisper-large-v3-turbo"), Transcripciones)
    assert isinstance(registro.interprete("prueba/fake"), InterpreteFake)
    openrouter = registro.interprete("openrouter/z-ai/glm-5.3-flash")
    assert isinstance(openrouter, Chat)
    # Los del proveedor y los del modelo se combinan; los del modelo pisan.
    assert openrouter._estricto and openrouter._parametros == {
        "provider": {"require_parameters": True}, "max_tokens": 4096, "reasoning": {"effort": "low"},
    }
    assert registro.interprete("openrouter/openai/gpt-5.4-mini")._parametros["temperature"] is None
    mimo = registro.asr("opencode-go/mimo-v2.6-flash")
    assert mimo._parametros == {"reasoning_effort": "none"}
    assert registro.interprete("opencode-go/glm-5.3-flash") is registro.interprete("opencode")  # se reutiliza


def test_las_variables_del_yaml_salen_del_entorno():
    local = RegistroModelos(PROVEEDORES, {"LLM_URL": "http://llm:8080"}).interprete("local/qwen3.5-4b")
    assert local._cliente.url == "http://llm:8080/v1"
    por_defecto = RegistroModelos(PROVEEDORES, {}).interprete("local/qwen3.5-4b")
    assert por_defecto._cliente.url == "http://localhost:8081/v1"


async def test_listado_para_el_front_sin_claves():
    # Sin claves: los modelos en la nube aparecen, pero no disponibles y con el motivo. No sale
    # ningún pedido para ellos.
    registro = RegistroModelos(PROVEEDORES, {})

    async def sin_red(*_):
        return False

    for etapa in ("asr", "interprete"):
        for id_ in registro.ids(etapa):
            if id_.startswith("local/"):
                (registro.asr(id_) if etapa == "asr" else registro.interprete(id_)).salud = sin_red

    listado = await registro.listado({"asr": "local/whisper-small", "interprete": "local/qwen3.5-4b"})
    assert listado["asr"]["predeterminado"] == "local/whisper-small"
    proveedores = {p["id"]: p for p in listado["interprete"]["proveedores"]}
    assert set(proveedores) == {"local", "opencode-go", "openrouter"}  # sin los ocultos
    openrouter = proveedores["openrouter"]
    assert openrouter["predeterminado"] == "openrouter/z-ai/glm-5.3-flash"
    assert not openrouter["listo"]
    assert all(m["motivo"] == "Falta OPENROUTER_API_KEY en servidor/.env" for m in openrouter["modelos"])
    assert proveedores["local"]["modelos"][0]["motivo"] == "No responde"


def _yaml(tmp_path, texto):
    ruta = tmp_path / "p.yaml"
    ruta.write_text(texto)
    return ruta


@pytest.mark.parametrize("texto, motivo", [
    ("proveedores:\n  a:\n    nombre: A\n    modelos:\n      m: {etapa: asr, protocolo: telepatia}\n", "telepatia"),
    ("proveedores:\n  a:\n    nombre: A\n    predeterminados: {asr: m}\n    modelos:\n      m: {etapa: interprete, protocolo: chat}\n",
     "predeterminado"),
    ("proveedores:\n  a:\n    nombre: A\n    api_key: sk-123\n    modelos: {}\n", "api_key"),  # una clave escrita en el YAML
    ("proveedores:\n  a/b:\n    nombre: A\n    modelos: {}\n", "'/'"),
])
def test_yaml_invalido(tmp_path, texto, motivo):
    with pytest.raises(ProveedoresInvalidos, match=motivo):
        cargar_proveedores(_yaml(tmp_path, texto), {})
