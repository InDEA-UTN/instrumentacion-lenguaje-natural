import pytest

from servidor.dominio.modelos import ComandoSCPI, Intencion, Rechazo, TipoIntencion
from servidor.validacion import validar


def _accion(accion, **parametros):
    return Intencion(tipo=TipoIntencion.ACCION, accion=accion, parametros=parametros, enunciado="")


def test_arma_el_comando(catalogo):
    c = validar(_accion("configurar_escala_vertical", canal=1, valor=0.5), catalogo)
    assert isinstance(c, ComandoSCPI)
    assert c.escritura == ":CHANnel1:SCALe 0.5"
    assert c.verificacion == ":CHANnel1:SCALe?"
    assert str(c.parametros["valor"]) == "0.5 V"


def test_consulta_no_escribe(catalogo):
    i = Intencion(tipo=TipoIntencion.CONSULTA, accion="configurar_escala_vertical",
                  parametros={"canal": 2}, enunciado="")
    c = validar(i, catalogo)
    assert c.escritura is None and c.verificacion == ":CHANnel2:SCALe?"


@pytest.mark.parametrize("intencion, motivo", [
    (_accion("borrar_disco"), "no está en el catálogo"),
    (_accion("configurar_escala_vertical", valor=0.5), "Faltan"),
    (_accion("configurar_escala_vertical", canal=5, valor=0.5), "fuera de rango"),
    (_accion("configurar_escala_vertical", canal=1, valor=100.0), "fuera de rango"),
    (_accion("configurar_escala_vertical", canal=1.5, valor=0.5), "entero"),
    (_accion("configurar_escala_vertical", canal=1, valor="medio"), "real"),
    (_accion("configurar_escala_vertical", canal=1, valor=0.5, offset=0), "no admite"),
    (Intencion(tipo=TipoIntencion.FUERA_DE_ALCANCE, enunciado=""), "no se ejecuta"),
])
def test_rechaza(catalogo, intencion, motivo):
    r = validar(intencion, catalogo)
    assert isinstance(r, Rechazo)
    assert motivo in r.motivo


def test_marca_sensible(catalogo):
    c = validar(_accion("reiniciar_instrumento"), catalogo)
    assert c.sensible and c.escritura == "*RST"
