from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_RAIZ_SERVIDOR = Path(__file__).resolve().parents[2]


class Configuracion(BaseSettings):
    """Todo se elige por variables de entorno. Las claves de API van solo acá, nunca en el código."""

    model_config = SettingsConfigDict(env_file=(_RAIZ_SERVIDOR / ".env", ".env"), extra="ignore")

    asr_motor: str = "whisper_cpp"  # ver registro.MOTORES_ASR
    asr_url: str = "http://localhost:8080"
    asr_modelo: str = "ggml-small"
    asr_fake_texto: str = "poné el canal uno en quinientos milivoltios por división"

    interprete: str = "fake"  # ver registro.INTERPRETES
    gemini_api_key: str | None = None
    gemini_modelo: str = "gemini-3.8-flash"
    llm_url: str = "http://localhost:8081"  # llama-server (servicio `llm` del docker-compose)
    llm_modelo: str = "qwen3.5-4b-q4_k_m"  # solo identifica el modelo; el archivo lo elige el servicio
    llm_timeout_s: float = 60.0  # el primer pedido procesa el prompt entero y en CPU tarda

    catalogo: Path = _RAIZ_SERVIDOR / "catalogos" / "osciloscopio_generico_4ch.yaml"
    umbral_confianza: float = 0.7
