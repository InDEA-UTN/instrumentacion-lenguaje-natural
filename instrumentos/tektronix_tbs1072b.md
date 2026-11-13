# Tektronix TBS1072B

Osciloscopio digital de 2 canales, 70 MHz y 1 GS/s, de la serie TBS1000B.

- **Respuesta a `*IDN?`:** *(pendiente: anotarla al conectar el equipo)*.
- **Interfaz:** USB (puerto de dispositivo, clase USBTMC). La cadena de recurso VISA tiene la forma
  `USB0::0x0699::0x....::<número de serie>::INSTR` *(pendiente: anotarla al conectar el equipo)*.
- **Manual de programación:** *TBS1000B/EDU, TBS1000, TDS2000C/TDS1000C-EDU, TDS2000B/TDS1000B,
  TDS2000/TDS1000, TDS200 and TPS2000B/TPS2000 Series Digital Oscilloscopes Programmer Manual*,
  Tektronix 077-0444-03, Rev B, disponible en tek.com. El PDF no se sube al repositorio.
- **Versión de firmware verificada:** ninguna todavía.
- **Estado:** solo simulado. Los comandos y argumentos salen del manual. Los rangos salen del
  manual y de la configuración de fábrica (apéndice B) y **no están verificados sobre el equipo**.

## Catálogo de acciones

Diez acciones. La declaración que usa el servidor está en
[`servidor/src/servidor/catalogos/tektronix_tbs1072b.yaml`](../servidor/src/servidor/catalogos/tektronix_tbs1072b.yaml).

| Acción | Parámetros y rango (del manual, sin verificar) | Plantilla SCPI | Consulta de verificación | Sensible |
|---|---|---|---|---|
| `configurar_escala_vertical` | `canal` 1–2; `valor` 2 mV a 50 V/div | `CH{canal}:SCAle {valor}` | `CH{canal}:SCAle?` | No |
| `configurar_acoplamiento` | `canal` 1–2; `acoplamiento` AC, DC, GND | `CH{canal}:COUPling {acoplamiento}` | `CH{canal}:COUPling?` | No |
| `configurar_atenuacion_sonda` | `canal` 1–2; `atenuacion` 1, 10, 20, 50, 100, 500, 1000 | `CH{canal}:PRObe {atenuacion}` | `CH{canal}:PRObe?` | No |
| `mostrar_canal` | `canal` 1–2; `visible` ON, OFF | `SELect:CH{canal} {visible}` | `SELect:CH{canal}?` | No |
| `configurar_base_tiempo` | `valor` 5 ns a 50 s/div | `HORizontal:MAIn:SCAle {valor}` | `HORizontal:MAIn:SCAle?` | No |
| `configurar_nivel_disparo` | `valor` −50 a 50 V | `TRIGger:MAIn:LEVel {valor}` | `TRIGger:MAIn:LEVel?` | No |
| `configurar_fuente_disparo` | `fuente` CH1, CH2, EXT, EXT5, LINE | `TRIGger:MAIn:EDGE:SOUrce {fuente}` | `TRIGger:MAIn:EDGE:SOUrce?` | No |
| `controlar_adquisicion` | `adquisicion` RUN, STOP | `ACQuire:STATE {adquisicion}` | `ACQuire:STATE?` | No |
| `medir` | `canal` 1–2; `magnitud` FREQuency, PERIod, PK2pk, AMplitude, MEAN, RMS, MAXImum, MINImum, RISe, FALL | `MEASUrement:IMMed:SOUrce CH{canal};TYPe {magnitud}` | `MEASUrement:IMMed:SOUrce CH{canal};TYPe {magnitud};VALue?` | No |
| `autoescala` | — | `AUTOSet EXECute` | — | **Sí** |

Por qué estas diez: cubren lo que un estudiante hace en casi toda práctica (escala, acoplamiento,
sonda, canales visibles, base de tiempo, disparo, congelar la pantalla y medir) más el autoset.
Quedaron afuera, como candidatas para la etapa 2: `CH<x>:POSition`, `TRIGger:MAIn:EDGE:SLOpe`,
`HORizontal:MAIn:POSition`, `ACQuire:MODe`, `CH<x>:BANdwidth` y `*RST`.

## Particularidades

Lo que dice el manual y conviene tener presente al verificar:

- **Encabezados en las respuestas.** De fábrica el equipo responde con `HEADer ON`:
  `CH1:SCAle?` devuelve `CH1:SCALE 1.0E0` en lugar de `1.0E0`. La conexión real tiene que enviar
  `HEADer OFF` al abrirse.
- **La escala vertical depende de la sonda.** `CH<x>:SCAle` está en V/div de pantalla, ya
  multiplicados por la atenuación. Va de 2 mV a 5 V/div con sonda 1X y de 20 mV a 50 V/div con
  10X, que es la atenuación de fábrica. El catálogo admite la unión de los dos rangos y el equipo
  ajusta lo que no corresponda. La lectura de verificación muestra el valor real.
- **Redondeo de la base de tiempo.** `HORizontal:MAIn:SCAle` solo admite la secuencia 1-2,5-5 y
  lleva cualquier otro valor al más cercano. El manual no da el rango por modelo: 5 ns a 50 s/div
  es el de la hoja de datos de la serie y hay que confirmarlo en el equipo.
- **Nivel de disparo.** El equipo lo limita a unas ±8 divisiones de la escala del canal fuente.
  Con la fuente en `LINE` ignora el comando y genera el evento 221.
- **Mediciones.** Si el canal medido no está visible, `MEASUrement:IMMed:VALue?` devuelve
  `9.9E37` y genera el evento 2225. Ese valor significa "no se pudo medir", no es una lectura.
- **Comandos encadenados.** `medir` usa el encadenamiento con `;` que documenta el manual
  (sección "Concatenating Commands"): los comandos de un mismo nodo se abrevian al último
  mnemónico.
- **`ACQuire:STATE?` y `SELect:CH<x>?`** responden `0` o `1`, no `STOP`/`RUN` ni `OFF`/`ON`.

## Simulador

Por ahora el servidor usa el instrumento en memoria (`servidor/src/servidor/ejecucion/instrumento_fake.py`).
Todavía no hay un archivo de `pyvisa-sim` para este equipo.
