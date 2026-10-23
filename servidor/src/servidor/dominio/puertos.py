"""Puertos: las interfaces que el dominio exige y los adaptadores implementan.

`Modelo` es la interfaz común a todo modelo (ASR, LLM). Cualquier implementación que cumpla el
protocolo es intercambiable por configuración; los tests de contrato en tests/contrato/ lo verifican.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .modelos import CatalogoInstrumento, Contexto, Grabacion, Intencion, ModeloInfo, Transcripcion


@runtime_checkable
class Modelo(Protocol):
    def info(self) -> ModeloInfo: ...

    async def salud(self) -> bool:
        """True si el modelo está listo para responder. No lanza excepciones."""
        ...


@runtime_checkable
class MotorASR(Modelo, Protocol):
    async def transcribir(self, grabacion: Grabacion) -> Transcripcion:
        """Lanza ModeloNoDisponible si el motor no responde."""
        ...


@runtime_checkable
class Interprete(Modelo, Protocol):
    async def interpretar(
        self, transcripcion: Transcripcion, catalogo: CatalogoInstrumento, contexto: Contexto
    ) -> Intencion:
        """Devuelve siempre una Intencion bien formada.

        Si el modelo responde fuera de esquema, el adaptador devuelve `fuera_de_alcance` o lanza
        RespuestaInvalida; nunca deja pasar una respuesta a medio armar.
        """
        ...


class ConexionInstrumento(Protocol):
    """Canal hacia el instrumento: PyVISA real, pyvisa-sim o un fake en memoria."""

    def escribir(self, comando: str) -> None: ...

    def consultar(self, comando: str) -> str: ...
