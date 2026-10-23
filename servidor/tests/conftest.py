from pathlib import Path

import pytest

from servidor.catalogo import cargar_catalogo

CATALOGO_DEMO = Path(__file__).resolve().parents[1] / "catalogos" / "osciloscopio_generico_4ch.yaml"


@pytest.fixture
def catalogo():
    return cargar_catalogo(CATALOGO_DEMO)
