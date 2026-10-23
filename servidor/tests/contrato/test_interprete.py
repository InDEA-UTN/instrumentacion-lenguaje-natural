"""Contrato del puerto Interprete. Todo intérprete nuevo se agrega a IMPLEMENTACIONES y tiene que pasarlo."""

import pytest

from servidor.dominio.modelos import Contexto, Intencion, ModeloInfo, TipoIntencion, Transcripcion
from servidor.dominio.puertos import Interprete
from servidor.config import Configuracion
from servidor.interpretacion.fake import InterpreteFake
from servidor.interpretacion.gemini import Gemini

IMPLEMENTACIONES = [
    pytest.param(lambda: InterpreteFake(), id="fake"),
    pytest.param(
        lambda: Gemini(api_key=(c := Configuracion()).gemini_api_key, modelo=c.gemini_modelo),
        id="gemini",
        marks=pytest.mark.integracion,
    ),
]

ASR = ModeloInfo(nombre="test", proveedor="test", version="0", ubicacion="local")


def _t(texto: str) -> Transcripcion:
    return Transcripcion(texto=texto, modelo=ASR)


@pytest.fixture(params=IMPLEMENTACIONES)
async def interprete(request) -> Interprete:
    interprete = request.param()
    if not await interprete.salud():
        pytest.skip(f"{interprete.info().nombre} no está disponible")
    return interprete


def test_cumple_el_protocolo(interprete):
    assert isinstance(interprete, Interprete)
    assert isinstance(interprete.info(), ModeloInfo)


async def test_ejemplo_del_catalogo(interprete, catalogo):
    i = await interprete.interpretar(
        _t("poné el canal uno en quinientos milivoltios por división"), catalogo, Contexto()
    )
    assert i.tipo == TipoIntencion.ACCION
    assert i.accion == "configurar_escala_vertical"
    assert i.parametros == {"canal": 1, "valor": pytest.approx(0.5)}


async def test_fuera_de_catalogo_no_se_aproxima(interprete, catalogo):
    i = await interprete.interpretar(_t("prendé la cafetera"), catalogo, Contexto())
    assert i.tipo == TipoIntencion.FUERA_DE_ALCANCE
    assert i.accion is None and i.parametros == {}


async def test_intencion_bien_formada(interprete, catalogo):
    texto = "subí la escala"
    i = await interprete.interpretar(_t(texto), catalogo, Contexto())
    assert isinstance(i, Intencion)
    assert i.modelo == interprete.info()
    assert i.enunciado == texto
    assert 0.0 <= i.confianza <= 1.0
    if i.accion is not None:
        assert catalogo.accion(i.accion) is not None
