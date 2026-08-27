# Aplicación de captura — Android

Extremo del sistema con el que interactúa el usuario: captura el audio del pedido, lo envía al
servidor y muestra qué entendió y qué hizo el sistema.

**Estado:** sin implementar. La decisión D4 —el transporte— está abierta
([`../docs/arquitectura.md`](../docs/arquitectura.md)).

## Qué tiene que hacer

1. **Grabar** mientras el usuario mantiene presionado un botón. Se elige presionar y sostener, y no
   una palabra de activación, porque en un laboratorio con gente hablando alrededor una activación
   por voz se dispara sola.
2. **Enviar** el audio al servidor.
3. **Mostrar** las tres cosas, y las tres importan:
   - la **transcripción** — para que el usuario vea si lo escuchó bien;
   - la **acción interpretada**, en lenguaje claro — *"escala vertical del canal 1 a 500 mV/div"*;
   - el **resultado**, leído del instrumento después de ejecutar, no el pedido repetido.
4. **Pedir confirmación** cuando la acción está marcada como sensible o cuando la confianza está
   por debajo del umbral.
5. **Repreguntar** cuando falta un dato, sin perder lo que ya se entendió del pedido.

## Por qué mostrar la transcripción

Es la única forma de que el usuario pueda distinguir un error de transcripción de un error de
interpretación. Si el sistema falla y solo muestra el resultado, el usuario no tiene manera de
saber si le entendió mal las palabras o entendió mal el pedido, y por lo tanto no sabe si repetir
más claro o decirlo de otra forma.

## Decisiones abiertas

| Decisión | Alternativas |
|---|---|
| Transporte (D4) | Archivo completo por HTTP al terminar de hablar, o transmisión por WebSocket durante la grabación. |
| Tecnología | Android nativo (Kotlin) o un entorno multiplataforma. Se define al arrancar la fase 1. |
| Formato y frecuencia de muestreo del audio | Los que requiera el motor de ASR elegido en D2. |
| Descubrimiento del servidor | Dirección fija configurable, o descubrimiento en la red del laboratorio. |
