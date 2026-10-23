"""Registro de modelos disponibles. Agregar un modelo = un adaptador nuevo + una línea acá."""

from collections.abc import Callable

from .catalogo import cargar_catalogo
from .config import Configuracion
from .dominio.puertos import Interprete, MotorASR
from .ejecucion import Ejecutor, InstrumentoFake
from .interpretacion.fake import InterpreteFake
from .interpretacion.gemini import Gemini
from .pipeline import ProcesarPedido
from .transcripcion.fake import ASRFake
from .transcripcion.whisper_cpp import WhisperCpp

MOTORES_ASR: dict[str, Callable[[Configuracion], MotorASR]] = {
    "whisper_cpp": lambda c: WhisperCpp(url=c.asr_url, modelo=c.asr_modelo),
    "fake": lambda c: ASRFake(texto=c.asr_fake_texto),
}

INTERPRETES: dict[str, Callable[[Configuracion], Interprete]] = {
    "fake": lambda c: InterpreteFake(),
    "gemini": lambda c: Gemini(api_key=c.gemini_api_key, modelo=c.gemini_modelo),
}


def _elegir[T](registro: dict[str, Callable[[Configuracion], T]], nombre: str, que: str, c: Configuracion) -> T:
    try:
        return registro[nombre](c)
    except KeyError:
        raise ValueError(f"{que} '{nombre}' desconocido. Disponibles: {', '.join(registro)}") from None


def construir_pipeline(c: Configuracion | None = None) -> ProcesarPedido:
    c = c or Configuracion()
    return ProcesarPedido(
        asr=_elegir(MOTORES_ASR, c.asr_motor, "Motor de ASR", c),
        interprete=_elegir(INTERPRETES, c.interprete, "Intérprete", c),
        catalogo=cargar_catalogo(c.catalogo),
        ejecutor=Ejecutor(InstrumentoFake()),  # PyVISA real cuando se cierre D1
        umbral_confianza=c.umbral_confianza,
    )
