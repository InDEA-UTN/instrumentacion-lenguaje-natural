"""Cliente HTTP para las API compatibles con la de OpenAI: llama.cpp, OpenCode, OpenRouter y otras.

Lo usan los adaptadores de protocolo (interpretacion/chat.py, transcripcion/chat_audio.py,
transcripcion/transcripciones.py). Lo propio de cada proveedor (URL, clave, cabeceras) no está
acá sino en proveedores.yaml.
"""

from __future__ import annotations

from uuid import uuid4

import httpx

from .dominio.errores import ModeloNoDisponible, RespuestaInvalida

# Algunos proveedores (OpenCode Go) piden identificarse con un agente propio.
AGENTE = "instrumentacion-lenguaje-natural/0.1"
# Y un identificador estable por conversación. Cada pedido del servidor es independiente (el
# contexto viaja en el mensaje), así que alcanza con uno por proceso.
SESION = uuid4().hex


class RechazoDelProveedor(ModeloNoDisponible):
    """El proveedor respondió con un error. `estado` permite decidir si vale reintentar."""

    def __init__(self, mensaje: str, estado: int):
        super().__init__(mensaje)
        self.estado = estado


class ClienteHTTP:
    def __init__(
        self,
        url: str,
        etiqueta: str,
        api_key: str | None = None,
        nombre_clave: str | None = None,
        cabeceras: dict[str, str] | None = None,
        cabecera_sesion: str | None = None,
        timeout_s: float = 30.0,
        modelos_url: str | None = None,
        salud_url: str | None = None,
        transporte: httpx.AsyncBaseTransport | None = None,  # para los tests
    ):
        """
        etiqueta: cómo se nombra al proveedor en los errores ("OpenRouter").
        nombre_clave: la variable de entorno de la clave. Si se declara y no hay clave, el modelo
            no está disponible y ningún pedido sale.
        modelos_url / salud_url: cómo se sabe si un modelo está disponible (ver `disponible`).
        """
        self.url = url.rstrip("/")
        self.etiqueta = etiqueta
        self._api_key = api_key
        self.nombre_clave = nombre_clave
        self._cabeceras = {"User-Agent": AGENTE, **(cabeceras or {})}
        if api_key:
            self._cabeceras["Authorization"] = f"Bearer {api_key}"
        if cabecera_sesion:
            self._cabeceras[cabecera_sesion] = SESION
        self._timeout = timeout_s
        self._modelos_url = modelos_url
        self._salud_url = salud_url
        self._transporte = transporte

    @property
    def falta_clave(self) -> bool:
        return bool(self.nombre_clave) and not self._api_key

    def _cliente(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self._transporte, headers=self._cabeceras)

    async def disponible(self, modelo: str) -> bool:
        """No lanza excepciones. Con `modelos_url`, el modelo tiene que figurar en el listado; con
        `salud_url`, alcanza con que responda 200. No prueba la clave: costaría un pedido pago."""
        if self.falta_clave:
            return False
        url = self._modelos_url or self._salud_url
        if url is None:
            return True
        try:
            async with self._cliente(5.0) as cliente:
                r = await cliente.get(url)
            if r.status_code != 200:
                return False
            if not self._modelos_url:
                return True
            datos = r.json()
        except (httpx.HTTPError, ValueError):
            return False
        lista = datos.get("data", []) if isinstance(datos, dict) else datos
        return any(isinstance(m, dict) and m.get("id") == modelo for m in lista)

    async def chat(self, modelo: str, cuerpo: dict) -> str:
        """Pedido a `/chat/completions`. Devuelve el texto de la respuesta."""
        datos = await self._post(modelo, "/chat/completions", json={"model": modelo, **cuerpo})
        try:
            contenido = datos["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise RespuestaInvalida(f"{self._quien(modelo)} respondió fuera de esquema: {str(datos)[:300]}") from e
        # Algunos proveedores parten el contenido en partes. El razonamiento viaja aparte
        # (`reasoning`, `reasoning_content`) y no forma parte de la respuesta.
        if isinstance(contenido, list):
            contenido = "".join(p.get("text", "") for p in contenido if isinstance(p, dict))
        if not isinstance(contenido, str):
            raise RespuestaInvalida(f"{self._quien(modelo)} respondió sin texto: {str(datos)[:300]}")
        return contenido

    async def transcripcion(self, modelo: str, nombre: str, audio: bytes, tipo: str, campos: dict) -> str:
        """Pedido a `/audio/transcriptions` (multipart, como la API de OpenAI)."""
        datos = await self._post(
            modelo, "/audio/transcriptions",
            data={"model": modelo, **{k: str(v) for k, v in campos.items()}},
            files={"file": (nombre, audio, tipo)},
        )
        texto = datos.get("text") if isinstance(datos, dict) else None
        if not isinstance(texto, str):
            raise RespuestaInvalida(f"{self._quien(modelo)} respondió sin campo 'text': {str(datos)[:300]}")
        return texto

    async def _post(self, modelo: str, ruta: str, **kwargs) -> dict:
        if self.falta_clave:
            raise ModeloNoDisponible(f"Falta {self.nombre_clave} en servidor/.env")
        quien = self._quien(modelo)
        try:
            async with self._cliente(self._timeout) as cliente:
                r = await cliente.post(f"{self.url}{ruta}", **kwargs)
        except httpx.TimeoutException as e:
            raise ModeloNoDisponible(f"{quien} no respondió en {self._timeout:g} s") from e
        except httpx.HTTPError as e:
            raise ModeloNoDisponible(f"{quien}: {type(e).__name__} {e}") from e
        try:
            datos = r.json()
        except ValueError:
            datos = None
        if r.status_code != 200:
            raise RechazoDelProveedor(f"{quien} respondió {r.status_code}: {_mensaje(datos, r.text)}", r.status_code)
        if not isinstance(datos, dict):
            raise RespuestaInvalida(f"{quien} respondió algo que no es JSON: {r.text[:300]}")
        # OpenRouter puede responder 200 con el error en el cuerpo (o en la opción elegida).
        error = datos.get("error") or _error_de_opcion(datos)
        if error:
            estado = error.get("code") if isinstance(error, dict) else None
            estado = estado if isinstance(estado, int) else 502
            raise RechazoDelProveedor(f"{quien} respondió {estado}: {_mensaje({'error': error}, '')}", estado)
        return datos

    def _quien(self, modelo: str) -> str:
        return f"{modelo} ({self.etiqueta})"


def _error_de_opcion(datos: dict):
    opciones = datos.get("choices")
    if isinstance(opciones, list) and opciones and isinstance(opciones[0], dict):
        return opciones[0].get("error")
    return None


def _mensaje(datos, crudo: str) -> str:
    """El mensaje legible de un error ({"error": {"message": ...}}), o el cuerpo recortado."""
    if isinstance(datos, dict):
        error = datos.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"][:300]
        if isinstance(error, str):
            return error[:300]
    return crudo[:300]
