from ..dominio.modelos import ComandoSCPI, ResultadoEjecucion
from ..dominio.puertos import ConexionInstrumento


class Ejecutor:
    """Envía el comando y, siempre que haya consulta de verificación, lee cómo quedó el instrumento."""

    def __init__(self, conexion: ConexionInstrumento):
        self._conexion = conexion

    def ejecutar(self, comando: ComandoSCPI) -> ResultadoEjecucion:
        if comando.escritura:
            self._conexion.escribir(comando.escritura)
        lectura = self._conexion.consultar(comando.verificacion) if comando.verificacion else None
        return ResultadoEjecucion(comando=comando, lectura=lectura)
