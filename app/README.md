# Aplicación de captura — Version preliminar

Version de prueba del front-end hecho para probar las funcionalidades de los modelos y endpoints

## Descripción de las responsabilidades

1. **Grabar** mientras el usuario mantiene presionado un botón. Se elige presionar y sostener, y no
   una palabra de activación, porque en un laboratorio con gente hablando alrededor una activación
   por voz se dispara sola.
2. **Enviar** el audio al servidor.
3. **Mostrar** tres cosas:
   - la **transcripción** — para que el usuario vea si lo escuchó bien;
   - la **acción interpretada**, en lenguaje claro — _"escala vertical del canal 1 a 500 mV/div"_;
   - el **resultado**, leído del instrumento después de ejecutar, no el pedido repetido.
4. **Pedir confirmación** cuando la acción está marcada como sensible o cuando la confianza está
   por debajo del umbral.
5. **Repreguntar** cuando falta un dato, sin perder lo que ya se entendió del pedido.
