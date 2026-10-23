"""Fuente de verdad del sistema. De acá salen las herramientas del modelo, las validaciones y el SCPI.

Ninguna cadena SCPI se arma fuera de este módulo.
"""

from .cargador import cargar_catalogo
from .esquema import a_json_schema
from .scpi import armar_comando, campos_de_plantilla

__all__ = ["cargar_catalogo", "a_json_schema", "armar_comando", "campos_de_plantilla"]
