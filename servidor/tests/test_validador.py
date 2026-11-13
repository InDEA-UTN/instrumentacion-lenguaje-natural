import pytest

from servidor.dominio.modelos import ComandoSCPI, Intencion, Rechazo, TipoIntencion
from servidor.validacion import validar


def _accion(accion, **parametros):
    return Intencion(tipo=TipoIntencion.ACCION, accion=accion, parametros=parametros, enunciado="")


def test_arma_el_comando(catalogo):
    c = validar(_accion("configurar_escala_vertical", canal=1, valor=0.5), catalogo)
    assert isinstance(c, ComandoSCPI)
    assert c.escritura == "CH1:SCAle 0.5"
    assert c.verificacion == "CH1:SCAle?"
    assert str(c.parametros["valor"]) == "0.5 V"


def test_consulta_no_escribe(catalogo):
    i = Intencion(tipo=TipoIntencion.CONSULTA, accion="configurar_escala_vertical",
                  parametros={"canal": 2}, enunciado="")
    c = validar(i, catalogo)
    assert c.escritura is None and c.verificacion == "CH2:SCAle?"


@pytest.mark.parametrize("intencion, motivo", [
    (_accion("borrar_disco"), "no está en el catálogo"),
    (_accion("configurar_escala_vertical", valor=0.5), "Faltan"),
    (_accion("configurar_escala_vertical", canal=3, valor=0.5), "fuera de rango"),
    (_accion("configurar_escala_vertical", canal=1, valor=100.0), "fuera de rango"),
    (_accion("configurar_acoplamiento", canal=1, acoplamiento="alterna"), "una de: AC, DC, GND"),
    (_accion("controlar_adquisicion", adquisicion=True), "una de: RUN, STOP"),
    (_accion("configurar_atenuacion_sonda", canal=1, atenuacion=3), "una de"),
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
    c = validar(_accion("autoescala"), catalogo)
    assert c.sensible and c.escritura == "AUTOSet EXECute"


def test_consulta_descarta_parametros_que_no_usa(catalogo):
    # "¿En cuánto está la base de tiempo?" con un `valor` agregado por el modelo: se lee igual.
    i = Intencion(tipo=TipoIntencion.CONSULTA, accion="configurar_base_tiempo",
                  parametros={"valor": 0.001}, enunciado="")
    c = validar(i, catalogo)
    assert isinstance(c, ComandoSCPI)
    assert c.escritura is None and c.verificacion == "HORizontal:MAIn:SCAle?"
    assert c.parametros == {}


def test_consulta_rechaza_parametros_ajenos_a_la_accion(catalogo):
    i = Intencion(tipo=TipoIntencion.CONSULTA, accion="configurar_escala_vertical",
                  parametros={"canal": 1, "offset": 0}, enunciado="")
    r = validar(i, catalogo)
    assert isinstance(r, Rechazo) and "no admite" in r.motivo


@pytest.mark.parametrize("accion, parametros, escritura", [
    ("configurar_acoplamiento", {"canal": 2, "acoplamiento": "gnd"}, "CH2:COUPling GND"),
    ("configurar_atenuacion_sonda", {"canal": 1, "atenuacion": 10}, "CH1:PRObe 10"),
    ("configurar_atenuacion_sonda", {"canal": 1, "atenuacion": 10.0}, "CH1:PRObe 10"),
    ("mostrar_canal", {"canal": 2, "visible": "ON"}, "SELect:CH2 ON"),
    ("configurar_fuente_disparo", {"fuente": "ch2"}, "TRIGger:MAIn:EDGE:SOUrce CH2"),
    ("controlar_adquisicion", {"adquisicion": "Stop"}, "ACQuire:STATE STOP"),
    ("configurar_nivel_disparo", {"valor": -0.2}, "TRIGger:MAIn:LEVel -0.2"),
    ("configurar_base_tiempo", {"valor": 1e-5}, "HORizontal:MAIn:SCAle 1e-05"),
    ("medir", {"canal": 1, "magnitud": "pk2pk"}, "MEASUrement:IMMed:SOUrce CH1;TYPe PK2pk"),
])
def test_opciones_salen_escritas_como_en_el_catalogo(catalogo, accion, parametros, escritura):
    c = validar(_accion(accion, **parametros), catalogo)
    assert isinstance(c, ComandoSCPI), c
    assert c.escritura == escritura
