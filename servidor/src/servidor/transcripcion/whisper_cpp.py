import time

import httpx

from ..dominio.errores import ModeloNoDisponible, RespuestaInvalida
from ..dominio.modelos import Grabacion, ModeloInfo, Transcripcion


class WhisperCpp:
    """whisper-server de whisper.cpp (servicio `whisper` de docker-compose.yml)."""

    def __init__(self, url: str, modelo: str = "ggml-small", idioma: str = "es", timeout_s: float = 60.0):
        self._url = url.rstrip("/")
        self._idioma = idioma
        self._timeout = timeout_s
        self._info = ModeloInfo(
            nombre=f"whisper.cpp-{modelo}", proveedor="ggml-org", version=modelo, ubicacion="local"
        )

    def info(self) -> ModeloInfo:
        return self._info

    async def salud(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as cliente:
                r = await cliente.get(f"{self._url}/")
            return r.status_code < 500
        except httpx.HTTPError:
            return False

    async def transcribir(self, grabacion: Grabacion) -> Transcripcion:
        inicio = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as cliente:
                r = await cliente.post(
                    f"{self._url}/inference",
                    files={"file": (grabacion.nombre, grabacion.contenido, f"audio/{grabacion.formato}")},
                    data={"language": self._idioma, "response_format": "json"},
                )
                r.raise_for_status()
        except httpx.HTTPError as e:
            raise ModeloNoDisponible(f"whisper.cpp en {self._url}: {e}") from e
        try:
            texto = r.json()["text"]
        except (ValueError, KeyError) as e:
            raise RespuestaInvalida(f"whisper.cpp respondió sin campo 'text': {r.text[:200]}") from e
        return Transcripcion(
            texto=texto.strip(),
            idioma=self._idioma,
            latencia_s=time.perf_counter() - inicio,
            modelo=self._info,
        )
