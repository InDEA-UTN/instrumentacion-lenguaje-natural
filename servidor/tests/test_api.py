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


def test_salud_del_instrumento_simulado(cliente):
    r = cliente.get("/salud/instrumento").json()
    assert r["id"] == "tektronix_tbs1072b" and r["modelo"] == "TBS1072B"
    assert r["conexion"] == "InstrumentoFake" and r["listo"] is True


def test_salud_del_instrumento_por_visa(cliente):
    # El simulador del TBS1072B: la API informa con qué equipo habló, y deja de hacerlo al perderlo.
    pytest.importorskip("pyvisa_sim")
    import servidor
    from servidor.ejecucion import ConexionVisa

    conexion = ConexionVisa(modelo="TBS1072B", backend=f"{servidor.__path__[0]}/simuladores/tektronix_tbs1072b.yaml@sim")
    cliente.app.state.pipeline.ejecutor.conexion = conexion
    try:
        r = cliente.get("/salud/instrumento").json()
        assert r["conexion"] == "ConexionVisa" and r["listo"] is True
        assert r["idn_conectado"].startswith("TEKTRONIX,TBS1072B,C010001")
        assert "C010001" in r["recurso_conectado"]

        conexion.salud = lambda: False  # como si lo desenchufaran
        r = cliente.get("/salud/instrumento").json()
        assert r["listo"] is False and r["idn_conectado"] is None and r["recurso_conectado"] is None
    finally:
        conexion.cerrar()


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


def test_modelos_por_etapa_y_proveedor(cliente, monkeypatch):
    from servidor.proveedores import _Salud

    async def todo_listo(self, id_, refrescar=False):
        return _Salud(True, None, 0.0)

    monkeypatch.setattr(type(cliente.app.state.registro), "salud", todo_listo)
    r = cliente.get("/modelos").json()
    for etapa in ("asr", "interprete"):
        assert r[etapa]["predeterminado"].startswith("prueba/")  # ASR_MOTOR / INTERPRETE del fixture
        assert [p["id"] for p in r[etapa]["proveedores"]] == ["local", "opencode-go", "openrouter"]
        assert all(m["id"].startswith(p["id"] + "/") for p in r[etapa]["proveedores"] for m in p["modelos"])


def test_pedido_elige_el_modelo(cliente):
    r = cliente.post("/pedidos", files={"audio": ("a.wav", b"", "audio/wav")},
                     data={"sesion": "s", "asr": "prueba/fake-asr", "interprete": "prueba/fake"})
    assert r.status_code == 200 and r.json()["estado"] == "ejecutada"


@pytest.mark.parametrize("campo, valor", [("interprete", "nadie/modelo"), ("asr", "opencode-go/glm-5.3-flash"),
                                          ("interprete", "http://evil/v1")])
def test_pedido_con_un_modelo_no_declarado(cliente, campo, valor):
    r = cliente.post("/pedidos", files={"audio": ("a.wav", b"", "audio/wav")}, data={"sesion": "s", campo: valor})
    assert r.status_code == 422


def test_modelo_caido_dice_que_etapa_cambiar(cliente):
    from servidor.dominio.errores import ModeloNoDisponible
    from servidor.interpretacion.fake import InterpreteFake

    class Caido(InterpreteFake):
        async def interpretar(self, *a):
            raise ModeloNoDisponible("glm (OpenRouter) respondió 402: sin crédito")

    cliente.app.state.pipeline.interprete = Caido()
    r = cliente.post("/pedidos", files={"audio": ("a.wav", b"", "audio/wav")}, data={"sesion": "s"})
    assert r.status_code == 503
    assert r.json()["detail"].startswith("Intérprete (local): glm (OpenRouter) respondió 402")
