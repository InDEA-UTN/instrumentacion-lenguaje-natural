"""Arma el pipeline: modelos predeterminados (proveedores.py), catálogo e instrumento.

Qué modelos hay se declara en proveedores.yaml; acá solo se eligen los predeterminados y la
conexión con el instrumento.
"""

from collections.abc import Callable

from .catalogo import cargar_catalogo
from .config import Configuracion
from .dominio.modelos import CatalogoInstrumento
from .dominio.puertos import ConexionInstrumento
from .ejecucion import ConexionVisa, Ejecutor, InstrumentoFake
from .pipeline import ProcesarPedido
from .proveedores import RegistroModelos

CONEXIONES: dict[str, Callable[[Configuracion, CatalogoInstrumento], ConexionInstrumento]] = {
    "fake": lambda c, cat: InstrumentoFake(),
    "visa": lambda c, cat: ConexionVisa(
        modelo=cat.instrumento.modelo,
        recurso=c.visa_recurso or cat.instrumento.recurso_visa,
        backend=c.visa_backend,
        timeout_ms=c.visa_timeout_ms,
        al_conectar=c.visa_al_conectar,
        consulta_eventos=c.visa_consulta_eventos,
    ),
}


def construir_pipeline(c: Configuracion | None = None, registro: RegistroModelos | None = None) -> ProcesarPedido:
    c = c or Configuracion()
    registro = registro or RegistroModelos(c.proveedores)
    catalogo = cargar_catalogo(c.catalogo)
    try:
        conexion = CONEXIONES[c.instrumento](c, catalogo)
    except KeyError:
        raise ValueError(f"Instrumento '{c.instrumento}' desconocido. Disponibles: {', '.join(CONEXIONES)}") from None
    return ProcesarPedido(
        asr=registro.asr(c.asr_motor),
        interprete=registro.interprete(c.interprete),
        catalogo=catalogo,
        ejecutor=Ejecutor(conexion),
        umbral_confianza=c.umbral_confianza,
    )
