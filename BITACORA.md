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
