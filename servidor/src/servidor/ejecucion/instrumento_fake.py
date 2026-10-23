class InstrumentoFake:
    """Instrumento en memoria: guarda lo que se escribe y lo devuelve al consultarlo.

    Sirve para probar la cascada sin hardware ni pyvisa-sim. No imita redondeos ni errores.
    """

    def __init__(self, idn: str = "FAKE,Instrumento en memoria,0,0"):
        self.idn = idn
        self.estado: dict[str, str] = {}
        self.historial: list[str] = []

    def escribir(self, comando: str) -> None:
        self.historial.append(comando)
        if comando.strip().upper() == "*RST":
            self.estado.clear()
            return
        clave, _, valor = comando.strip().partition(" ")
        self.estado[clave.upper()] = valor

    def consultar(self, comando: str) -> str:
        self.historial.append(comando)
        if comando.strip().upper() == "*IDN?":
            return self.idn
        return self.estado.get(comando.strip().rstrip("?").upper(), "0")
