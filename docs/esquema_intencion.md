# Esquema de intención

> **Estado: propuesta inicial (D5).** La forma concreta se fija en la fase 0. Lo que sigue es el
> punto de partida para discutirla, no una especificación cerrada.

La **intención** es el objeto que el modelo de lenguaje produce y que la capa de validación
consume. Es el contrato que separa lo probabilístico de lo determinístico
([`arquitectura.md`](arquitectura.md), sección 2) y, por lo tanto, el documento más importante del
proyecto: mientras el contrato no cambie, se puede reemplazar el modelo sin tocar la ejecución, y
al revés.

## 1. Forma general

```json
{
  "tipo": "accion",
  "accion": "configurar_escala_vertical",
  "parametros": { "canal": 1, "valor": 0.5 },
  "confianza": 0.94,
  "enunciado": "poné el canal uno en quinientos milivoltios por división"
}
```

| Campo | Para qué |
|---|---|
| `tipo` | `accion`, `consulta`, `aclaracion` o `fuera_de_alcance`. Ver la sección 3. |
| `accion` | Identificador de una acción del catálogo. **Cerrado**: si no está en el catálogo, no existe. |
| `parametros` | Los argumentos de esa acción, ya normalizados a unidades del Sistema Internacional y **sin unidad**: la unidad la fija la definición del parámetro en el catálogo, así el modelo no puede equivocarse en ella. |
| `confianza` | Estimación del modelo sobre su propia interpretación. Por debajo de un umbral se pide confirmación en vez de ejecutar. |
| `enunciado` | La transcripción original. Se conserva para la trazabilidad y para el conjunto de datos de la etapa 3. |

### Contexto de la conversación

El modelo recibe, además del enunciado, el **contexto**: el canal activo, la última intención y, si
la hubo, la aclaración pendiente. Es lo que permite interpretar *"subilo un poco"* o completar un
pedido después de repreguntar sin perder lo ya entendido. Su forma está en
[`modelo_dominio.md`](modelo_dominio.md).

## 2. Definición de una acción

Cada acción del catálogo se declara una sola vez, con todo lo que la capa de validación necesita
para decidir sin consultar a nadie:

```yaml
configurar_escala_vertical:
  descripcion: Fija los volt por división de un canal vertical.
  parametros:
    canal:
      tipo: entero
      rango: [1, 4]
      obligatorio: true
    valor:
      tipo: real
      unidad: V
      rango: [1.0e-3, 10.0]
      obligatorio: true
  plantilla_scpi: ":CHANnel{canal}:SCALe {valor}"
  verificacion_scpi: ":CHANnel{canal}:SCALe?"
  sensible: false
  ejemplos:
    - poné el canal uno en quinientos milivoltios por división
    - subí la escala vertical del canal dos a un volt
    - canal 1 a 50 milivolt
```

Sobre tres campos que no son obvios:

- **`verificacion_scpi`** — la consulta que se emite después de escribir, para informarle al usuario
  cómo quedó **realmente** el instrumento y no cómo se le pidió que quedara.
- **`sensible`** — marca las acciones que requieren confirmación explícita antes de ejecutarse:
  las que pueden dañar el instrumento o el circuito bajo prueba, o las que descartan trabajo del
  usuario. Habilitar una salida del generador con amplitud alta es sensible; cambiar la escala
  vertical del osciloscopio no lo es.
- **`ejemplos`** — no son decorativos. Alimentan la instrucción del modelo en la etapa 1 y son la
  semilla del conjunto de datos de la etapa 3 ([`dataset.md`](dataset.md)).

## 3. Los cuatro tipos de intención

Un sistema que solo sabe ejecutar es un sistema que ejecuta cualquier cosa. Los cuatro tipos
existen para que "no entendí" y "no puedo" sean respuestas legítimas y no un ajuste forzado a la
acción más parecida:

| Tipo | Cuándo | Qué hace el sistema |
|---|---|---|
| `accion` | El pedido corresponde a una acción del catálogo y están todos sus parámetros. | Valida y ejecuta. |
| `consulta` | El usuario pregunta el estado actual ("¿en cuánto está la base de tiempo?"). | Consulta al instrumento y responde. No modifica nada. |
| `aclaracion` | El pedido es reconocible pero le falta un dato ("subí la escala" — ¿de qué canal?). | Repregunta y espera. |
| `fuera_de_alcance` | El pedido no corresponde a ninguna acción del catálogo. | Lo dice explícitamente y **no ejecuta nada**. |

**La regla que no se negocia:** ante la duda, `aclaracion` o `fuera_de_alcance`. Nunca la acción
más parecida. Un sistema que adivina es peor que uno que pregunta, porque el usuario deja de poder
confiar en él.

## 4. Cómo se convierte esto en la interfaz del modelo

Las declaraciones de acción son la única fuente de verdad. De ellas se derivan, sin escribirlas dos
veces:

1. Las **herramientas** que se le declaran al modelo de lenguaje, con sus parámetros tipados.
2. Las **validaciones** de la capa determinística: obligatoriedad, tipos y rangos.
3. Las **plantillas SCPI** que se instancian para armar el comando.
4. Los **casos de prueba** del catálogo.

Que todo salga del mismo archivo es lo que evita el error clásico: agregar una acción, olvidarse de
agregarle la validación, y descubrirlo cuando el instrumento recibe un valor imposible.

## 5. Catálogo de la etapa 1

Entre cinco y diez acciones sobre un solo instrumento. El catálogo concreto se fija junto con la
decisión D1 y se documenta en [`scpi.md`](scpi.md) y en la ficha del instrumento en
[`../instrumentos/`](../instrumentos/).
