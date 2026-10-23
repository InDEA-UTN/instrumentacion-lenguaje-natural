"""Traducción del catálogo a JSON Schema, neutral respecto del proveedor.

Cada adaptador de `interpretacion` toma esto y lo envuelve en el formato de su API (herramientas,
salida estructurada). Así la declaración de una acción se escribe una sola vez.
"""

from ..dominio.modelos import Accion, CatalogoInstrumento, DefParametro

_TIPOS = {"entero": "integer", "real": "number"}


def a_json_schema(catalogo: CatalogoInstrumento) -> list[dict]:
    """Una herramienta por acción: {nombre, descripcion, parametros (JSON Schema)}."""
    return [_herramienta(a) for a in catalogo.acciones.values()]


def _herramienta(accion: Accion) -> dict:
    return {
        "nombre": accion.id,
        "descripcion": accion.descripcion,
        "parametros": {
            "type": "object",
            "properties": {p.nombre: _propiedad(p) for p in accion.parametros},
            "required": [p.nombre for p in accion.parametros if p.obligatorio],
            "additionalProperties": False,
        },
    }


def _propiedad(p: DefParametro) -> dict:
    prop: dict = {"type": _TIPOS[p.tipo]}
    if p.unidad:
        prop["description"] = f"En {p.unidad} (unidades del SI, sin prefijos)."
    if p.rango:
        prop["minimum"], prop["maximum"] = p.rango
    return prop
