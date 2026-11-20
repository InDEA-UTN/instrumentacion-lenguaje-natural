# Front web de prueba

Cliente mínimo para probar el sistema completo desde el navegador: graba el pedido, lo manda al
servidor (`POST /pedidos`) y muestra qué escuchó, qué entendió y qué respondió el instrumento. No es
la app de captura del proyecto (la PWA): es una herramienta de prueba manual.

## Uso

Se levanta junto con el resto del sistema desde la raíz del repo:

```bash
docker compose up -d
```

Abrir `http://localhost:5173` y aceptar el permiso de micrófono. **Mantener presionado** el botón (o
la barra espaciadora) mientras se habla y soltar para enviar. Un toque de menos de 300 ms se
descarta.

- Arriba se ve si el servidor y el instrumento responden (`GET /salud`).
- **Selector de modelos:** para la transcripción y para el intérprete se elige el proveedor (Local,
  OpenCode Go, OpenRouter) y el modelo (`GET /modelos`). La lista sale de
  `servidor/src/servidor/proveedores.yaml`: el front no tiene ninguna propia.
  - ✓ o ✗ indica si cada uno responde. Un modelo sin su clave aparece deshabilitado, con el motivo.
  - Al cambiar de proveedor se elige su modelo predeterminado.
  - La elección se recuerda en el navegador y viaja con cada pedido.
  - **El respaldo es manual:** si un pedido falla porque un proveedor no responde, el error dice
    qué etapa falló, y se elige otro en el selector. "↻ Actualizar disponibilidad" vuelve a
    consultar el estado.
- La tarjeta muestra el último pedido: transcripción, intención, comando SCPI y lectura del
  instrumento, o el motivo del rechazo.
- Una acción sensible o con confianza baja pide **Confirmar / Cancelar**
  (`POST /confirmaciones/{id}`).
- Una **aclaración** se responde grabando de nuevo: el pedido siguiente va en la misma sesión y el
  servidor completa lo que ya había entendido.
- **Nueva sesión** descarta el contexto (canal activo, última intención). Usarla al empezar una
  prueba nueva, para que los pedidos anteriores no influyan.

## Configuración

`VITE_SERVIDOR_URL` cambia la dirección del servidor. Por defecto es
`http://<host de la página>:8000`.

El navegador solo habilita el micrófono en `localhost` o por HTTPS. Desde otro dispositivo de la
red por `http://` lo bloquea; eso queda para la PWA.

## Desarrollo sin Docker

```bash
npm install
npm run dev
```

Requiere el servidor corriendo (`docker compose up -d servidor` desde la raíz, que levanta también
whisper y el modelo de lenguaje).
