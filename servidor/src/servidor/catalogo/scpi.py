from string import Formatter

from ..dominio.modelos import Accion, ComandoSCPI, Magnitud


def campos_de_plantilla(plantilla: str) -> set[str]:
    return {campo for _, campo, _, _ in Formatter().parse(plantilla) if campo}


def armar_comando(accion: Accion, valores: dict[str, int | float], consulta: bool = False) -> ComandoSCPI:
    """Instancia las plantillas de la acción. Los valores ya tienen que estar validados."""
    texto = {k: _formatear(v) for k, v in valores.items()}
    verificacion = accion.verificacion_scpi.format(**texto) if accion.verificacion_scpi else None
    return ComandoSCPI(
        accion=accion.id,
        escritura=None if consulta else accion.plantilla_scpi.format(**texto),
        verificacion=verificacion,
        parametros={
            k: Magnitud(valor=v, unidad=(p.unidad if (p := accion.parametro(k)) else None))
            for k, v in valores.items()
        },
        sensible=accion.sensible and not consulta,
    )


def _formatear(valor: int | float) -> str:
    return str(valor) if isinstance(valor, int) else f"{valor:g}"
