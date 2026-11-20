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
| `GET /salud` | Qué modelo hay detrás de cada puerto y si responde. |
| `POST /pedidos` | Audio (`multipart`, campo `audio`; opcional `sesion`) → `Interaccion`. |
| `POST /confirmaciones/{id}` | `{"aceptar": true}` ejecuta una acción que quedó pendiente de confirmación. |

Los modelos se eligen por variables de entorno (ver `src/servidor/config.py`): `ASR_MOTOR`
(`whisper_cpp`, `fake`), `ASR_URL`, `INTERPRETE` (`fake`, `gemini`, `llama_cpp`), `GEMINI_API_KEY`,
`GEMINI_MODELO`, `LLM_URL`, `LLM_MODELO`, `LLM_TIMEOUT_S`, `CATALOGO`, `UMBRAL_CONFIANZA`,
`INSTRUMENTO` (`fake`, `visa`) y las `VISA_*` de la sección siguiente. El
docker-compose usa `llama_cpp`; el modelo local se baja a mano (ver
[`../modelos/llm/README.md`](../modelos/llm/README.md)). Para desarrollo local van en `servidor/.env`, que
no se versiona.

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

La línea de salud del front pasa a decir "TBS1072B ✓ conectado". Qué hace la conexión:

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

1. Un archivo en `transcripcion/` o `interpretacion/` con una clase que cumpla `MotorASR` o
   `Interprete` ([`src/servidor/dominio/puertos.py`](src/servidor/dominio/puertos.py)).
2. Una línea en `MOTORES_ASR` o `INTERPRETES` de [`src/servidor/registro.py`](src/servidor/registro.py).
3. Agregarlo a `IMPLEMENTACIONES` del test de contrato correspondiente en `tests/contrato/` y que pase.

Nada más cambia: ni la validación, ni la ejecución, ni la API.
