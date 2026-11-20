class ErrorDominio(Exception):
    pass


class ModeloNoDisponible(ErrorDominio):
    """El modelo no responde: servicio caído, red, tiempo de espera agotado."""


class RespuestaInvalida(ErrorDominio):
    """El modelo respondió algo que no cumple el esquema esperado."""


class CatalogoInvalido(ErrorDominio):
    """El archivo de catálogo está mal formado."""


class InteraccionInexistente(ErrorDominio):
    pass


class InstrumentoNoDisponible(ErrorDominio):
    """No hay comunicación con el instrumento: desenchufado, apagado, otro modelo o timeout."""


class RechazoDelInstrumento(ErrorDominio):
    """El instrumento recibió el comando y lo rechazó, o no pudo dar el dato pedido."""
