import pytest

from servidor.catalogo import cargar_catalogo
from servidor.config import CATALOGOS

CATALOGO_DEMO = CATALOGOS / "osciloscopio_generico_4ch.yaml"


@pytest.fixture
def catalogo():
    return cargar_catalogo(CATALOGO_DEMO)
