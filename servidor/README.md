# Servidor

Corazón del sistema: recibe el audio, lo transcribe, lo interpreta, **valida** el resultado y
ejecuta el comando contra el instrumento.

**Estado:** sin implementar. Las decisiones D2, D3 y D4 están abiertas
([`../docs/arquitectura.md`](../docs/arquitectura.md)).

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
pip install -r requirements.txt   # cuando exista
```

Las dependencias se fijan al arrancar la fase 1, una vez cerradas D2 y D3.
