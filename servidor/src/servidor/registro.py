"""Registro de modelos disponibles. Agregar un modelo = un adaptador nuevo + una línea acá."""

from collections.abc import Callable

from .catalogo import cargar_catalogo
from .config import Configuracion
from .dominio.modelos import CatalogoInstrumento
from .dominio.puertos import ConexionInstrumento, Interprete, MotorASR
from .ejecucion import ConexionVisa, Ejecutor, InstrumentoFake
from .interpretacion.fake import InterpreteFake
from .interpretacion.gemini import Gemini
from .interpretacion.llama_cpp import LlamaCpp
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
    "llama_cpp": lambda c: LlamaCpp(url=c.llm_url, modelo=c.llm_modelo, timeout_s=c.llm_timeout_s),
}


CONEXIONES: dict[str, Callable[[Configuracion, CatalogoInstrumento], ConexionInstrumento]] = {
    "fake": lambda c, cat: InstrumentoFake(),
    "visa": lambda c, cat: ConexionVisa(
        modelo=cat.instrumento.modelo,
        recurso=c.visa_recurso or cat.instrumento.recurso_visa,
        backend=c.visa_backend,
        timeout_ms=c.visa_timeout_ms,
        al_conectar=c.visa_al_conectar,
        consulta_eventos=c.visa_consulta_eventos,
    ),
}


def _elegir[T](registro: dict[str, Callable[..., T]], nombre: str, que: str, *args) -> T:
    try:
        return registro[nombre](*args)
    except KeyError:
        raise ValueError(f"{que} '{nombre}' desconocido. Disponibles: {', '.join(registro)}") from None


def construir_pipeline(c: Configuracion | None = None) -> ProcesarPedido:
    c = c or Configuracion()
    catalogo = cargar_catalogo(c.catalogo)
    return ProcesarPedido(
        asr=_elegir(MOTORES_ASR, c.asr_motor, "Motor de ASR", c),
        interprete=_elegir(INTERPRETES, c.interprete, "Intérprete", c),
        catalogo=catalogo,
        ejecutor=Ejecutor(_elegir(CONEXIONES, c.instrumento, "Instrumento", c, catalogo)),
        umbral_confianza=c.umbral_confianza,
    )
