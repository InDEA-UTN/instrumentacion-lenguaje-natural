# Estado del arte

> **Estado: pendiente (OE1).** Este documento es el resultado del primer objetivo específico del
> proyecto. Lo que sigue es la guía de qué relevar y con qué criterio, no el relevamiento hecho.

El relevamiento no es un trámite previo: es lo que evita reimplementar algo que ya existe y lo que
permite justificar cada decisión de la fase 0 con algo más que una preferencia. Se escribe **acá**,
en este archivo, a medida que se avanza.

## Cómo se anota cada antecedente

Para cada trabajo, herramienta o modelo relevado:

```markdown
### Título del trabajo o nombre de la herramienta
- **Referencia:** autores, año, enlace (artículo, repositorio o documentación).
- **Qué hace:** dos o tres líneas.
- **Qué toma de acá:** qué de este trabajo aplica a nuestro problema.
- **En qué se diferencia:** qué hace distinto o qué no resuelve.
- **Conclusión para el proyecto:** se adopta, se descarta, o queda como referencia.
```

Un antecedente sin la línea de conclusión no sirve: es una cita sin decisión.

## 1. Control de instrumentación por lenguaje natural

Qué buscar:

- Trabajos que usen modelos de lenguaje para generar comandos SCPI o controlar instrumental de
  laboratorio.
- Interfaces por voz en entornos industriales o de laboratorio, y qué reportan sobre confiabilidad
  y aceptación de los usuarios.
- Herramientas de los propios fabricantes de instrumental que incorporen asistentes conversacionales.
- El patrón general de **traducción de lenguaje natural a un lenguaje formal acotado**, que es el
  problema del que este proyecto es un caso particular: consultas a bases de datos, control
  robótico, invocación de interfaces de programación.

Pregunta a responder: ¿alguien ya puso la frontera entre lo probabilístico y lo determinístico en
otro lado, y con qué resultado?

## 2. Reconocimiento automático del habla (ASR)

Insumo directo de la decisión **D2**. Comparar sobre los mismos criterios:

| Criterio | Por qué importa acá |
|---|---|
| Tasa de error de palabra (WER) en español rioplatense | El sistema se usa en Mendoza, no en un laboratorio de referencia. |
| Desempeño con vocabulario técnico | "volt por división", "trigger", "duty cycle", "punta por diez". Un motor genérico falla justo acá. |
| Latencia | Determina si la interacción se siente conversacional o no. |
| Local o en la nube | Define si el sistema funciona sin internet y cuál es el costo por uso. |
| Requerimientos de cómputo | Si es local, tiene que correr en el hardware del laboratorio. |
| Licencia | El proyecto es abierto. |

Candidatos a relevar: Whisper y sus variantes optimizadas, modelos de ASR abiertos entrenados en
español, y los servicios de transcripción comerciales.

**No se elige por reputación: se mide.** El corpus de prueba y el protocolo están en
[`evaluacion.md`](evaluacion.md).

## 3. Modelos de lenguaje y salida estructurada

Insumo de la decisión **D3** y de la fase 3:

- Modelos comerciales con llamada a herramientas, para la etapa 1: capacidad de respetar un
  esquema, latencia, costo por consulta.
- Modelos abiertos y chicos candidatos al ajuste fino de la etapa 3 —del orden de los 4 mil
  millones de parámetros—, con atención a cuáles ya vienen entrenados para llamada a herramientas.
- Técnicas de ajuste fino eficiente en parámetros (LoRA y variantes) y el hardware que requieren.
- Modelos multimodales con entrada de voz, para la comparación de la fase 4.

## 4. Bibliotecas de comunicación con instrumentos

Ya relevado parcialmente en [`scpi.md`](scpi.md): PyVISA, `pyvisa-py`, `pyvisa-sim` y el acceso
directo por *sockets*. Falta verificar cuál funciona efectivamente con el instrumento que se elija
en D1, y con qué versión de la capa VISA.

## 5. Antecedentes relevados

*(vacío — se completa a medida que avanza el OE1)*
