"""Intérprete con Gemini (API REST de Google AI Studio), por salida estructurada.

Se usa salida forzada a un esquema y no llamada a herramientas porque un solo esquema cubre los
cuatro tipos de intención, incluidos `aclaracion` y `fuera_de_alcance`.
"""

import httpx

from ..dominio.errores import ModeloNoDisponible, RespuestaInvalida
from ..dominio.modelos import CatalogoInstrumento, Contexto, Intencion, ModeloInfo, Transcripcion
from .comun import a_intencion, esquema_respuesta, instrucciones, mensaje

_API = "https://generativelanguage.googleapis.com/v1beta"


class Gemini:
    def __init__(self, api_key: str | None, modelo: str = "gemini-3.8-flash", timeout_s: float = 15.0,
                 reintentos: int = 1):
        self._api_key = api_key
        self._modelo = modelo
        self._timeout = timeout_s
        self._reintentos = reintentos
        self._info = ModeloInfo(nombre=modelo, proveedor="google", version=modelo, ubicacion="nube")

    def info(self) -> ModeloInfo:
        return self._info

    async def salud(self) -> bool:
        if not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as cliente:
                r = await cliente.get(f"{_API}/models/{self._modelo}", headers=self._cabeceras())
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def interpretar(
        self, transcripcion: Transcripcion, catalogo: CatalogoInstrumento, contexto: Contexto
    ) -> Intencion:
        if not self._api_key:
            raise ModeloNoDisponible("Falta GEMINI_API_KEY (ver servidor/.env)")
        cuerpo = {
            "systemInstruction": {"parts": [{"text": instrucciones(catalogo)}]},
            "contents": [{"role": "user", "parts": [{"text": mensaje(transcripcion, contexto)}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": esquema_respuesta(catalogo),
                "thinkingConfig": {"thinkingLevel": "low"},  # latencia: es una clasificación acotada
            },
        }
        # La latencia de la API es irregular: casi todas las respuestas tardan pocos segundos, pero
        # algunas quedan colgadas más de un minuto. Cortar y reintentar sale más rápido que esperar.
        for intento in range(self._reintentos + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as cliente:
                    r = await cliente.post(
                        f"{_API}/models/{self._modelo}:generateContent", headers=self._cabeceras(), json=cuerpo
                    )
                break
            except httpx.TimeoutException as e:
                if intento == self._reintentos:
                    raise ModeloNoDisponible(
                        f"Gemini no respondió en {self._timeout:g} s ({intento + 1} intentos)"
                    ) from e
            except httpx.HTTPError as e:
                raise ModeloNoDisponible(f"Gemini: {type(e).__name__} {e}") from e
        if r.status_code != 200:
            raise ModeloNoDisponible(f"Gemini respondió {r.status_code}: {r.text[:300]}")
        respuesta = r.json()
        try:
            # El JSON puede venir partido en varias `parts`; las de razonamiento no forman parte de él.
            partes = respuesta["candidates"][0]["content"]["parts"]
            texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
        except (KeyError, IndexError, TypeError) as e:
            raise RespuestaInvalida(f"Gemini respondió fuera de esquema: {str(respuesta)[:300]}") from e
        return a_intencion(texto, transcripcion, catalogo, self._info)

    def _cabeceras(self) -> dict[str, str]:
        return {"x-goog-api-key": self._api_key or ""}
