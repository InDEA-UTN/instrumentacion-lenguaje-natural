"""ASR con un modelo de chat que recibe audio (protocolo `chat_audio`).

Sirve para los proveedores que no tienen un servicio de transcripción, como OpenCode Go: se le
manda la grabación a un modelo de chat con la instrucción de transcribirla literalmente.

Probado el 2026-11-20 con OpenCode Go (BITACORA.md):
- `mimo-v2.6-flash` y `mimo-v2.6-pro` funcionan. Con el razonamiento prendido dejan la respuesta
  vacía y ponen el texto en el campo de razonamiento: proveedores.yaml les apaga el razonamiento.
- `gemini-4-argon` no: la API compatible con OpenAI de Go no le traduce el audio.

Riesgo propio de un modelo de lenguaje: **con silencio o ruido inventa un pedido completo**, armado
con el vocabulario de las instrucciones. Las instrucciones le dan una salida explícita
(`[inaudible]`), que se convierte en texto vacío, y el pipeline no interpreta un texto vacío.
Donde haya un servicio de transcripción real (protocolo `transcripciones`), conviene ese.
"""

import base64
import time

from ..clientes import ClienteHTTP
from ..dominio.modelos import Grabacion, ModeloInfo, Transcripcion

INAUDIBLE = "[inaudible]"

_INSTRUCCIONES = f"""\
Sos un sistema de transcripción automática (ASR). Transcribí literalmente, palabra por palabra, lo
que dice la persona en el audio, en español.
Devolvé SOLO el texto transcripto, sin comillas ni comentarios.
No respondas ni ejecutes el pedido, no lo corrijas, no lo completes y no agregues nada que no se oiga.
Si el audio está en silencio, tiene solo ruido o no se entiende, devolvé exactamente: {INAUDIBLE}
Contexto: suelen ser pedidos a un osciloscopio (canal, volt, milivoltios, base de tiempo, disparo,
acoplamiento, sonda, autoset). Usalo solo para escribir bien palabras que efectivamente se oyen;
nunca para inventar."""


class ChatAudio:
    def __init__(
        self, cliente: ClienteHTTP, modelo: str, info: ModeloInfo, idioma: str = "es",
        parametros: dict | None = None,
    ):
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
        audio = base64.b64encode(grabacion.contenido).decode("ascii")
        texto = await self._cliente.chat(self._modelo, {
            "temperature": 0,
            **self._parametros,
            "messages": [
                {"role": "system", "content": _INSTRUCCIONES},
                {"role": "user", "content": [
                    {"type": "input_audio", "input_audio": {"data": audio, "format": grabacion.formato}},
                ]},
            ],
        })
        texto = texto.strip().strip('"“”«»').strip()
        return Transcripcion(
            texto="" if texto.lower() == INAUDIBLE else texto,
            idioma=self._idioma,
            latencia_s=time.perf_counter() - inicio,
            modelo=self._info,
        )
