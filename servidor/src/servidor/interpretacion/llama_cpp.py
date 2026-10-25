"""Intérprete con un modelo local servido por llama.cpp (llama-server), por salida estructurada.

Le habla a la API compatible con OpenAI (/v1/chat/completions), así que sirve igual para Ollama o
vLLM cambiando la URL. El esquema de respuesta se convierte en una gramática: el modelo no puede
generar un JSON que no lo cumpla.
"""

import httpx

from ..dominio.errores import ModeloNoDisponible, RespuestaInvalida
from ..dominio.modelos import CatalogoInstrumento, Contexto, Intencion, ModeloInfo, Transcripcion
from .comun import a_intencion, esquema_respuesta, instrucciones, mensaje


class LlamaCpp:
    def __init__(self, url: str, modelo: str, timeout_s: float = 60.0):
        self._url = url.rstrip("/")
        self._timeout = timeout_s
        self._info = ModeloInfo(nombre=modelo, proveedor="llama.cpp", version=modelo, ubicacion="local")

    def info(self) -> ModeloInfo:
        return self._info

    async def salud(self) -> bool:
        # /health responde 503 mientras carga el modelo y 200 cuando está listo.
        try:
            async with httpx.AsyncClient(timeout=5.0) as cliente:
                r = await cliente.get(f"{self._url}/health")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def interpretar(
        self, transcripcion: Transcripcion, catalogo: CatalogoInstrumento, contexto: Contexto
    ) -> Intencion:
        cuerpo = {
            # El prompt de sistema es igual en todos los pedidos: llama-server lo guarda en caché y
            # solo procesa el mensaje nuevo. El primer pedido después de arrancar tarda bastante más.
            "messages": [
                {"role": "system", "content": instrucciones(catalogo)},
                {"role": "user", "content": mensaje(transcripcion, contexto)},
            ],
            "temperature": 0,  # el mismo pedido tiene que dar siempre la misma intención
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "intencion", "schema": esquema_respuesta(catalogo)},
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as cliente:
                r = await cliente.post(f"{self._url}/v1/chat/completions", json=cuerpo)
        except httpx.TimeoutException as e:
            raise ModeloNoDisponible(f"{self._info.nombre} no respondió en {self._timeout:g} s") from e
        except httpx.HTTPError as e:
            raise ModeloNoDisponible(f"{self._info.nombre}: {type(e).__name__} {e}") from e
        if r.status_code != 200:
            raise ModeloNoDisponible(f"{self._info.nombre} respondió {r.status_code}: {r.text[:300]}")
        respuesta = r.json()
        try:
            texto = respuesta["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise RespuestaInvalida(f"{self._info.nombre} respondió fuera de esquema: {str(respuesta)[:300]}") from e
        return a_intencion(texto, transcripcion, catalogo, self._info)
