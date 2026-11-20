"""ASR por un servicio de transcripción (protocolo `transcripciones`): `/audio/transcriptions`.

Es la API de transcripción de OpenAI. La implementan OpenRouter (whisper, voxtral, gpt-transcribe
y otros), OpenAI directo, Groq y servidores locales como speaches. A diferencia de `chat_audio`, el
modelo es un reconocedor del habla y no un modelo de lenguaje: no contesta el pedido.
"""

import time

from ..clientes import ClienteHTTP
from ..dominio.modelos import Grabacion, ModeloInfo, Transcripcion


class Transcripciones:
    def __init__(
        self, cliente: ClienteHTTP, modelo: str, info: ModeloInfo, idioma: str = "es",
        parametros: dict | None = None,
    ):
        """parametros: campos extra del formulario (ej. {"prompt": "osciloscopio, milivoltios"})."""
        self._cliente = cliente
        self._modelo = modelo
        self._info = info
        self._idioma = idioma
        self._parametros = dict(parametros or {})

    def info(self) -> ModeloInfo:
        return self._info

    async def salud(self) -> bool:
        return await self._cliente.disponible(self._modelo)

    async def transcribir(self, grabacion: Grabacion) -> Transcripcion:
        inicio = time.perf_counter()
        texto = await self._cliente.transcripcion(
            self._modelo, grabacion.nombre, grabacion.contenido, f"audio/{grabacion.formato}",
            {"language": self._idioma, "response_format": "json", **self._parametros},
        )
        return Transcripcion(
            texto=texto.strip(),
            idioma=self._idioma,
            latencia_s=time.perf_counter() - inicio,
            modelo=self._info,
        )
