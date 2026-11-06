from pathlib import Path

import yaml
from pydantic import ValidationError

from ..dominio.errores import CatalogoInvalido
from ..dominio.modelos import Accion, CatalogoInstrumento, DefParametro, Instrumento
from .scpi import campos_de_plantilla


def cargar_catalogo(ruta: str | Path) -> CatalogoInstrumento:
    """Lee el YAML de un instrumento (formato de docs/esquema_intencion.md, sección 2)."""
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    try:
        instrumento = Instrumento(**datos["instrumento"])
        acciones = {
            id_accion: _accion(id_accion, decl) for id_accion, decl in datos["acciones"].items()
        }
    except (KeyError, TypeError, ValidationError) as e:
        raise CatalogoInvalido(f"{ruta}: {e}") from e
    _verificar_tipos_homonimos(acciones)
    return CatalogoInstrumento(instrumento=instrumento, acciones=acciones)


def _verificar_tipos_homonimos(acciones: dict[str, Accion]) -> None:
    """El esquema de respuesta del intérprete declara cada parámetro una sola vez, por nombre
    (interpretacion/comun.py). Si dos acciones usan el mismo nombre con tipos distintos, la gramática
    le exigiría a una de ellas el tipo de la otra: se rechaza el catálogo antes de que pase."""
    tipos: dict[str, tuple[str, str]] = {}  # parámetro -> (tipo, acción donde se declaró primero)
    for accion in acciones.values():
        for p in accion.parametros:
            previo = tipos.setdefault(p.nombre, (p.tipo, accion.id))
            if previo[0] != p.tipo:
                raise CatalogoInvalido(
                    f"El parámetro '{p.nombre}' es {previo[0]} en '{previo[1]}' y {p.tipo} en "
                    f"'{accion.id}'. Los parámetros con el mismo nombre tienen que tener el mismo tipo."
                )


def _accion(id_accion: str, decl: dict) -> Accion:
    parametros = tuple(
        DefParametro(nombre=nombre, **p) for nombre, p in (decl.get("parametros") or {}).items()
    )
    accion = Accion(
        id=id_accion,
        descripcion=decl["descripcion"],
        parametros=parametros,
        plantilla_scpi=decl["plantilla_scpi"],
        verificacion_scpi=decl.get("verificacion_scpi"),
        sensible=decl.get("sensible", False),
        ejemplos=tuple(decl.get("ejemplos") or ()),
    )
    declarados = {p.nombre for p in parametros}
    for plantilla in (accion.plantilla_scpi, accion.verificacion_scpi or ""):
        sobrantes = campos_de_plantilla(plantilla) - declarados
        if sobrantes:
            raise CatalogoInvalido(
                f"{id_accion}: la plantilla usa parámetros no declarados: {sorted(sobrantes)}"
            )
    return accion
