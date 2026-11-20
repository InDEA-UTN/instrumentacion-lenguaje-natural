"""Registro de modelos: lee proveedores.yaml y arma el adaptador de cada modelo cuando se pide.

Separa tres cosas (docs/modelo_dominio.md, sección 4):
- el **protocolo**, cómo se le habla a una API: un adaptador de código por protocolo;
- el **proveedor**, dónde está la API (URL, clave, cabeceras): declarado en el YAML;
- el **modelo**, un modelo concreto de un proveedor para una etapa: declarado en el YAML.

Sumar un modelo o un proveedor que hable un protocolo conocido es editar el YAML. Solo un protocolo
nuevo lleva código: un adaptador y una línea en PROTOCOLOS_ASR o PROTOCOLOS_INTERPRETE.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from .clientes import ClienteHTTP
from .dominio.errores import ErrorDominio
from .dominio.modelos import ModeloInfo
from .dominio.puertos import Interprete, MotorASR
from .interpretacion.chat import Chat
from .interpretacion.fake import InterpreteFake
from .interpretacion.gemini import Gemini
from .transcripcion.chat_audio import ChatAudio
from .transcripcion.fake import ASRFake
from .transcripcion.transcripciones import Transcripciones
from .transcripcion.whisper_cpp import WhisperCpp

Etapa = Literal["asr", "interprete"]
ETAPAS: tuple[Etapa, ...] = ("asr", "interprete")
_SALUD_VIGENTE_S = 30.0  # cuánto se reutiliza la consulta de salud de un modelo


class ProveedoresInvalidos(ErrorDominio):
    """proveedores.yaml está mal formado."""


class ModeloDesconocido(ErrorDominio):
    """Se pidió un modelo que no está declarado (o no es de esa etapa)."""


# ---------------------------------------------------------------------------
# Declaración (lo que dice el YAML)
# ---------------------------------------------------------------------------


class _Decl(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DeclModelo(_Decl):
    etapa: Etapa
    protocolo: str
    url: str | None = None
    salud_url: str | None = None
    timeout_s: float | None = None
    parametros: dict = {}
    esquema_estricto: bool | None = None


class DeclProveedor(_Decl):
    nombre: str
    ubicacion: Literal["local", "nube"] = "nube"
    url: str | None = None
    clave: str | None = None  # NOMBRE de la variable de entorno, nunca la clave
    cabeceras: dict[str, str] = {}
    cabecera_sesion: str | None = None
    timeout_s: float = 30.0
    modelos_url: str | None = None
    salud_url: str | None = None
    esquema_estricto: bool = False
    parametros: dict[Etapa, dict] = {}
    predeterminados: dict[Etapa, str] = {}
    oculto: bool = False
    modelos: dict[str, DeclModelo]

    @model_validator(mode="after")
    def _coherente(self) -> DeclProveedor:
        for etapa, modelo in self.predeterminados.items():
            if modelo not in self.modelos or self.modelos[modelo].etapa != etapa:
                raise ValueError(f"el predeterminado de {etapa} ('{modelo}') no es un modelo de {etapa} declarado")
        for nombre, m in self.modelos.items():
            protocolos = PROTOCOLOS_ASR if m.etapa == "asr" else PROTOCOLOS_INTERPRETE
            if m.protocolo not in protocolos:
                raise ValueError(f"'{nombre}': protocolo '{m.protocolo}' desconocido para {m.etapa}. "
                                 f"Disponibles: {', '.join(protocolos)}")
        return self


# ---------------------------------------------------------------------------
# Protocolos: de la declaración al adaptador
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Armado:
    """Lo que un protocolo necesita para armar su adaptador: la declaración resuelta de un modelo."""

    proveedor_id: str
    proveedor: DeclProveedor
    modelo: str
    decl: DeclModelo
    entorno: Mapping[str, str]

    @property
    def info(self) -> ModeloInfo:
        return ModeloInfo(nombre=self.modelo, proveedor=self.proveedor_id, version=self.modelo,
                          ubicacion=self.proveedor.ubicacion)

    @property
    def url(self) -> str:
        url = self.decl.url or self.proveedor.url
        if not url:
            raise ProveedoresInvalidos(f"{self.proveedor_id}/{self.modelo}: no tiene `url`")
        return url

    @property
    def api_key(self) -> str | None:
        return self.entorno.get(self.proveedor.clave) or None if self.proveedor.clave else None

    @property
    def timeout_s(self) -> float:
        return self.decl.timeout_s or self.proveedor.timeout_s

    @property
    def parametros(self) -> dict:
        return {**self.proveedor.parametros.get(self.decl.etapa, {}), **self.decl.parametros}

    def cliente(self) -> ClienteHTTP:
        p = self.proveedor
        return ClienteHTTP(
            url=self.url, etiqueta=p.nombre, api_key=self.api_key, nombre_clave=p.clave,
            cabeceras=p.cabeceras, cabecera_sesion=p.cabecera_sesion, timeout_s=self.timeout_s,
            modelos_url=None if self.decl.salud_url else p.modelos_url,
            salud_url=self.decl.salud_url or p.salud_url,
        )


PROTOCOLOS_INTERPRETE: dict[str, Callable[[Armado], Interprete]] = {
    "chat": lambda c: Chat(
        c.cliente(), c.modelo, c.info, c.parametros,
        esquema_estricto=c.decl.esquema_estricto if c.decl.esquema_estricto is not None
        else c.proveedor.esquema_estricto,
    ),
    "gemini": lambda c: Gemini(api_key=c.api_key, modelo=c.modelo, info=c.info),
    "fake": lambda c: InterpreteFake(),
}

PROTOCOLOS_ASR: dict[str, Callable[[Armado], MotorASR]] = {
    "whisper_cpp": lambda c: WhisperCpp(url=c.url, modelo=c.modelo, timeout_s=c.timeout_s, info=c.info),
    "chat_audio": lambda c: ChatAudio(c.cliente(), c.modelo, c.info, parametros=c.parametros),
    "transcripciones": lambda c: Transcripciones(c.cliente(), c.modelo, c.info, parametros=c.parametros),
    "fake": lambda c: ASRFake(**({"texto": c.entorno["ASR_FAKE_TEXTO"]} if "ASR_FAKE_TEXTO" in c.entorno else {})),
}

# Nombres de antes del registro (ASR_MOTOR=whisper_cpp, INTERPRETE=llama_cpp...): siguen andando y
# eligen el predeterminado de ese proveedor.
ALIAS = {"whisper_cpp": "local", "llama_cpp": "local", "opencode": "opencode-go", "gemini": "google",
         "fake": "prueba"}


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------


@dataclass
class _Salud:
    listo: bool
    motivo: str | None
    cuando: float


class RegistroModelos:
    def __init__(self, ruta: str | Path, entorno: Mapping[str, str] | None = None):
        """entorno: de dónde salen las claves y las ${VARIABLES} del YAML (por defecto, servidor/.env
        más las variables de entorno, que tienen prioridad)."""
        self._entorno = dict(entorno if entorno is not None else entorno_completo())
        self.proveedores = cargar_proveedores(ruta, self._entorno)
        self._adaptadores: dict[str, MotorASR | Interprete] = {}
        self._salud: dict[str, _Salud] = {}

    # -- Resolución -----------------------------------------------------------------------------

    def resolver(self, etapa: Etapa, nombre: str) -> str:
        """`proveedor/modelo`, `proveedor` (su predeterminado) o un alias viejo → `proveedor/modelo`."""
        nombre = ALIAS.get(nombre, nombre)
        proveedor_id, _, modelo = nombre.partition("/")
        proveedor = self.proveedores.get(proveedor_id)
        if proveedor is None:
            raise ModeloDesconocido(f"Proveedor '{proveedor_id}' desconocido. Disponibles: {', '.join(self.proveedores)}")
        if not modelo:
            modelo = proveedor.predeterminados.get(etapa)
            if modelo is None:
                raise ModeloDesconocido(f"{proveedor.nombre} no tiene un modelo de {etapa} predeterminado")
        decl = proveedor.modelos.get(modelo)
        if decl is None or decl.etapa != etapa:
            raise ModeloDesconocido(f"'{proveedor_id}/{modelo}' no es un modelo de {etapa} declarado en proveedores.yaml")
        return f"{proveedor_id}/{modelo}"

    def asr(self, nombre: str) -> MotorASR:
        return self._adaptador("asr", nombre)

    def interprete(self, nombre: str) -> Interprete:
        return self._adaptador("interprete", nombre)

    def _adaptador(self, etapa: Etapa, nombre: str):
        id = self.resolver(etapa, nombre)
        if id not in self._adaptadores:
            ctx = self._contexto(id)
            protocolos = PROTOCOLOS_ASR if etapa == "asr" else PROTOCOLOS_INTERPRETE
            self._adaptadores[id] = protocolos[ctx.decl.protocolo](ctx)
        return self._adaptadores[id]

    def _contexto(self, id: str) -> Armado:
        proveedor_id, _, modelo = id.partition("/")
        proveedor = self.proveedores[proveedor_id]
        return Armado(proveedor_id, proveedor, modelo, proveedor.modelos[modelo], self._entorno)

    def ids(self, etapa: Etapa, visibles: bool = True) -> list[str]:
        return [
            f"{pid}/{m}" for pid, p in self.proveedores.items() if not (visibles and p.oculto)
            for m, d in p.modelos.items() if d.etapa == etapa
        ]

    # -- Disponibilidad -------------------------------------------------------------------------

    async def salud(self, id: str, refrescar: bool = False) -> _Salud:
        guardada = self._salud.get(id)
        if guardada and not refrescar and time.monotonic() - guardada.cuando < _SALUD_VIGENTE_S:
            return guardada
        ctx = self._contexto(id)
        if ctx.proveedor.clave and not ctx.api_key:
            salud = _Salud(False, f"Falta {ctx.proveedor.clave} en servidor/.env", time.monotonic())
        else:
            adaptador = self._adaptador(ctx.decl.etapa, id)
            listo = await adaptador.salud()
            salud = _Salud(listo, None if listo else "No responde", time.monotonic())
        self._salud[id] = salud
        return salud

    async def listado(self, predeterminados: dict[Etapa, str], refrescar: bool = False) -> dict:
        """Lo que muestra el front: por etapa, los proveedores visibles con sus modelos y su estado."""
        ids = [i for etapa in ETAPAS for i in self.ids(etapa)]
        saludes = dict(zip(ids, await asyncio.gather(*(self.salud(i, refrescar) for i in ids))))
        respuesta = {}
        for etapa in ETAPAS:
            proveedores = []
            for pid, p in self.proveedores.items():
                if p.oculto:
                    continue
                modelos = [
                    {"id": f"{pid}/{m}", "nombre": m, "listo": saludes[f"{pid}/{m}"].listo,
                     "motivo": saludes[f"{pid}/{m}"].motivo}
                    for m, d in p.modelos.items() if d.etapa == etapa
                ]
                if not modelos:
                    continue
                predeterminado = p.predeterminados.get(etapa)
                proveedores.append({
                    "id": pid, "nombre": p.nombre, "ubicacion": p.ubicacion,
                    "predeterminado": f"{pid}/{predeterminado}" if predeterminado else modelos[0]["id"],
                    "listo": any(m["listo"] for m in modelos),
                    "modelos": modelos,
                })
            respuesta[etapa] = {"predeterminado": predeterminados[etapa], "proveedores": proveedores}
        return respuesta


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

_VARIABLE = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


def cargar_proveedores(ruta: str | Path, entorno: Mapping[str, str]) -> dict[str, DeclProveedor]:
    texto = _VARIABLE.sub(lambda m: entorno.get(m[1]) or (m[2] or ""), Path(ruta).read_text(encoding="utf-8"))
    try:
        datos = yaml.safe_load(texto)["proveedores"]
        proveedores = {pid: DeclProveedor(**decl) for pid, decl in datos.items()}
    except (KeyError, TypeError, ValidationError) as e:
        raise ProveedoresInvalidos(f"{ruta}: {e}") from e
    if malos := [pid for pid in proveedores if "/" in pid]:
        raise ProveedoresInvalidos(f"{ruta}: el id de un proveedor no puede tener '/': {malos}")
    return proveedores


def entorno_completo() -> dict[str, str]:
    """servidor/.env (si existe) y las variables de entorno, que tienen prioridad. Con Docker, las
    claves ya llegan como variables (env_file del docker-compose)."""
    from dotenv import dotenv_values

    from .config import RAIZ_SERVIDOR

    archivo = {k: v for k, v in dotenv_values(RAIZ_SERVIDOR / ".env").items() if v is not None}
    return {**archivo, **os.environ}
