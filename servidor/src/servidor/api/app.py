"""Interfaz HTTP con la aplicación de captura (PWA)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import asyncio

from ..dominio.errores import (
    InstrumentoNoDisponible,
    InteraccionInexistente,
    ModeloNoDisponible,
    RespuestaInvalida,
)
from ..dominio.modelos import Contexto, EstadoInteraccion, Grabacion, Interaccion
from ..config import Configuracion
from ..pipeline import actualizar_contexto
from ..proveedores import ModeloDesconocido, RegistroModelos
from ..registro import construir_pipeline

# Contexto por sesión, en memoria. Alcanza para un prototipo con un solo servidor.
_contextos: dict[str, Contexto] = {}
# A qué sesión pertenece cada confirmación pendiente, para actualizar su contexto al resolverla.
_sesion_de_pendiente: dict[str, str] = {}


@asynccontextmanager
async def _ciclo_de_vida(app: FastAPI):
    c = Configuracion()
    app.state.registro = RegistroModelos(c.proveedores)
    app.state.pipeline = construir_pipeline(c, app.state.registro)
    app.state.predeterminados = {
        "asr": app.state.registro.resolver("asr", c.asr_motor),
        "interprete": app.state.registro.resolver("interprete", c.interprete),
    }
    yield
    if cerrar := getattr(app.state.pipeline.ejecutor.conexion, "cerrar", None):
        cerrar()


app = FastAPI(title="Instrumentación por lenguaje natural", lifespan=_ciclo_de_vida)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/salud")
async def salud():
    p = app.state.pipeline
    return {
        "asr": {**p.asr.info().model_dump(), "listo": await p.asr.salud()},
        "interprete": {**p.interprete.info().model_dump(), "listo": await p.interprete.salud()},
        "instrumento": {
            **p.catalogo.instrumento.model_dump(),
            "conexion": type(p.ejecutor.conexion).__name__,
            "listo": await asyncio.to_thread(p.ejecutor.conexion.salud),
            "idn_conectado": getattr(p.ejecutor.conexion, "idn", None),
        },
    }


@app.get("/modelos")
async def modelos(refrescar: bool = False):
    """Por etapa, los proveedores con sus modelos y si están disponibles. Lo usa el selector del front.
    La disponibilidad se reutiliza 30 s; `refrescar=true` la vuelve a consultar."""
    return await app.state.registro.listado(app.state.predeterminados, refrescar)


@app.post("/pedidos", response_model=Interaccion)
async def crear_pedido(
    audio: UploadFile,
    sesion: str = Form("default"),
    asr: str | None = Form(None),  # `proveedor/modelo` de GET /modelos; si no, el predeterminado
    interprete: str | None = Form(None),
) -> Interaccion:
    # Solo se aceptan modelos declarados en proveedores.yaml: el front elige, nunca dice a dónde ir.
    registro = app.state.registro
    try:
        motor_asr = registro.asr(asr) if asr else None
        motor_interprete = registro.interprete(interprete) if interprete else None
    except ModeloDesconocido as e:
        raise HTTPException(422, str(e)) from e
    grabacion = Grabacion(
        contenido=await audio.read(),
        nombre=audio.filename or "audio.wav",
        formato=(audio.filename or "audio.wav").rsplit(".", 1)[-1],
    )
    contexto = _contextos.get(sesion, Contexto())
    try:
        interaccion = await app.state.pipeline.procesar(grabacion, contexto, motor_asr, motor_interprete)
    except (ModeloNoDisponible, InstrumentoNoDisponible) as e:
        raise HTTPException(503, str(e)) from e
    except RespuestaInvalida as e:
        raise HTTPException(502, str(e)) from e
    _contextos[sesion] = actualizar_contexto(contexto, interaccion)
    if interaccion.estado == EstadoInteraccion.CONFIRMACION_PENDIENTE:
        _sesion_de_pendiente[interaccion.id] = sesion
    return interaccion


class Confirmacion(BaseModel):
    aceptar: bool


@app.post("/confirmaciones/{interaccion_id}", response_model=Interaccion)
async def confirmar(interaccion_id: str, confirmacion: Confirmacion) -> Interaccion:
    try:
        interaccion = await app.state.pipeline.confirmar(interaccion_id, confirmacion.aceptar)
    except InteraccionInexistente as e:
        raise HTTPException(404, f"No hay confirmación pendiente con id {interaccion_id}") from e
    except InstrumentoNoDisponible as e:
        # La confirmación ya se consumió: el usuario tiene que repetir el pedido.
        _sesion_de_pendiente.pop(interaccion_id, None)
        raise HTTPException(503, f"{e} Repetí el pedido cuando el instrumento esté disponible.") from e
    if (sesion := _sesion_de_pendiente.pop(interaccion_id, None)) is not None:
        _contextos[sesion] = actualizar_contexto(_contextos.get(sesion, Contexto()), interaccion)
    return interaccion
