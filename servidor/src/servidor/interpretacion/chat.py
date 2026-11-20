"""Intérprete por chat completions (protocolo `chat`): cualquier API compatible con la de OpenAI.

Lo usan llama.cpp local, OpenCode Go y OpenRouter; qué proveedor y qué modelo lo decide
proveedores.yaml. Todos reciben el mismo prompt y el mismo esquema (`comun.py`), así que la
comparación entre modelos mide el modelo y no la redacción.

El esquema va como salida estructurada (`response_format`). llama.cpp lo convierte en una
gramática; los proveedores en la nube lo aplican si el modelo lo admite. Si un modelo lo rechaza,
se reintenta sin él: las instrucciones ya piden JSON y la respuesta pasa igual por `a_intencion`,
que rechaza lo que no cumpla el esquema.
"""

import logging
import re

from ..clientes import ClienteHTTP, RechazoDelProveedor
from ..dominio.modelos import CatalogoInstrumento, Contexto, Intencion, ModeloInfo, Transcripcion
from .comun import a_intencion, esquema_respuesta, instrucciones, mensaje

log = logging.getLogger(__name__)

# Códigos con los que un proveedor rechaza un parámetro que no admite.
_PARAMETRO_NO_ADMITIDO = (400, 422)


class Chat:
    def __init__(
        self,
        cliente: ClienteHTTP,
        modelo: str,
        info: ModeloInfo,
        parametros: dict | None = None,
        esquema_estricto: bool = False,
    ):
        """
        modelo: el nombre que se le manda a la API (`model`).
        parametros: campos extra del pedido (ej. {"reasoning_effort": "low"}). Pisan a los de acá,
            salvo `messages`.
        esquema_estricto: pide `strict: true` (OpenRouter lo necesita para hacer cumplir el esquema).
        """
        self._cliente = cliente
        self._modelo = modelo
        self._info = info
        self._parametros = dict(parametros or {})
        self._estricto = esquema_estricto
        self._con_esquema = True  # pasa a False si el modelo rechaza `response_format`

    def info(self) -> ModeloInfo:
        return self._info

    async def salud(self) -> bool:
        return await self._cliente.disponible(self._modelo)

    async def interpretar(
        self, transcripcion: Transcripcion, catalogo: CatalogoInstrumento, contexto: Contexto
    ) -> Intencion:
        cuerpo = {
            "temperature": 0,  # el mismo pedido tiene que dar siempre la misma intención
            **self._parametros,
        }
        # Un parámetro en null no se manda: hay modelos que rechazan alguno (gpt-5.4-mini, temperature).
        cuerpo = {k: v for k, v in cuerpo.items() if v is not None}
        cuerpo |= {
            # El prompt de sistema es igual en todos los pedidos: los servidores lo guardan en caché.
            "messages": [
                {"role": "system", "content": instrucciones(catalogo)},
                {"role": "user", "content": mensaje(transcripcion, contexto)},
            ],
        }
        esquema = {"name": "intencion", "schema": esquema_respuesta(catalogo)}
        if self._estricto:
            esquema["strict"] = True
        if self._con_esquema:
            try:
                texto = await self._cliente.chat(
                    self._modelo, {**cuerpo, "response_format": {"type": "json_schema", "json_schema": esquema}}
                )
            except RechazoDelProveedor as e:
                if e.estado not in _PARAMETRO_NO_ADMITIDO:
                    raise
                # Un 400 puede ser por otra cosa (ej. región no habilitada). Solo si sin esquema
                # funciona se concluye que el problema era `response_format` y se recuerda.
                texto = await self._cliente.chat(self._modelo, cuerpo)
                log.warning("%s rechazó response_format; se sigue sin esquema: %s", self._modelo, e)
                self._con_esquema = False
        else:
            texto = await self._cliente.chat(self._modelo, cuerpo)
        return a_intencion(extraer_json(texto), transcripcion, catalogo, self._info)


def extraer_json(texto: str) -> str:
    """Sin salida estructurada, un modelo puede envolver el JSON en un bloque ```json o agregarle
    una frase. Se toma desde la primera llave hasta la última; si no hay, el texto tal cual (y
    `a_intencion` lo rechaza)."""
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    inicio, fin = texto.find("{"), texto.rfind("}")
    return texto[inicio : fin + 1] if 0 <= inicio < fin else texto
