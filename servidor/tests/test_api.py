"""La API de punta a punta con los fakes: sin whisper, sin modelo de lenguaje y sin instrumento."""

import pytest
from fastapi.testclient import TestClient

from servidor.api import app as modulo
from servidor.transcripcion.fake import ASRFake


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("ASR_MOTOR", "fake")
    monkeypatch.setenv("INTERPRETE", "fake")
    monkeypatch.setattr(modulo, "_contextos", {})
    monkeypatch.setattr(modulo, "_sesion_de_pendiente", {})
    with TestClient(modulo.app) as c:
        yield c


def _decir(cliente, texto, sesion="s1"):
    cliente.app.state.pipeline.asr = ASRFake(texto)
    r = cliente.post("/pedidos", files={"audio": ("a.wav", b"", "audio/wav")}, data={"sesion": sesion})
    assert r.status_code == 200
    return r.json()


def test_salud(cliente):
    r = cliente.get("/salud").json()
    assert r["asr"]["listo"] and r["interprete"]["listo"]
    assert r["instrumento"]["id"] == "tektronix_tbs1072b"


def test_confirmar_actualiza_el_contexto_de_la_sesion(cliente):
    pendiente = _decir(cliente, "hacé un autoset")
    assert pendiente["estado"] == "confirmacion_pendiente"
    assert "s1" not in modulo._contextos or modulo._contextos["s1"].ultima_intencion is None

    r = cliente.post(f"/confirmaciones/{pendiente['id']}", json={"aceptar": True})
    assert r.status_code == 200 and r.json()["estado"] == "ejecutada"
    assert modulo._contextos["s1"].ultima_intencion.accion == "autoescala"
    assert modulo._sesion_de_pendiente == {}


def test_confirmacion_inexistente(cliente):
    r = cliente.post("/confirmaciones/no-existe", json={"aceptar": True})
    assert r.status_code == 404


def test_las_sesiones_no_se_mezclan(cliente):
    _decir(cliente, "poné el canal uno en quinientos milivoltios por división", sesion="a")
    _decir(cliente, "en cuánto está la escala del canal dos", sesion="b")
    assert modulo._contextos["a"].canal_activo == 1
    assert modulo._contextos["b"].canal_activo == 2
