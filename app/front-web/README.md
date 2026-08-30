# Front web de prueba

Cliente mínimo para probar el servicio de transcripción (whisper.cpp) grabando audio desde el
navegador. No es la app Android del proyecto: es una herramienta de testing manual para la fase 0
(decisión D2).

## Uso

Se levanta junto con whisper.cpp desde la raíz del repo:

```bash
docker compose up -d
```

Abrir `http://localhost:5173`, aceptar el permiso de micrófono, presionar "Grabar", hablar,
presionar "Detener". El audio se envía como WAV a `POST http://localhost:8080/inference` y se
muestra la transcripción devuelta.

## Desarrollo sin Docker

```bash
npm install
npm run dev
```

Requiere el servicio de whisper corriendo (`docker compose up -d whisper` desde la raíz).
