# Bitácora del proyecto

Registro **cronológico** del trabajo: hitos, decisiones, resultados de cada iteración y próximos
pasos. Es la memoria del proyecto y el insumo del informe final.

> **Este archivo es el registro formal de la Práctica Profesional Supervisada (PPS).** El
> laboratorio no lleva una bitácora de asistencia aparte para esta figura: lo que consta del
> trabajo es lo que está acá. Una semana sin entradas es una semana sin registro.

**Cómo se usa:**

- **Lo más reciente va arriba.** Cada iteración o hito agrega una entrada nueva al principio.
- Cada entrada usa la plantilla de abajo. Copiala, completala y pegala arriba de las demás.
- La entrada va **en el mismo pull request** que el trabajo que describe, no después.
- La bitácora es un **índice**, no la documentación: el detalle técnico va al documento de `docs/`
  que corresponda y la entrada apunta ahí.
- Los datos y figuras pesados (capturas de pantalla del instrumento, grabaciones de audio,
  mediciones) no se pegan acá: se enlazan, con una leyenda de qué muestran y en qué condiciones.

---

### Plantilla de entrada (copiar y completar)

```
## AAAA-MM-DD — Título de la iteración o hito
- **Fase:** 0 / 1 / 2 / 3 / 4 · **Estado:** 🟨 En curso / ✅ Hecho / ⏸️ En pausa
- **Objetivo:** qué se quería lograr o verificar.
- **Actividad:** qué se hizo.
- **Resultado:** qué salió, comparado con lo esperado. Si no funcionó, también se anota.
- **Documentado en:** enlace al commit, al pull request o al documento de `docs/`.
- **Próximo paso:** qué sigue.
```

---

## 2026-10-25 — Front de prueba integrado con el servidor
- **Fase:** 1 · **Estado:** ✅ Hecho
- **Objetivo:** recorrer la cadena completa desde el navegador, no solo con `curl`, mostrando lo que
  pide [`app/README.md`](app/README.md): transcripción, acción interpretada y resultado leído del
  instrumento, con confirmación y aclaración.
- **Actividad:** el front deja de hablar con whisper y pasa a usar solo el servidor (`/pedidos`,
  `/confirmaciones`, `/salud`).
  - Grabación con **presionar y sostener**, con el botón o la barra espaciadora. Un toque de menos
    de 300 ms se descarta.
  - Una tarjeta con el último pedido y botones Confirmar / Cancelar.
  - Línea de salud con el modelo de cada etapa.
  - Id de sesión por pestaña y botón "Nueva sesión".
  - El servidor no cambió.
- **Resultado:** probado con Chrome headless (Playwright).
  - Con un audio real como micrófono simulado, la cadena completa se ejecutó en 8,2 s.
  - El resto de los estados se probó con copias del servidor con ASR de texto fijo y Qwen real:
    confirmación → Confirmar → ejecutada, Cancelar → cancelada, rechazo fuera de catálogo,
    consulta y aclaración.
  - También se verificaron el error 503 con el detalle del servidor y el descarte del toque corto.
  - Volvió a aparecer el problema de contexto: el mismo pedido explícito, repetido en la misma
    sesión, termina en una aclaración innecesaria. "Nueva sesión" lo evita, pero el arreglo es
    del prompt.
  - Sin `CATALOGO` definida, el servidor instalado en la imagen no encuentra el catálogo, porque la
    ruta por defecto de `config.py` solo sirve en modo editable. El compose lo cubre.
- **Documentado en:** [`app/front-web/README.md`](app/front-web/README.md).
- **Próximo paso:**
  - Arreglar el prompt para pedidos explícitos con contexto.
  - Probar la respuesta a una aclaración hablando (la cadena "subí la escala" → "el canal dos" no
    se pudo automatizar).
  - Corregir la ruta por defecto del catálogo.

## 2026-10-25 — Intérprete local con Qwen3.5-4B sobre llama.cpp (prueba de concepto)
- **Fase:** 0 (insumo de D3), sobre el esqueleto de servidor de la fase 1 · **Estado:** ✅ Hecho
- **Objetivo:** verificar si un modelo abierto y chico, corriendo local en CPU, puede reemplazar a
  Gemini como intérprete, con el mismo prompt, el mismo esquema y los mismos tests de contrato.
- **Actividad:** se eligió Qwen3.5-4B (generación actual de Qwen, febrero de 2026) en cuantización
  Q4_K_M, servido con `llama-server` de llama.cpp. Se prefirió llama.cpp a Ollama para fijar el
  archivo exacto y el tamaño de contexto (ver la nota del registro de modelos). Se agregó el
  servicio `llm` al docker-compose, con la imagen fija en `server-b11870`, `--reasoning off` y
  `-c 8192`. Se movieron el prompt y el esquema de Gemini a un módulo común, para que todos los
  modelos reciban exactamente lo mismo, y se escribió el adaptador `llama_cpp`, que pide salida
  forzada a un JSON Schema a la API compatible con OpenAI. Corre en CPU porque el Docker Engine de
  la máquina de desarrollo no tiene el runtime de NVIDIA.
- **Resultado:**
  - Pasa los tests de contrato (ejemplo del catálogo, fuera de catálogo sin aproximar, intención
    bien formada).
  - De punta a punta, con un audio real, ejecutó `:CHANnel1:SCALe 0.5` sobre el instrumento
    simulado en 7,6 s en total, todo local.
  - En una sonda de 4 pedidos acertó acción, consulta incompleta con aclaración y fuera de alcance,
    con la conversión de unidades correcta ("diez microsegundos" → 0.00001).
  - Latencia del intérprete en CPU (12 hilos): 14 s el primer pedido, que procesa el prompt de
    unos 1000 tokens; de 4 a 7 s los siguientes, con el prompt en caché. Casi todo el tiempo se va
    en generar el JSON (≈12,8 tokens/s).
  - Dos problemas:
    - En un pedido fuera de alcance completó igual una `accion`; la capa común la descarta y no
      se ejecuta nada.
    - Al repetir el mismo pedido explícito en la misma sesión, el contexto lo confundió y pidió una
      aclaración innecesaria.
  - Gemini no se pudo comparar en esta sesión: la API respondía 503 ("high demand").
- **Documentado en:** [`modelos/llm/README.md`](modelos/llm/README.md), registro de
  [`modelos/README.md`](modelos/README.md) y [`servidor/README.md`](servidor/README.md).
- **Próximo paso:**
  - Reforzar el prompt para que un pedido completo no dependa del contexto de sesión.
  - Probar respuesta JSON compacta para bajar la latencia.
  - Correr la misma batería contra Gemini y Qwen3-4B-Instruct-2507 para tener la primera
    comparación de D3.
  - Evaluar la GPU (runtime de NVIDIA en Docker).

## 2026-08-27 — Creación del repositorio y estructura inicial
- **Fase:** 0 · **Estado:** ✅ Hecho
- **Objetivo:** dejar el proyecto listo para arrancar, con el plan escrito, la arquitectura
  propuesta y las decisiones abiertas identificadas.
- **Actividad:** el director creó el repositorio con `README.md`, `00_PLAN.md`, esta bitácora y los
  documentos de `docs/` en estado inicial. Se fijó la arquitectura en cascada, la separación entre
  el modelo de lenguaje y la capa determinística de traducción, y las cinco decisiones de fase 0
  (D1 a D5).
- **Resultado:** estructura lista. Todo lo grande queda abierto a propósito: instrumento objetivo,
  motor de ASR, modelo de lenguaje, transporte y esquema de intención.
- **Documentado en:** [`00_PLAN.md`](00_PLAN.md) y [`docs/`](docs/).
- **Próximo paso:** arrancar el relevamiento del estado del arte (OE1) y la definición D2, el motor
  de reconocimiento del habla.
