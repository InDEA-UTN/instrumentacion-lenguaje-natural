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

    parametros = dict(intencion.parametros)
    admitidos = {p.nombre for p in accion.parametros}
    if desconocidos := set(parametros) - admitidos:
        return Rechazo(motivo=f"Parámetros que '{accion.id}' no admite: {', '.join(sorted(desconocidos))}.")

    if consulta:
        # Una consulta solo usa lo que identifica qué leer (ej. el canal). Si el modelo agregó un
        # parámetro de la acción que no hace falta ("¿en cuánto está la base de tiempo?" con un
        # `valor`), se descarta: no se escribe nada, así que no hay riesgo en ignorarlo.
        requeridos = campos_de_plantilla(accion.verificacion_scpi)
        parametros = {k: v for k, v in parametros.items() if k in requeridos}
    else:
        requeridos = {p.nombre for p in accion.parametros if p.obligatorio}
        requeridos |= campos_de_plantilla(accion.plantilla_scpi)
        requeridos |= campos_de_plantilla(accion.verificacion_scpi or "")

    recibidos = set(parametros)

    # 2. Están todos los obligatorios.
    if faltantes := requeridos - recibidos:
        return Rechazo(motivo=f"Faltan parámetros de '{accion.id}': {', '.join(sorted(faltantes))}.")

    # 3 y 4. Tipo correcto y dentro del rango de este instrumento.
    valores: dict[str, int | float | str] = {}
    for nombre, crudo in parametros.items():
        definicion = accion.parametro(nombre)
        valor = _convertir(definicion, crudo)
        if valor is None:
            if definicion.tipo == "opcion":
                admitidas = ", ".join(definicion.opciones)
                return Rechazo(motivo=f"'{nombre}' tiene que ser una de: {admitidas}; llegó {crudo!r}.")
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


def _convertir(definicion: DefParametro, crudo: Valor) -> int | float | str | None:
    if isinstance(crudo, bool):
        return None
    if definicion.tipo == "opcion":
        return _opcion(definicion, crudo)
    try:
        numero = float(crudo)
    except (TypeError, ValueError):
        return None
    if definicion.tipo == "entero":
        return int(numero) if numero.is_integer() else None
    return numero


def _opcion(definicion: DefParametro, crudo: Valor) -> str | None:
    """Devuelve la opción tal como la declara el catálogo. Acepta mayúsculas o minúsculas, y un
    número para opciones numéricas (atenuación de sonda 10 → "10")."""
    if isinstance(crudo, float) and crudo.is_integer():
        crudo = int(crudo)
    texto = str(crudo).strip().upper()
    return next((o for o in definicion.opciones if o.upper() == texto), None)
