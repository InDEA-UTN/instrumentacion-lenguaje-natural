import pytest

from servidor.catalogo import cargar_catalogo
from servidor.config import Configuracion
from servidor.dominio.errores import CatalogoInvalido

_INSTRUMENTO = """\
instrumento: {id: prueba, fabricante: X, modelo: Y}
acciones:
"""


def _yaml(tmp_path, acciones: str):
    ruta = tmp_path / "catalogo.yaml"
    ruta.write_text(_INSTRUMENTO + acciones, encoding="utf-8")
    return ruta


def test_catalogo_por_defecto_existe():
    # Viaja con el paquete: tiene que encontrarse sin definir CATALOGO (bitácora 2026-10-25).
    assert cargar_catalogo(Configuracion().catalogo).instrumento.id == "osciloscopio_generico_4ch"


def test_rechaza_parametros_homonimos_con_tipos_distintos(tmp_path):
    ruta = _yaml(tmp_path, """\
  a:
    descripcion: a
    parametros: {valor: {tipo: real}}
    plantilla_scpi: "A {valor}"
  b:
    descripcion: b
    parametros: {valor: {tipo: entero}}
    plantilla_scpi: "B {valor}"
""")
    with pytest.raises(CatalogoInvalido, match="'valor' es real en 'a' y entero en 'b'"):
        cargar_catalogo(ruta)


def test_admite_parametros_homonimos_del_mismo_tipo(tmp_path):
    ruta = _yaml(tmp_path, """\
  a:
    descripcion: a
    parametros: {valor: {tipo: real, rango: [0, 1]}}
    plantilla_scpi: "A {valor}"
  b:
    descripcion: b
    parametros: {valor: {tipo: real, rango: [0, 100]}}
    plantilla_scpi: "B {valor}"
""")
    assert set(cargar_catalogo(ruta).acciones) == {"a", "b"}
