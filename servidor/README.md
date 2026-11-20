# Servidor

Corazón del sistema: recibe el audio, lo transcribe, lo interpreta, **valida** el resultado y
ejecuta el comando contra el instrumento.

**Estado:** funcionando de punta a punta con whisper.cpp, un intérprete local (Qwen3.5-4B sobre
llama.cpp, prueba de concepto) y un instrumento en memoria. Gemini y un intérprete de prueba (guion
fijo) siguen disponibles. La elección del intérprete es D3, y el instrumento real espera a D1
([`../docs/arquitectura.md`](../docs/arquitectura.md)). El modelo de dominio y la interfaz común de
los modelos están en [`../docs/modelo_dominio.md`](../docs/modelo_dominio.md).

## Módulos previstos

Uno por etapa de la cascada, con las fronteras en el mismo lugar que en el diseño. Cada módulo se
puede reemplazar sin tocar los otros; ese es el punto.

| Módulo | Responsabilidad | Entrada → salida |
|---|---|---|
| `transcripcion` | Reconocimiento automático del habla. | audio → texto |
| `interpretacion` | Modelo de lenguaje con el catálogo de acciones declarado. | texto → intención |
| `catalogo` | Declaración de las acciones por instrumento: parámetros, rangos y plantillas SCPI. | — |
| `validacion` | Verificación de existencia, obligatoriedad, unidades y rangos. | intención → comando o rechazo |
| `ejecucion` | Comunicación con el instrumento por PyVISA, y verificación posterior. | comando → estado real |
| `api` | Interfaz con la aplicación. | — |

**`catalogo` es la fuente de verdad de todo el sistema.** De sus declaraciones salen las
herramientas que se le presentan al modelo, las validaciones, las plantillas SCPI y los casos de
prueba ([`../docs/esquema_intencion.md`](../docs/esquema_intencion.md)). Nada de eso se escribe dos
veces.

## Reglas de implementación

Estas no son preferencias de estilo: son las que sostienen el diseño.

1. **`validacion` y `ejecucion` no conocen al modelo de lenguaje.** Reciben una intención y no
   saben ni les importa de dónde salió. Se prueban sin modelo y sin instrumento.
2. **Ninguna cadena SCPI se arma fuera de `catalogo`.** Si aparece un comando escrito a mano en
   otro módulo, es un agujero en la validación.
3. **Después de escribir, se lee.** Toda escritura va seguida de su consulta de verificación, y lo
   que se le informa al usuario es lo que respondió el instrumento.
4. **Fallar es una salida válida.** Rechazar con un mensaje claro es correcto; aproximar al comando
   más parecido, nunca.
5. **Las credenciales van en variables de entorno.** El repositorio es público. Ninguna clave de
   interfaz de programación de aplicaciones (API) entra al código ni a un archivo versionado.

## Entorno de desarrollo

El entorno virtual de Python **no se crea dentro del repositorio**. La convención del laboratorio
es tenerlos en una carpeta aparte, fuera de cualquier directorio sincronizado con la nube.

```bash
python3 -m venv ~/Documents/entornos/instrumentacion-lenguaje-natural
source ~/Documents/entornos/instrumentacion-lenguaje-natural/bin/activate
pip install -e '.[dev]'
```

Si el Python del sistema no trae `ensurepip`, `uv venv` y `uv pip install -e '.[dev]'` hacen lo mismo.

## Uso

```bash
pytest                                   # contrato, validación y pipeline, sin modelo ni instrumento
pytest -m integracion                    # además whisper.cpp (docker compose up -d whisper)
uvicorn servidor.api.app:app --reload    # API en http://localhost:8000/docs
```

O todo junto desde la raíz: `docker compose up -d` (servidor en el puerto 8000).

| Endpoint | Qué hace |
|---|---|
| `GET /salud` | Los modelos predeterminados, el instrumento y si responden. |
| `GET /salud/instrumento` | Solo el instrumento: le pregunta `*IDN?` en el momento y, si respondió, con qué equipo habló (`idn_conectado`, `recurso_conectado`). El front lo consulta cada 5 s. |
| `GET /modelos` | Por etapa, los proveedores con sus modelos y si están disponibles (el selector del front). `?refrescar=true` no usa la consulta guardada (30 s). |
| `POST /pedidos` | Audio (`multipart`, campo `audio`; opcionales `sesion`, `asr` e `interprete` con un `proveedor/modelo` de `/modelos`) → `Interaccion`. Un modelo no declarado da 422. |
| `POST /confirmaciones/{id}` | `{"aceptar": true}` ejecuta una acción que quedó pendiente de confirmación. |

Qué modelos hay se declara en [`src/servidor/proveedores.yaml`](src/servidor/proveedores.yaml)
(sección siguiente). Las variables de entorno (ver `src/servidor/config.py`) eligen los
predeterminados, `ASR_MOTOR` e `INTERPRETE`, que se usan cuando el pedido no elige otro. Además
están `CATALOGO`, `UMBRAL_CONFIANZA`, `INSTRUMENTO` (`fake`, `visa`) y las `VISA_*` de "Conectar
el osciloscopio real". Las claves van en `servidor/.env`, que no se versiona. El modelo local se
baja a mano (ver [`../modelos/llm/README.md`](../modelos/llm/README.md)).

## Proveedores y modelos

El front tiene un selector de proveedor y modelo para cada etapa. **El respaldo es manual:** si un
proveedor se cae o no anda, se elige otro ahí. Hoy hay tres:

| Proveedor | Transcripción | Intérprete | Clave |
|---|---|---|---|
| **Local** | whisper-small (whisper.cpp) | Qwen3.5-4B (llama.cpp) | No tiene |
| **OpenCode Go** (suscripción) | mimo-v2.6 (modelo de chat con audio) | glm-5.3, claude-haiku-5-5, qwen3.8-max, kimi-k3 | `OPENCODE_API_KEY` |
| **OpenRouter** (crédito prepago) | whisper-large-v3-turbo, gpt-4o-mini-transcribe, voxtral | glm-5.3-flash, gpt-5.4-mini, gemini-3.8-flash, qwen3.8-flash, mistral-small, nemotron (gratis) | `OPENROUTER_API_KEY` |

### Cómo está armado

Hay tres cosas separadas:

- **Protocolo:** cómo se le habla a una API. Es código, con un adaptador por protocolo.
- **Proveedor:** dónde está la API (URL, clave, cabeceras). Es configuración.
- **Modelo:** un modelo concreto de un proveedor para una etapa, con sus particularidades. Es configuración.

| Etapa | Protocolo | Adaptador | Lo usan |
|---|---|---|---|
| Intérprete | `chat` | [`interpretacion/chat.py`](src/servidor/interpretacion/chat.py) | Local, OpenCode, OpenRouter |
| Intérprete | `gemini` | [`interpretacion/gemini.py`](src/servidor/interpretacion/gemini.py) | Google directo (oculto en el front) |
| ASR | `whisper_cpp` | [`transcripcion/whisper_cpp.py`](src/servidor/transcripcion/whisper_cpp.py) | Local |
| ASR | `chat_audio` | [`transcripcion/chat_audio.py`](src/servidor/transcripcion/chat_audio.py) | OpenCode |
| ASR | `transcripciones` | [`transcripcion/transcripciones.py`](src/servidor/transcripcion/transcripciones.py) | OpenRouter |

El cliente HTTP común está en [`src/servidor/clientes.py`](src/servidor/clientes.py), y el
registro que lee el YAML y arma los adaptadores, en
[`src/servidor/proveedores.py`](src/servidor/proveedores.py). Cada modelo se nombra
`proveedor/modelo`, por ejemplo `openrouter/z-ai/glm-5.3-flash`. Ese nombre es el que manda el
front, el que guarda la traza y el que recibe el comparador.

### Qué cambiar según el caso

- **Cambiar o sumar un modelo** de un proveedor que ya está: una línea en `proveedores.yaml`.
- **Un modelo que necesita un ajuste** (más tiempo de espera, razonamiento apagado, un parámetro
  que no admite): sus `parametros` en el YAML. Un parámetro en `null` no se manda.
- **Un proveedor nuevo** que hable un protocolo conocido: un bloque en el YAML y su clave en
  `servidor/.env`. Casi todos hablan `chat` (la API de OpenAI), y muchos también `transcripciones`.
- **Un protocolo nuevo:** un adaptador que cumpla `MotorASR` o `Interprete`
  ([`src/servidor/dominio/puertos.py`](src/servidor/dominio/puertos.py)) y una línea en
  `PROTOCOLOS_ASR` o `PROTOCOLOS_INTERPRETE` de `proveedores.py`.

En ningún caso cambian la validación, la ejecución ni la API. El YAML no lleva claves, porque el
repositorio es público: `clave` es el *nombre* de la variable de entorno que la tiene.

### Elegir los predeterminados

```bash
# Con Docker (desde la raíz). Sin variables: local/whisper-small y local/qwen3.5-4b.
INTERPRETE=openrouter docker compose up -d servidor   # el predeterminado de OpenRouter
ASR_MOTOR=opencode-go/mimo-v2.6-flash INTERPRETE=opencode-go/glm-5.3-flash docker compose up -d servidor
```

`ASR_MOTOR` e `INTERPRETE` aceptan `proveedor/modelo`, solo `proveedor` (su predeterminado) o los
nombres de antes (`whisper_cpp`, `llama_cpp`, `opencode`, `gemini`, `fake`).

### Particularidades encontradas al probar (2026-11-20)

- **El chat de OpenCode Go y OpenRouter.** Todos los intérpretes reciben el mismo prompt y el mismo
  esquema como salida estructurada. Si un modelo no admite `response_format`, se reintenta sin él.
  Si el proveedor responde 400 por otra causa (por ejemplo, una región no habilitada), se sigue
  usando el esquema.
- **OpenRouter:**
  - `require_parameters: true` hace que solo rutee a proveedores que respeten el esquema.
  - `max_tokens: 4096` evita un 402: sin ese tope, reserva crédito para la salida máxima del
    modelo, de 65 000 a 131 000 tokens.
  - A veces responde 200 con el error en el cuerpo, y el cliente lo trata como error.
  - `gpt-5.4-mini` no admite `temperature`.
  - `glm` y `gemini` razonan siempre, así que se les pide el menor esfuerzo.
  - La transcripción exige al menos US$ 0,50 de saldo. Con saldo, `whisper-large-v3-turbo`
    transcribe en unos 2 s y es fiel con un pedido cortado. `gpt-4o-mini-transcribe`, en cambio,
    completó un número que no se dijo.
- **whisper local** escribe una anotación con silencio o ruido ("[MÚSICA]", "[Sonido de la
  ventana]"). El adaptador borra lo que va entre corchetes, paréntesis o asteriscos, así el silencio
  da texto vacío.
- **El ASR de OpenCode Go** es un modelo de lenguaje y no whisper:
  - **Con silencio o ruido inventaba un pedido completo.** Las instrucciones le dan una salida
    explícita (`[inaudible]`), que se convierte en texto vacío, y el pipeline rechaza una
    transcripción vacía sin llamar al intérprete.
  - Con el razonamiento prendido, mimo deja la respuesta vacía.
  - `gemini-4-argon` no anda por esta API.
- **Disponibilidad.** Un modelo está disponible si tiene su clave y figura en el listado del
  proveedor, o si responde su `salud_url` (llama.cpp). No se prueba la clave ni el saldo: eso
  costaría un pedido. Una clave inválida o la falta de saldo aparecen en el primer pedido, como un
  503 que dice qué etapa falló.
- **Uso de OpenCode Go.** Go está pensado para agentes de programación. Algunos modelos piden
  habilitar regiones en la consola (DeepSeek: "Global"). Los `*-contributor` entrenan con los
  datos enviados: no usarlos con grabaciones reales.
- **Privacidad.** Con un proveedor en la nube, el audio y el texto salen del laboratorio.

### Comparar modelos

El comparador corre las nueve frases del guion de prueba contra cada modelo, cuenta aciertos y
mide la latencia. Son nueve pedidos por modelo:

```bash
python -m servidor.herramientas.comparar_modelos opencode-go/glm-5.3-flash openrouter/z-ai/glm-5.3-flash
python -m servidor.herramientas.comparar_modelos openrouter            # todos los intérpretes de OpenRouter
python -m servidor.herramientas.comparar_modelos "openrouter/+qwen/qwen3.8-27b"   # uno sin declarar, para evaluarlo
python -m servidor.herramientas.comparar_modelos --asr local opencode-go openrouter --audio ../modelos/audio_ejemplos/*.wav
```

Las pruebas de contrato recorren todos los modelos declarados: `pytest -m integracion`, o uno
solo con `-k "openrouter/z-ai"`. Un modelo sin clave o que no responde se saltea.

## Conectar el osciloscopio real

Con `INSTRUMENTO=visa`, el servidor habla con el equipo por PyVISA
([`src/servidor/ejecucion/visa.py`](src/servidor/ejecucion/visa.py)). Usa pyvisa-py, que no
necesita los drivers del fabricante.

```bash
# Con Docker: el contenedor ve el bus USB del host.
INSTRUMENTO=visa docker compose up -d servidor

# Sin Docker: hace falta el extra `visa` y permiso sobre el USB (ver abajo).
pip install -e '.[visa]'
INSTRUMENTO=visa uvicorn servidor.api.app:app
```

La línea del instrumento en el front pasa a decir "TBS1072B ✓ conectado", con el número de serie y
el firmware. Se actualiza sola cada 5 s, así que se ve enchufarlo o desenchufarlo sin recargar.
Al pasar el mouse muestra la respuesta completa a `*IDN?` y la cadena VISA, que hay que anotar en
la ficha del instrumento. Qué hace la conexión:

- **Busca el equipo sola.** Pregunta `*IDN?` a cada instrumento USB y elige el que nombra el
  `modelo` del catálogo. `VISA_RECURSO` fija la cadena VISA si hace falta. Con un modelo
  distinto no se conecta: un catálogo del TBS1072B no le manda comandos a otro equipo.
- **Al abrir envía `*CLS` y `HEADer OFF`** (`VISA_AL_CONECTAR`), para que las consultas devuelvan
  solo el valor.
- **Después de cada mensaje lee `*ESR?`.** Si el equipo marcó un error, el pedido queda rechazado
  con el detalle de `ALLEv?` (`VISA_CONSULTA_EVENTOS`). Una medición que devuelve `9.9E37` también
  se rechaza: significa que no hubo dato.
- **Un pedido a la vez.** La escritura y su verificación no se intercalan con otro pedido.
- **Arranca y se reconecta sola.** El servidor arranca sin el equipo enchufado; si se pierde la
  comunicación, el próximo pedido reabre. Mientras no haya equipo, un pedido responde 503.
- `VISA_TIMEOUT_MS` vale 10 s por defecto, porque el autoset tarda unos segundos.

**Permisos sobre el USB, solo sin Docker.** Por defecto, un usuario común no puede abrir el
dispositivo. Se habilita una vez con una regla de udev para los equipos Tektronix (fabricante
`0699`) y se reconecta el cable:

```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0699", MODE="0660", GROUP="plugdev"' \
  | sudo tee /etc/udev/rules.d/99-tektronix.rules
sudo udevadm control --reload-rules
```

**Simulador.** [`src/servidor/simuladores/tektronix_tbs1072b.yaml`](src/servidor/simuladores/tektronix_tbs1072b.yaml)
imita al equipo con pyvisa-sim. Lo usan los tests de `tests/test_visa.py`, y sirve para probar el
camino PyVISA a mano:

```bash
INSTRUMENTO=visa VISA_BACKEND="$PWD/src/servidor/simuladores/tektronix_tbs1072b.yaml@sim" uvicorn servidor.api.app:app
```

## Cómo agregar un modelo

Ver "Qué cambiar según el caso" en la sección "Proveedores y modelos". Un modelo declarado entra
solo en los tests de contrato (`tests/contrato/`), y tiene que pasarlos con `pytest -m integracion`.
