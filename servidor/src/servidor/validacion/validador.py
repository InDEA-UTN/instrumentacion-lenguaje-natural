"""Validación determinística de una intención (docs/arquitectura.md, sección 3.4).

No conoce al modelo de lenguaje: recibe una Intencion y no le importa de dónde salió. La
confirmación de acciones sensibles no se decide acá sino en el pipeline, que es quien guarda estado.
"""

from ..catalogo import armar_comando, campos_de_plantilla
from ..dominio.modelos import (
    CatalogoInstrumento,
    ComandoSCPI,
    DefParametro,
    Intencion,
    Rechazo,
    TipoIntencion,
    Valor,
)


def validar(intencion: Intencion, catalogo: CatalogoInstrumento) -> ComandoSCPI | Rechazo:
    if intencion.tipo not in (TipoIntencion.ACCION, TipoIntencion.CONSULTA):
        return Rechazo(motivo=f"Una intención de tipo '{intencion.tipo}' no se ejecuta.")

    # 1. La acción existe en el catálogo del instrumento conectado.
    accion = catalogo.accion(intencion.accion)
    if accion is None:
        return Rechazo(
            motivo=f"La acción '{intencion.accion}' no está en el catálogo de {catalogo.instrumento.id}."
        )

    consulta = intencion.tipo == TipoIntencion.CONSULTA
    if consulta and not accion.verificacion_scpi:
        return Rechazo(motivo=f"La acción '{accion.id}' no tiene una consulta asociada.")

    if consulta:
        admitidos = requeridos = campos_de_plantilla(accion.verificacion_scpi)
    else:
        admitidos = {p.nombre for p in accion.parametros}
        requeridos = {p.nombre for p in accion.parametros if p.obligatorio}
        requeridos |= campos_de_plantilla(accion.plantilla_scpi)
        requeridos |= campos_de_plantilla(accion.verificacion_scpi or "")

    recibidos = set(intencion.parametros)
    if desconocidos := recibidos - admitidos:
        return Rechazo(motivo=f"Parámetros que '{accion.id}' no admite: {', '.join(sorted(desconocidos))}.")

    # 2. Están todos los obligatorios.
    if faltantes := requeridos - recibidos:
        return Rechazo(motivo=f"Faltan parámetros de '{accion.id}': {', '.join(sorted(faltantes))}.")

    # 3 y 4. Tipo correcto y dentro del rango de este instrumento.
    valores: dict[str, int | float] = {}
    for nombre, crudo in intencion.parametros.items():
        definicion = accion.parametro(nombre)
        valor = _convertir(definicion, crudo)
        if valor is None:
            return Rechazo(motivo=f"'{nombre}' tiene que ser {definicion.tipo}; llegó {crudo!r}.")
        if definicion.rango and not (definicion.rango[0] <= valor <= definicion.rango[1]):
            minimo, maximo = definicion.rango
            unidad = f" {definicion.unidad}" if definicion.unidad else ""
            return Rechazo(
                motivo=f"'{nombre}' = {valor:g}{unidad} está fuera de rango [{minimo:g}, {maximo:g}]{unidad}."
            )
        valores[nombre] = valor

    # 6. Armar el comando (el 5, confirmación, lo resuelve el pipeline).
    return armar_comando(accion, valores, consulta=consulta)


def _convertir(definicion: DefParametro, crudo: Valor) -> int | float | None:
    if isinstance(crudo, bool):
        return None
    try:
        numero = float(crudo)
    except (TypeError, ValueError):
        return None
    if definicion.tipo == "entero":
        return int(numero) if numero.is_integer() else None
    return numero
