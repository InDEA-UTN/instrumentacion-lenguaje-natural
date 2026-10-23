"""Interfaz HTTP con la aplicación de captura (PWA)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..dominio.errores import InteraccionInexistente, ModeloNoDisponible, RespuestaInvalida
from ..dominio.modelos import Contexto, Grabacion, Interaccion
from ..pipeline import actualizar_contexto
from ..registro import construir_pipeline

# Contexto por sesión, en memoria. Alcanza para un prototipo con un solo servidor.
_contextos: dict[str, Contexto] = {}


@asynccontextmanager
async def _ciclo_de_vida(app: FastAPI):
    app.state.pipeline = construir_pipeline()
    yield


app = FastAPI(title="Instrumentación por lenguaje natural", lifespan=_ciclo_de_vida)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/salud")
async def salud():
    p = app.state.pipeline
    return {
        "asr": {**p.asr.info().model_dump(), "listo": await p.asr.salud()},
        "interprete": {**p.interprete.info().model_dump(), "listo": await p.interprete.salud()},
        "instrumento": p.catalogo.instrumento.model_dump(),
    }


@app.post("/pedidos", response_model=Interaccion)
async def crear_pedido(audio: UploadFile, sesion: str = Form("default")) -> Interaccion:
    grabacion = Grabacion(
        contenido=await audio.read(),
        nombre=audio.filename or "audio.wav",
        formato=(audio.filename or "audio.wav").rsplit(".", 1)[-1],
    )
    contexto = _contextos.get(sesion, Contexto())
    try:
        interaccion = await app.state.pipeline.procesar(grabacion, contexto)
    except ModeloNoDisponible as e:
        raise HTTPException(503, str(e)) from e
    except RespuestaInvalida as e:
        raise HTTPException(502, str(e)) from e
    _contextos[sesion] = actualizar_contexto(contexto, interaccion)
    return interaccion


class Confirmacion(BaseModel):
    aceptar: bool


@app.post("/confirmaciones/{interaccion_id}", response_model=Interaccion)
async def confirmar(interaccion_id: str, confirmacion: Confirmacion) -> Interaccion:
    try:
        return await app.state.pipeline.confirmar(interaccion_id, confirmacion.aceptar)
    except InteraccionInexistente as e:
        raise HTTPException(404, f"No hay confirmación pendiente con id {interaccion_id}") from e
