"""Lo que comparten los intérpretes basados en un modelo de lenguaje: instrucciones, mensaje,
esquema de respuesta y conversión a Intencion.

Todos los modelos reciben exactamente el mismo prompt y el mismo esquema, para que la comparación
entre ellos mida el modelo y no la redacción de las instrucciones.
"""

import json

from pydantic import ValidationError

from ..catalogo import a_json_schema
from ..dominio.errores import RespuestaInvalida
from ..dominio.modelos import (
    CatalogoInstrumento,
    Contexto,
    Intencion,
    ModeloInfo,
    TipoIntencion,
    Transcripcion,
)

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


def instrucciones(catalogo: CatalogoInstrumento) -> str:
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


def mensaje(transcripcion: Transcripcion, contexto: Contexto) -> str:
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


def esquema_respuesta(catalogo: CatalogoInstrumento) -> dict:
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


def a_intencion(
    texto: str, transcripcion: Transcripcion, catalogo: CatalogoInstrumento, modelo: ModeloInfo
) -> Intencion:
    """Convierte el JSON que devolvió el modelo en una Intencion, o lanza RespuestaInvalida."""
    try:
        datos = json.loads(texto)
        intencion = Intencion(
            tipo=datos["tipo"],
            accion=datos.get("accion"),
            parametros={k: v for k, v in (datos.get("parametros") or {}).items() if v is not None},
            confianza=datos.get("confianza", 0.0),
            pregunta=datos.get("pregunta"),
            enunciado=transcripcion.texto,
            modelo=modelo,
        )
    except (KeyError, TypeError, ValueError, ValidationError) as e:
        raise RespuestaInvalida(f"{modelo.nombre} respondió fuera de esquema: {texto[:300]}") from e
    inventada = intencion.accion is not None and catalogo.accion(intencion.accion) is None
    if inventada or intencion.tipo == TipoIntencion.FUERA_DE_ALCANCE:
        # Una acción inventada no se aproxima, y un pedido fuera de alcance no arrastra acción.
        return intencion.model_copy(update={"tipo": TipoIntencion.FUERA_DE_ALCANCE, "accion": None, "parametros": {}})
    return intencion
