"""Intérprete con Gemini (API REST de Google AI Studio), por salida estructurada.

Se usa salida forzada a un esquema y no llamada a herramientas porque un solo esquema cubre los
cuatro tipos de intención, incluidos `aclaracion` y `fuera_de_alcance`.
"""

import json

import httpx
from pydantic import ValidationError

from ..catalogo import a_json_schema
from ..dominio.errores import ModeloNoDisponible, RespuestaInvalida
from ..dominio.modelos import (
    CatalogoInstrumento,
    Contexto,
    Intencion,
    ModeloInfo,
    TipoIntencion,
    Transcripcion,
)

_API = "https://generativelanguage.googleapis.com/v1beta"

_INSTRUCCIONES = """\
Sos el intérprete de un sistema que configura instrumental de laboratorio por voz. Recibís la
transcripción de lo que dijo el usuario (español rioplatense, puede tener errores de transcripción)
y devolvés UNA intención en JSON.

Catálogo cerrado de acciones del instrumento "{instrumento}":
{acciones}

Reglas:
- `tipo`:
  - "accion": el pedido corresponde a una acción del catálogo y están todos sus parámetros obligatorios.
  - "consulta": el usuario pregunta el valor actual de algo; `accion` es la acción cuyo valor se
    consulta (solo las marcadas consultable) y `parametros` solo lo necesario para identificarlo (ej. canal).
  - "aclaracion": el pedido es reconocible pero falta un dato; poné en `pregunta` qué falta, breve.
  - "fuera_de_alcance": no corresponde a ninguna acción del catálogo.
- Ante la duda, "aclaracion" o "fuera_de_alcance". NUNCA elijas la acción más parecida.
- `accion` es exactamente uno de los identificadores del catálogo, o null.
- Los valores van en la unidad indicada, en unidades del SI SIN prefijos: "quinientos milivoltios" → 0.5,
  "diez microsegundos" → 0.00001. No incluyas la unidad, solo el número.
- `confianza` entre 0 y 1: qué tan seguro estás de la interpretación.
- Usá el contexto para resolver referencias ("subilo", "el mismo canal") y para completar una
  aclaración pendiente con la respuesta del usuario.
"""


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
            "systemInstruction": {"parts": [{"text": _instrucciones(catalogo)}]},
            "contents": [{"role": "user", "parts": [{"text": _mensaje(transcripcion, contexto)}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _esquema_respuesta(catalogo),
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
        return self._a_intencion(r.json(), transcripcion, catalogo)

    def _cabeceras(self) -> dict[str, str]:
        return {"x-goog-api-key": self._api_key or ""}

    def _a_intencion(self, respuesta: dict, transcripcion: Transcripcion, catalogo: CatalogoInstrumento) -> Intencion:
        try:
            texto = respuesta["candidates"][0]["content"]["parts"][0]["text"]
            datos = json.loads(texto)
            intencion = Intencion(
                tipo=datos["tipo"],
                accion=datos.get("accion"),
                parametros={k: v for k, v in (datos.get("parametros") or {}).items() if v is not None},
                confianza=datos.get("confianza", 0.0),
                pregunta=datos.get("pregunta"),
                enunciado=transcripcion.texto,
                modelo=self._info,
            )
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as e:
            raise RespuestaInvalida(f"Gemini respondió fuera de esquema: {str(respuesta)[:300]}") from e
        inventada = intencion.accion is not None and catalogo.accion(intencion.accion) is None
        if inventada or intencion.tipo == TipoIntencion.FUERA_DE_ALCANCE:
            # Una acción inventada no se aproxima, y un pedido fuera de alcance no arrastra acción.
            return intencion.model_copy(update={"tipo": TipoIntencion.FUERA_DE_ALCANCE, "accion": None, "parametros": {}})
        return intencion


def _instrucciones(catalogo: CatalogoInstrumento) -> str:
    acciones = []
    for herramienta in a_json_schema(catalogo):
        accion = catalogo.accion(herramienta["nombre"])
        acciones.append({
            **herramienta,
            "consultable": accion.verificacion_scpi is not None,
            "sensible": accion.sensible,
            "ejemplos": list(accion.ejemplos),
        })
    return _INSTRUCCIONES.format(
        instrumento=catalogo.instrumento.id, acciones=json.dumps(acciones, ensure_ascii=False, indent=1)
    )


def _mensaje(transcripcion: Transcripcion, contexto: Contexto) -> str:
    ctx = {
        "canal_activo": contexto.canal_activo,
        "ultima_intencion": _resumen(contexto.ultima_intencion),
        "aclaracion_pendiente": _resumen(contexto.aclaracion_pendiente),
    }
    return f"Contexto: {json.dumps(ctx, ensure_ascii=False)}\nTranscripción: {transcripcion.texto}"


def _resumen(intencion: Intencion | None) -> dict | None:
    if intencion is None:
        return None
    return intencion.model_dump(include={"tipo", "accion", "parametros", "pregunta", "enunciado"})


def _esquema_respuesta(catalogo: CatalogoInstrumento) -> dict:
    # Un objeto con propiedades fijas: se declara la unión de los parámetros del catálogo, todos
    # opcionales. Qué corresponde a cada acción lo verifica el validador.
    parametros = {
        p.nombre: {"type": "integer" if p.tipo == "entero" else "number"}
        for a in catalogo.acciones.values() for p in a.parametros
    }
    return {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": [t.value for t in TipoIntencion]},
            "accion": {"type": "string", "enum": list(catalogo.acciones)},
            "parametros": {"type": "object", "properties": parametros},
            "confianza": {"type": "number", "minimum": 0, "maximum": 1},
            "pregunta": {"type": "string"},
        },
        "required": ["tipo", "confianza"],
    }
