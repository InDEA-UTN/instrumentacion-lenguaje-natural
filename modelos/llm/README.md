# Modelos de lenguaje locales (llama.cpp)

El intérprete local (`INTERPRETE=llama_cpp`) le habla a `llama-server`, que se levanta desde el
`docker-compose.yml` de la raíz del repo. A diferencia de whisper, el contenedor **no descarga el
modelo**: el archivo se baja una vez a esta carpeta.

```bash
curl -L -o modelos/llm/Qwen3.5-4B-Q4_K_M.gguf \
  https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf
docker compose up -d llm
```

Se baja a mano para saber exactamente qué archivo se evaluó, y porque `llama-server -hf` baja
además el módulo de visión (`mmproj`, unos 670 MB), que el intérprete no usa.

Servidor disponible en `http://localhost:8081` (`GET /health` responde 503 mientras carga y 200
cuando está listo).

## Configuración del servicio `llm`

- **Imagen con versión fija** (`server-bNNNN`, no `:server`): la arquitectura de Qwen3.5 es reciente
  y un cambio de versión puede cambiar los resultados. No todas las versiones publican imagen; las
  disponibles están en https://github.com/ggml-org/llama.cpp/pkgs/container/llama.cpp.
- **`--reasoning off`**: Qwen3.5 razona antes de responder por defecto. Para clasificar contra un
  catálogo cerrado solo suma latencia.
- **`-c 8192`**: el prompt (reglas y catálogo) ocupa unos 1000 tokens.

## Probar otro modelo

1. Bajar el `.gguf` a esta carpeta.
2. Cambiar `-m` en el servicio `llm` de [`../../docker-compose.yml`](../../docker-compose.yml) y
   `LLM_MODELO` del servicio `servidor` (solo identifica el modelo en las respuestas y en la bitácora).
3. `docker compose up -d llm servidor` y correr `pytest -m integracion tests/contrato/test_interprete.py`
   desde `servidor/`.
