from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_SERVIDOR = Path(__file__).resolve().parents[2]
# Junto al código y no bajo RAIZ_SERVIDOR, que fuera del modo editable no apunta a servidor/.
CATALOGOS = Path(__file__).resolve().parent / "catalogos"
PROVEEDORES = Path(__file__).resolve().parent / "proveedores.yaml"


class Configuracion(BaseSettings):
    """Todo se elige por variables de entorno. Las claves de API van solo en servidor/.env, nunca
    en el código: proveedores.yaml nombra la variable de cada una."""

    model_config = SettingsConfigDict(env_file=(RAIZ_SERVIDOR / ".env", ".env"), extra="ignore")

    # Modelos que se usan cuando el pedido no elige: `proveedor/modelo`, `proveedor` (su
    # predeterminado) o un nombre viejo (whisper_cpp, llama_cpp, opencode, gemini, fake).
    # Qué modelos hay, dónde están y con qué clave: proveedores.yaml.
    asr_motor: str = "whisper_cpp"
    interprete: str = "fake"
    proveedores: Path = PROVEEDORES

    catalogo: Path = CATALOGOS / "tektronix_tbs1072b.yaml"

    instrumento: str = "fake"  # ver registro.CONEXIONES; "visa" para el equipo real
    visa_recurso: str | None = None  # None: se busca por USB el modelo del catálogo
    visa_backend: str = "@py"  # pyvisa-py; "ruta.yaml@sim" para pyvisa-sim
    visa_timeout_ms: int = 10_000  # el autoset tarda unos segundos en devolver el control
    visa_al_conectar: list[str] = ["HEADer OFF"]  # en JSON si se define por entorno
    visa_consulta_eventos: str | None = "ALLEv?"  # Tektronix; en otros fabricantes, SYSTem:ERRor?
    umbral_confianza: float = 0.7
