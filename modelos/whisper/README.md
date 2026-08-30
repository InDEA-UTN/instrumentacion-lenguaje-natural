# Whisper.cpp

Se levanta junto con el resto del sistema desde el `docker-compose.yml` de la raíz del repo:

```bash
docker compose up -d whisper
```

El contenedor descarga el modelo (si no está ya en esta carpeta) y arranca `whisper-server`.

Para probar otro modelo, cambiar `MODEL_NAME` y `MODEL_URL` del servicio `whisper` en
[`../../docker-compose.yml`](../../docker-compose.yml) (los binarios están en
https://huggingface.co/ggerganov/whisper.cpp/tree/main) y volver a levantar.

Servidor disponible en `http://localhost:8080`.
