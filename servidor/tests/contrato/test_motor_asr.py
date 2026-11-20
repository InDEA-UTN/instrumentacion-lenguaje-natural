"""Contrato del puerto MotorASR. Todo motor nuevo se agrega a IMPLEMENTACIONES y tiene que pasarlo."""

from pathlib import Path

import pytest

from servidor.config import Configuracion
from servidor.dominio.modelos import Grabacion, ModeloInfo, Transcripcion
from servidor.dominio.puertos import MotorASR
from servidor.proveedores import RegistroModelos

AUDIO_EJEMPLOS = Path(__file__).resolve().parents[3] / "modelos" / "audio_ejemplos"

# Todos los motores declarados en proveedores.yaml (ver test_interprete.py).
_REGISTRO = RegistroModelos(Configuracion().proveedores)
IMPLEMENTACIONES = [
    pytest.param(id_, id=id_, marks=() if id_.startswith("prueba/") else pytest.mark.integracion)
    for id_ in _REGISTRO.ids("asr", visibles=False)
]


@pytest.fixture(params=IMPLEMENTACIONES)
async def motor(request) -> MotorASR:
    motor = _REGISTRO.asr(request.param)
    if not await motor.salud():
        pytest.skip(f"{motor.info().nombre} no está disponible")
    return motor


@pytest.fixture
def grabacion() -> Grabacion:
    wavs = sorted(AUDIO_EJEMPLOS.glob("*.wav"))
    if not wavs:
        pytest.skip("No hay audios en modelos/audio_ejemplos/")
    return Grabacion(contenido=wavs[0].read_bytes(), nombre=wavs[0].name)


def test_cumple_el_protocolo(motor):
    assert isinstance(motor, MotorASR)
    assert isinstance(motor.info(), ModeloInfo)


async def test_transcribe_y_se_identifica(motor, grabacion):
    t = await motor.transcribir(grabacion)
    assert isinstance(t, Transcripcion)
    assert t.texto.strip()
    assert t.modelo == motor.info()
    assert t.latencia_s >= 0
