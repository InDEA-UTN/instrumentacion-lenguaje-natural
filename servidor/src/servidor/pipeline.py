"""Orquestador de la cascada: grabación → transcripción → intención → validación → ejecución.

Recibe los modelos por sus puertos: no sabe cuál está detrás de cada uno.
"""

import asyncio

from .dominio.errores import InteraccionInexistente
from .dominio.modelos import (
    CatalogoInstrumento,
    ComandoSCPI,
    Contexto,
    EstadoInteraccion,
    Grabacion,
    Interaccion,
    Rechazo,
    TipoIntencion,
    Transcripcion,
)
from .dominio.puertos import Interprete, MotorASR
from .ejecucion import Ejecutor
from .validacion import validar


class ProcesarPedido:
    def __init__(
        self,
        asr: MotorASR,
        interprete: Interprete,
        catalogo: CatalogoInstrumento,
        ejecutor: Ejecutor,
        umbral_confianza: float = 0.7,
    ):
        self.asr = asr
        self.interprete = interprete
        self.catalogo = catalogo
        self._ejecutor = ejecutor
        self._umbral = umbral_confianza
        self._pendientes: dict[str, Interaccion] = {}

    async def procesar(self, grabacion: Grabacion, contexto: Contexto) -> Interaccion:
        transcripcion = await self.asr.transcribir(grabacion)
        return await self.procesar_transcripcion(transcripcion, contexto)

    async def procesar_transcripcion(self, transcripcion: Transcripcion, contexto: Contexto) -> Interaccion:
        intencion = await self.interprete.interpretar(transcripcion, self.catalogo, contexto)
        base = {"transcripcion": transcripcion, "intencion": intencion}

        if intencion.tipo == TipoIntencion.FUERA_DE_ALCANCE:
            return Interaccion(
                **base, estado=EstadoInteraccion.RECHAZADA,
                mensaje="No puedo hacer eso: no está en el catálogo de este instrumento.",
            )
        if intencion.tipo == TipoIntencion.ACLARACION:
            return Interaccion(
                **base, estado=EstadoInteraccion.ACLARACION,
                mensaje=intencion.pregunta or "Me falta un dato para hacer eso.",
            )

        validado = validar(intencion, self.catalogo)
        if isinstance(validado, Rechazo):
            return Interaccion(**base, estado=EstadoInteraccion.RECHAZADA, mensaje=validado.motivo, rechazo=validado)

        if validado.sensible or intencion.confianza < self._umbral:
            pendiente = Interaccion(
                **base, comando=validado, estado=EstadoInteraccion.CONFIRMACION_PENDIENTE,
                mensaje=f"¿Confirmás? {_describir(validado)}",
            )
            self._pendientes[pendiente.id] = pendiente
            return pendiente

        return await self._ejecutar(Interaccion(**base, comando=validado, estado=EstadoInteraccion.EJECUTADA, mensaje=""))

    async def confirmar(self, interaccion_id: str, aceptar: bool) -> Interaccion:
        pendiente = self._pendientes.pop(interaccion_id, None)
        if pendiente is None:
            raise InteraccionInexistente(interaccion_id)
        if not aceptar:
            return pendiente.model_copy(update={"estado": EstadoInteraccion.CANCELADA, "mensaje": "Cancelado."})
        return await self._ejecutar(pendiente)

    async def _ejecutar(self, interaccion: Interaccion) -> Interaccion:
        comando = interaccion.comando
        resultado = await asyncio.to_thread(self._ejecutor.ejecutar, comando)
        consulta = comando.escritura is None
        lectura = f" El instrumento responde: {resultado.lectura}." if resultado.lectura is not None else ""
        return interaccion.model_copy(update={
            "estado": EstadoInteraccion.CONSULTADA if consulta else EstadoInteraccion.EJECUTADA,
            "mensaje": f"{'Consultado' if consulta else 'Hecho'}: {_describir(comando)}.{lectura}",
            "resultado": resultado,
        })


def actualizar_contexto(contexto: Contexto, interaccion: Interaccion) -> Contexto:
    intencion = interaccion.intencion
    if intencion is None:
        return contexto
    canal = intencion.parametros.get("canal", contexto.canal_activo)
    return contexto.model_copy(update={
        "ultima_intencion": intencion,
        "canal_activo": canal if isinstance(canal, int) else contexto.canal_activo,
        "aclaracion_pendiente": intencion if interaccion.estado == EstadoInteraccion.ACLARACION else None,
    })


def _describir(comando: ComandoSCPI) -> str:
    parametros = ", ".join(f"{k} = {v}" for k, v in comando.parametros.items())
    return f"{comando.accion}({parametros})"
