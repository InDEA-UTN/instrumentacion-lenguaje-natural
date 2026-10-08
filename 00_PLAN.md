# Plan del proyecto

**Proyecto:** Control de instrumentación electrónica por lenguaje natural
**Responsable:** Juan Pablo Masuet — Práctica Profesional Supervisada (PPS)
**Director:** Javier Velez
**Laboratorio:** InDEA, UTN Facultad Regional Mendoza
**Inicio:** 2026-08-27

Este documento fija qué se busca, en qué orden y con qué criterio se da por cumplida cada etapa.
Se actualiza cuando una decisión se cierra o una fase cambia de estado; **no** es la bitácora, que
va en [`BITACORA.md`](BITACORA.md).

## 1. Objetivo general

Diseñar, implementar y evaluar un sistema que permita configurar instrumental electrónico de
laboratorio mediante instrucciones habladas en lenguaje natural, traduciéndolas de forma validada a
comandos SCPI (*Standard Commands for Programmable Instruments*).

## 2. Objetivos específicos

| | Objetivo específico | Fase |
|---|---|---|
| **OE1** | Relevar el estado del arte en control de instrumentación por lenguaje natural, los modelos de reconocimiento automático del habla (ASR) disponibles y las bibliotecas de comunicación con instrumentos. | 0 |
| **OE2** | Definir el **esquema de intención**: el conjunto cerrado de acciones que el sistema reconoce, sus parámetros y sus límites, como contrato entre el modelo de lenguaje y la capa de ejecución. | 0–1 |
| **OE3** | Implementar un prototipo funcional extremo a extremo —aplicación de captura, transcripción, interpretación, validación y ejecución— con un modelo comercial y un catálogo acotado. | 1 |
| **OE4** | Ampliar el catálogo de acciones y la cobertura de instrumentos, y caracterizar el vocabulario real con el que los usuarios formulan los pedidos. | 2 |
| **OE5** | Construir un conjunto de datos de pares *(enunciado, intención)* y ajustar finamente un modelo de lenguaje abierto y chico que pueda ejecutarse en el laboratorio. | 3 |
| **OE6** | Evaluar comparativamente la arquitectura en cascada (ASR + modelo de lenguaje) frente a un modelo multimodal con entrada de voz directa, con métricas objetivas. | 4 |

## 3. Fases

### Fase 0 — Relevamiento y definiciones · *en curso*

Antes de escribir código hay que cerrar cinco cosas. Ninguna es una decisión de implementación:
todas cambian la arquitectura si se resuelven de una manera o de otra.

| # | Qué hay que definir | Dónde se documenta |
|---|---|---|
| D1 | **Instrumento objetivo** de la etapa 1: qué equipo con interfaz remota se va a usar. Ver la advertencia de la sección 5. | [`instrumentos/`](instrumentos/) |
| D2 | **Motor de ASR**: servicio en la nube o modelo local; costo, latencia y desempeño con vocabulario técnico en español rioplatense. | [`docs/estado_del_arte.md`](docs/estado_del_arte.md) |
| D3 | **Modelo de lenguaje de la etapa 1** y mecanismo de salida estructurada (llamada a herramientas, salida forzada a un esquema, o análisis sintáctico de la respuesta). | [`docs/arquitectura.md`](docs/arquitectura.md) |
| D4 | **Transporte** entre la aplicación y el servidor, y ubicación del servidor respecto del instrumento. | [`docs/arquitectura.md`](docs/arquitectura.md) |
| D5 | **Versión inicial del esquema de intención** y el catálogo de acciones de la etapa 1. | [`docs/esquema_intencion.md`](docs/esquema_intencion.md) |

**Criterio de aceptación:** las cinco decisiones escritas, con su fundamento y las alternativas
descartadas. Una decisión sin el motivo anotado se vuelve a discutir en tres meses.

### Fase 1 — Prototipo extremo a extremo

Cadena completa funcionando sobre **un** instrumento y **entre cinco y diez acciones**. El objetivo
es tener algo que funcione de punta a punta lo antes posible, no que funcione bien: el prototipo
existe para descubrir los problemas reales de la idea.

Alcance mínimo:

- Aplicación web (PWA) que captura audio y lo envía al servidor.
- Servidor que transcribe, interpreta, **valida** y ejecuta.
- Realimentación al usuario: qué entendió el sistema y qué hizo o por qué se negó.
- Un pedido fuera del catálogo se **rechaza explícitamente**; nunca se aproxima al comando más
  parecido.

**Criterio de aceptación:** una demostración en vivo donde una persona ajena al proyecto configura
el instrumento hablando, sin tocarlo, y el sistema rechaza correctamente al menos un pedido fuera
de su catálogo.

### Fase 2 — Ampliación del catálogo

Extender acciones, parámetros e instrumentos. Recolectar cómo pide realmente la gente cada cosa:
ese registro es la materia prima del conjunto de datos de la fase 3.

**Criterio de aceptación:** catálogo documentado por instrumento y un corpus inicial de enunciados
reales, anotados.

### Fase 3 — Conjunto de datos y ajuste fino

Construir el conjunto de datos de pares *(enunciado, intención)* y ajustar finamente un modelo
abierto y chico —Qwen3-4B, Gemma 3 4B o equivalente, **a definir**— que corra en el laboratorio.
Motivación: independencia del servicio pago, costo por consulta nulo, latencia previsible y
funcionamiento sin conexión a internet.

**Criterio de aceptación:** el modelo ajustado iguala o supera al modelo comercial en el catálogo
de la etapa 2, medido con el protocolo de [`docs/evaluacion.md`](docs/evaluacion.md).

### Fase 4 — Evaluación comparativa y cierre

Comparar la cascada contra un **modelo multimodal con entrada de voz directa**, que elimina la
etapa de transcripción y con ella su acumulación de errores. Informe final y defensa de la PPS.

**Criterio de aceptación:** informe con las métricas de las dos arquitecturas, sus condiciones
experimentales y una recomendación fundada.

## 4. Fuera de alcance

Para que el alcance no se corra sin que nadie lo note, queda explícito lo que **no** entra:

- Control de instrumentos por interfaces propietarias que no expongan SCPI ni una interfaz de
  programación documentada.
- Automatización de secuencias de medición completas o generación de informes. El sistema configura
  el instrumento; no reemplaza al operador.
- Aplicaciones nativas para Android o iOS. La captura es una aplicación web (PWA).
- Cualquier acción sobre el instrumento que pueda dañarlo o dañar al circuito bajo prueba. El
  catálogo es cerrado y sus límites son parte del diseño.

## 5. Riesgos y dependencias

| Riesgo | Impacto | Mitigación |
|---|---|---|
| **No hay en el inventario del laboratorio ningún instrumento con interfaz SCPI registrada.** El instrumental cargado es analógico o sin interfaz remota. | Bloquea la validación sobre hardware real. | La fase 1 se desarrolla contra un **instrumento simulado** (`pyvisa-sim` o un servidor SCPI de prueba), que además deja el sistema comprobable sin ocupar el equipo. En paralelo, el director gestiona el acceso a un instrumento real: compra, préstamo o uso en otra cátedra. |
| Desempeño pobre del ASR con vocabulario técnico y español rioplatense. | Errores de transcripción que se propagan a la interpretación. | Medirlo en la fase 0 antes de comprometerse (D2). Es uno de los argumentos a favor del modelo multimodal de la fase 4. |
| El modelo interpreta mal y emite una acción válida pero no deseada. | Configuración incorrecta del instrumento. | Confirmación explícita al usuario antes de ejecutar, y validación de rangos. Ver [`docs/arquitectura.md`](docs/arquitectura.md). |
| Costo del servicio comercial durante la etapa 1. | Restringe la experimentación. | Catálogo acotado, registro del consumo y salida programada hacia el modelo propio en la fase 3. |

## 6. Decisiones cerradas

Se anotan acá para no volver a discutirlas. Mientras la tabla esté vacía, todo está abierto.

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-08-27 | El modelo de lenguaje **no emite SCPI**: emite una intención estructurada y una capa determinística la traduce y la valida. | Hace auditable lo que llega al instrumento y acota el daño de una interpretación errónea. |
| 2026-10-08 | La aplicación de captura es una **aplicación web progresiva (PWA)**, no una aplicación nativa Android o iOS. | Un solo código corre en cualquier dispositivo con navegador, se instala sin tienda de aplicaciones y comparte la base del front web de prueba. |
| 2026-08-27 | El repositorio es **público**, con licencia MIT. | El proyecto es de investigación aplicada y no maneja datos sensibles. |
