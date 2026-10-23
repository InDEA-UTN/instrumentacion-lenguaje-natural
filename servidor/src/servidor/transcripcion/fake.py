from ..dominio.modelos import Grabacion, ModeloInfo, Transcripcion


class ASRFake:
    """Devuelve siempre el mismo texto. Para tests y para probar la cascada sin whisper."""

    def __init__(self, texto: str = "poné el canal uno en quinientos milivoltios por división"):
        self.texto = texto
        self._info = ModeloInfo(nombre="asr-fake", proveedor="local", version="0", ubicacion="local")

    def info(self) -> ModeloInfo:
        return self._info

    async def salud(self) -> bool:
        return True

    async def transcribir(self, grabacion: Grabacion) -> Transcripcion:
        return Transcripcion(texto=self.texto, idioma="es", latencia_s=0.0, modelo=self._info)
