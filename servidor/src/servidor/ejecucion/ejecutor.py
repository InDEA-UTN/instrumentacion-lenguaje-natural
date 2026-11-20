import threading

from ..dominio.modelos import ComandoSCPI, ResultadoEjecucion
from ..dominio.puertos import ConexionInstrumento


class Ejecutor:
    """Envía el comando y, siempre que haya consulta de verificación, lee cómo quedó el instrumento."""

    def __init__(self, conexion: ConexionInstrumento):
        self.conexion = conexion
        # La escritura y su verificación van juntas: otro pedido no puede meterse en el medio.
        self._candado = threading.Lock()

    def ejecutar(self, comando: ComandoSCPI) -> ResultadoEjecucion:
        with self._candado:
            if comando.escritura:
                self.conexion.escribir(comando.escritura)
            lectura = self.conexion.consultar(comando.verificacion) if comando.verificacion else None
        return ResultadoEjecucion(comando=comando, lectura=lectura)
