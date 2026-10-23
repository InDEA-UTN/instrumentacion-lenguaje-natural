"""Entidades y objetos valor del dominio.

Ver docs/modelo_dominio.md. Todo es inmutable: cada etapa de la cascada produce un objeto nuevo
en lugar de modificar el anterior, y eso es lo que permite guardar la traza completa de un pedido.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

Valor = int | float | str


class _Inmutable(BaseModel):
    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Modelos (ASR, LLM): lo que todo modelo declara de sí mismo
# ---------------------------------------------------------------------------


class ModeloInfo(_Inmutable):
    """Identifica qué modelo produjo un resultado. Viaja en cada transcripción e intención."""

    nombre: str  # "whisper.cpp-small", "qwen3-4b-ft-v1"
    proveedor: str
    version: str
    ubicacion: Literal["local", "nube"]


# ---------------------------------------------------------------------------
# Catálogo: lo que se declara una vez por instrumento
# ---------------------------------------------------------------------------


class DefParametro(_Inmutable):
    nombre: str
    tipo: Literal["entero", "real"]
    unidad: str | None = None  # unidad del SI; la fija el catálogo, no el modelo
    rango: tuple[float, float] | None = None
    obligatorio: bool = True


class Accion(_Inmutable):
    id: str
    descripcion: str
    parametros: tuple[DefParametro, ...] = ()
    plantilla_scpi: str
    verificacion_scpi: str | None = None
    sensible: bool = False
    ejemplos: tuple[str, ...] = ()

    def parametro(self, nombre: str) -> DefParametro | None:
        return next((p for p in self.parametros if p.nombre == nombre), None)


class Instrumento(_Inmutable):
    id: str
    fabricante: str
    modelo: str
    idn: str | None = None  # respuesta exacta a *IDN?
    recurso_visa: str | None = None
    estado: Literal["verificado", "simulado"] = "simulado"


class CatalogoInstrumento(_Inmutable):
    instrumento: Instrumento
    acciones: dict[str, Accion]

    def accion(self, id: str | None) -> Accion | None:
        return self.acciones.get(id) if id else None


class Magnitud(_Inmutable):
    valor: int | float
    unidad: str | None = None

    def __str__(self) -> str:
        return f"{self.valor:g} {self.unidad}" if self.unidad else f"{self.valor:g}"


# ---------------------------------------------------------------------------
# El pedido: lo que recorre la cascada
# ---------------------------------------------------------------------------


class Grabacion(_Inmutable):
    contenido: bytes = Field(repr=False)
    formato: str = "wav"
    nombre: str = "audio.wav"


class Transcripcion(_Inmutable):
    texto: str
    idioma: str | None = None
    latencia_s: float = 0.0
    modelo: ModeloInfo


class TipoIntencion(StrEnum):
    ACCION = "accion"
    CONSULTA = "consulta"
    ACLARACION = "aclaracion"
    FUERA_DE_ALCANCE = "fuera_de_alcance"


class Intencion(_Inmutable):
    """El contrato entre lo probabilístico y lo determinístico (docs/esquema_intencion.md).

    Los parámetros vienen en unidades del SI y sin unidad: la unidad la define el catálogo.
    """

    tipo: TipoIntencion
    accion: str | None = None
    parametros: dict[str, Valor] = Field(default_factory=dict)
    confianza: float = Field(default=1.0, ge=0.0, le=1.0)
    enunciado: str
    pregunta: str | None = None  # para `aclaracion`: qué hay que repreguntar
    modelo: ModeloInfo | None = None


class Contexto(_Inmutable):
    """Estado de la conversación. Permite "subilo un poco" y repreguntar sin perder lo entendido."""

    instrumento_id: str | None = None
    canal_activo: int | None = None
    ultima_intencion: Intencion | None = None
    aclaracion_pendiente: Intencion | None = None


class ComandoSCPI(_Inmutable):
    """Comando listo para enviar. Solo lo construye `catalogo.armar_comando`."""

    accion: str
    escritura: str | None  # None en una consulta: no se modifica nada
    verificacion: str | None
    parametros: dict[str, Magnitud] = Field(default_factory=dict)
    sensible: bool = False


class Rechazo(_Inmutable):
    motivo: str


class ResultadoEjecucion(_Inmutable):
    comando: ComandoSCPI
    lectura: str | None  # lo que respondió el instrumento, no lo que se pidió


class EstadoInteraccion(StrEnum):
    EJECUTADA = "ejecutada"
    CONSULTADA = "consultada"
    ACLARACION = "aclaracion"
    CONFIRMACION_PENDIENTE = "confirmacion_pendiente"
    RECHAZADA = "rechazada"
    CANCELADA = "cancelada"


class Interaccion(_Inmutable):
    """Traza completa de un pedido. Persistida, es la materia prima del corpus de la fase 2."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    creada: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    estado: EstadoInteraccion
    mensaje: str
    transcripcion: Transcripcion | None = None
    intencion: Intencion | None = None
    comando: ComandoSCPI | None = None
    rechazo: Rechazo | None = None
    resultado: ResultadoEjecucion | None = None
