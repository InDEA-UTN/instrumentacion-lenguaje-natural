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
    return CatalogoInstrumento(instrumento=instrumento, acciones=acciones)


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
