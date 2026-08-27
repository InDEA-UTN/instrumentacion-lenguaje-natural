# Evaluación

> **Estado: protocolo propuesto.** Se fija en la fase 1, antes de tener resultados. Definir las
> métricas después de ver los números es elegir las que dan bien.

Este documento define **qué se mide, cómo y contra qué**. Es común a todas las etapas: la
comparación entre el modelo comercial de la etapa 1, el modelo ajustado de la etapa 3 y el modelo
multimodal de la etapa 4 solo significa algo si las tres se miden igual.

## 1. Métricas por etapa

La cascada tiene etapas separables, y hay que medirlas por separado antes de medir el conjunto: un
sistema que falla el 20 % de las veces no dice nada sobre **dónde** falla.

### Transcripción (ASR)

| Métrica | Definición |
|---|---|
| **WER** (*word error rate*, tasa de error de palabra) | Proporción de palabras mal transcriptas sobre el total. Métrica estándar. |
| **WER sobre el vocabulario del dominio** | Lo mismo, restringido a los términos técnicos. **Es la que importa acá:** una transcripción con 5 % de WER general pero que se come sistemáticamente la unidad no sirve. |
| Latencia de transcripción | Del fin del audio al texto disponible. |

### Interpretación (modelo de lenguaje)

Se mide sobre texto de referencia, **sin** el ASR, para aislar el error:

| Métrica | Definición |
|---|---|
| **Exactitud de intención** | Proporción de enunciados donde el `tipo` y la `accion` son los correctos. |
| **Exactitud de parámetros** | Proporción de acciones correctas donde además **todos** los parámetros son correctos. Parcialmente bien es mal. |
| **Exactitud conjunta** | Acción y parámetros correctos, sobre el total de enunciados. Es el número que resume la etapa. |
| **Tasa de rechazo correcto** | De los pedidos fuera del catálogo, cuántos se rechazaron. |
| **Tasa de falso rechazo** | De los pedidos válidos, cuántos se rechazaron por error. |
| **Tasa de invención** | Cuántas veces produjo una acción o un parámetro que no existe en el catálogo. **El objetivo es cero:** cualquier valor distinto de cero indica una falla de la restricción de salida, no del modelo. |

### Sistema completo

| Métrica | Definición |
|---|---|
| **Tasa de éxito extremo a extremo** | De los pedidos hablados, cuántos dejaron al instrumento en el estado pedido. Es la métrica que le importa al usuario. |
| **Latencia extremo a extremo** | Del fin del enunciado a la confirmación. Se informa la mediana y el percentil 95, no el promedio. |
| **Tasa de acción incorrecta ejecutada** | Cuántas veces el instrumento quedó en un estado que el usuario no pidió. **Es la métrica crítica:** un error acá es peor que un rechazo, porque el usuario no se entera. |
| **Costo por instrucción** | En la etapa 1, el gasto del servicio comercial. Es el argumento cuantitativo de la etapa 3. |

## 2. Conjunto de prueba

Un conjunto fijo de enunciados con su intención de referencia, construido en la fase 1 y
**congelado**. Cada vez que cambie algo —el modelo, la instrucción, el ASR— se corre el mismo
conjunto y se comparan los números.

Composición mínima:

| Categoría | Proporción orientativa |
|---|---|
| Pedidos bien formulados, de una acción del catálogo | 50 % |
| Pedidos con formulaciones alternativas, sinónimos y unidades distintas | 20 % |
| Pedidos ambiguos, que corresponde repreguntar | 10 % |
| Pedidos fuera del catálogo, que corresponde rechazar | 15 % |
| Pedidos con errores de transcripción verosímiles | 5 % |

**El 25 % que corresponde rechazar o repreguntar no es relleno.** Es la parte que distingue un
sistema confiable de uno que siempre contesta algo.

La versión hablada del conjunto —las mismas frases, grabadas por varias personas distintas— es la
que permite medir el sistema completo y comparar la cascada contra el modelo multimodal. Se graba
en condiciones realistas: el laboratorio con su ruido, no una sala silenciosa.

## 3. Comparación entre arquitecturas (fase 4)

Cascada (ASR + modelo de lenguaje) contra modelo multimodal de voz, sobre el **mismo** conjunto
hablado y las mismas métricas de sistema completo. Se informa también:

- Cuánto del error de la cascada viene de la transcripción y cuánto de la interpretación. Es lo que
  justifica —o no— saltear la etapa de texto.
- Costo y requerimientos de cómputo de cada una.

## 4. Cómo se informan los resultados

Cada corrida queda registrada con la fecha, la versión del conjunto de prueba, la versión de cada
componente y los valores obtenidos. Un resultado sin esas cuatro cosas no es comparable con nada.

Los resultados van a este documento y la entrada correspondiente a
[`../BITACORA.md`](../BITACORA.md), con el enlace.

## 5. Resultados

*(vacío — se completa desde la fase 1)*
