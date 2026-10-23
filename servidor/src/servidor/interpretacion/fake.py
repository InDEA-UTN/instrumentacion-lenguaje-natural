import re
import unicodedata

from ..dominio.modelos import (
    CatalogoInstrumento,
    Contexto,
    Intencion,
    ModeloInfo,
    TipoIntencion,
    Transcripcion,
)

# Enunciados del catálogo de prueba con su intención esperada. Lo que no está acá es fuera de alcance.
GUION_DEMO: dict[str, dict] = {
    "poné el canal uno en quinientos milivoltios por división": {
        "tipo": "accion", "accion": "configurar_escala_vertical", "parametros": {"canal": 1, "valor": 0.5},
    },
    "canal 1 a 50 milivolt": {
        "tipo": "accion", "accion": "configurar_escala_vertical", "parametros": {"canal": 1, "valor": 0.05},
    },
    "poné la base de tiempo en un milisegundo": {
        "tipo": "accion", "accion": "configurar_base_tiempo", "parametros": {"valor": 0.001},
    },
    "en cuánto está la escala del canal dos": {
        "tipo": "consulta", "accion": "configurar_escala_vertical", "parametros": {"canal": 2},
    },
    "subí la escala": {
        "tipo": "aclaracion", "accion": "configurar_escala_vertical", "pregunta": "¿De qué canal?",
    },
    "reiniciá el osciloscopio": {"tipo": "accion", "accion": "reiniciar_instrumento"},
}


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", sin_tildes.lower())).strip()


class InterpreteFake:
    """Busca el enunciado en un guion fijo. Sustituto del modelo de lenguaje mientras D3 esté abierta."""

    def __init__(self, guion: dict[str, dict] | None = None):
        self._guion = {normalizar(k): v for k, v in (guion if guion is not None else GUION_DEMO).items()}
        self._info = ModeloInfo(nombre="interprete-fake", proveedor="local", version="0", ubicacion="local")

    def info(self) -> ModeloInfo:
        return self._info

    async def salud(self) -> bool:
        return True

    async def interpretar(
        self, transcripcion: Transcripcion, catalogo: CatalogoInstrumento, contexto: Contexto
    ) -> Intencion:
        entrada = self._guion.get(normalizar(transcripcion.texto))
        if entrada is None or (entrada.get("accion") and catalogo.accion(entrada["accion"]) is None):
            entrada = {"tipo": TipoIntencion.FUERA_DE_ALCANCE}
        return Intencion(**entrada, confianza=1.0, enunciado=transcripcion.texto, modelo=self._info)
