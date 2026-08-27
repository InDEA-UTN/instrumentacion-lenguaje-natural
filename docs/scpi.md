# SCPI y la comunicación con el instrumento

## 1. Qué es SCPI

**SCPI** (*Standard Commands for Programmable Instruments*, comandos estándar para instrumentos
programables) es un estándar de 1990, construido sobre IEEE 488.2, que define una sintaxis común
para controlar instrumentos de medición por texto plano. La idea que lo hace útil para este
proyecto: instrumentos de fabricantes distintos aceptan comandos con la misma forma.

Un comando es una cadena de texto con una jerarquía separada por dos puntos:

```
:CHANnel1:SCALe 0.5      → escritura: poné el canal 1 en 0,5 V/div
:CHANnel1:SCALe?         → consulta: ¿en cuánto está el canal 1?
:TIMebase:MAIN:SCALe 1e-3
*IDN?                    → identificación del instrumento
*RST                     → reinicio a valores de fábrica
```

Tres convenciones que conviene tener claras desde el principio:

- **Mayúsculas y minúsculas.** `CHANnel` indica que la forma corta es `CHAN` y la larga
  `CHANNEL`; las dos son válidas y equivalentes. En este proyecto se escribe **siempre la forma
  larga** en las plantillas: es más legible y el ahorro de bytes no le importa a nadie.
- **Comandos comunes.** Los que empiezan con asterisco (`*IDN?`, `*RST`, `*OPC?`) son del estándar
  IEEE 488.2 y los implementa cualquier instrumento que diga ser compatible.
- **Escritura contra consulta.** El signo de pregunta al final marca una consulta, que devuelve un
  valor. Sin él es una escritura, que no devuelve nada. De ahí la regla de trabajo del proyecto:
  después de cada escritura se emite la consulta equivalente para verificar el resultado.

**Lo que el estándar no garantiza.** SCPI define la gramática, no el vocabulario completo: cada
fabricante agrega comandos propios y no todos implementan el mismo subconjunto. Por eso el catálogo
de acciones se declara **por instrumento** y no globalmente ([`esquema_intencion.md`](esquema_intencion.md)).

## 2. PyVISA y la capa de transporte

**VISA** (*Virtual Instrument Software Architecture*) es la interfaz de programación estándar que
abstrae *por dónde* está conectado el instrumento —USB, LAN, GPIB, puerto serie—. **PyVISA** es su
ligadura para Python: el mismo código sirve para las cuatro interfaces cambiando una cadena de
recurso.

```python
import pyvisa

rm = pyvisa.ResourceManager()
print(rm.list_resources())          # descubre lo que hay conectado

inst = rm.open_resource("TCPIP::192.168.1.50::INSTR")
print(inst.query("*IDN?"))          # identificación
inst.write(":CHANnel1:SCALe 0.5")   # escritura
print(inst.query(":CHANnel1:SCALe?"))  # verificación
```

Alternativas a evaluar en la fase 0 si PyVISA trae complicaciones de instalación de la capa VISA
del fabricante: `pyvisa-py` (implementación en Python puro, sin capa nativa) o hablar directamente
por *sockets* TCP, que muchos instrumentos exponen en el puerto 5025.

## 3. Desarrollo sin el instrumento: el simulador

Mientras la decisión D1 esté abierta —y también después, para las pruebas automáticas— el
desarrollo se hace contra un **instrumento simulado**. `pyvisa-sim` permite declarar en un archivo
YAML un instrumento con sus comandos y sus respuestas, y `PyVISA` lo abre como si fuera real.

Esto no es un parche: es lo que permite que la capa de validación y traducción tenga tests que
corren en cualquier máquina, sin hardware y sin ocupar el equipo del laboratorio. El simulador se
versiona junto con la ficha del instrumento que imita.

## 4. Cómo se releva el conjunto de comandos de un instrumento

Procedimiento para cada instrumento que se incorpore, en este orden:

1. **Identificarlo.** `*IDN?` devuelve fabricante, modelo, número de serie y versión de firmware.
   Ese es el dato que hay que anotar en la ficha, no lo que dice la etiqueta del frente.
2. **Conseguir el manual de programación.** Es un documento distinto del manual de usuario, y es
   el que trae la lista completa de comandos con sus rangos. Se enlaza desde la ficha del
   instrumento; **no se sube el PDF al repositorio**.
3. **Elegir el subconjunto.** No se soportan todos los comandos: se eligen los que corresponden a
   las operaciones que la gente realmente pide. El catálogo acotado es una decisión de diseño, no
   una limitación temporal.
4. **Verificar cada comando a mano** antes de declararlo en el catálogo, anotando el rango real
   aceptado. Los manuales tienen erratas y los firmware tienen diferencias entre versiones.
5. **Anotar los rangos en la declaración de la acción.** Son los que usa la capa de validación para
   rechazar un valor imposible antes de enviarlo.

## 5. Catálogo de la etapa 1

*(Pendiente de la decisión D1: instrumento objetivo.)*

Como referencia del tipo de operación que se busca cubrir en el prototipo —entre cinco y diez
acciones sobre un osciloscopio—:

| Operación | Ejemplo de pedido hablado |
|---|---|
| Escala vertical de un canal | *"poné el canal uno en quinientos milivoltios por división"* |
| Base de tiempo | *"llevá la base de tiempo a un milisegundo"* |
| Fuente y nivel del disparo | *"disparo por flanco en el canal dos, a un volt"* |
| Acoplamiento de un canal | *"pasá el canal uno a acoplamiento alterna"* |
| Encender o apagar un canal | *"apagá el canal tres"* |
| Autoescala | *"autoescala"* |
| Consulta de estado | *"¿en cuánto está la base de tiempo?"* |

La tabla definitiva, con la plantilla SCPI y el rango verificado de cada parámetro, va en la ficha
del instrumento en [`../instrumentos/`](../instrumentos/).

## 6. Referencias

- Manual de programación del instrumento objetivo — *(pendiente de D1)*.
- [Documentación de PyVISA](https://pyvisa.readthedocs.io/)
- [`pyvisa-sim`](https://pyvisa-sim.readthedocs.io/) — instrumentos simulados.
- IEEE 488.2 y el estándar SCPI 1999.0 (SCPI Consortium).
