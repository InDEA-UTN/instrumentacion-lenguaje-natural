# Conjunto de datos y ajuste fino

> **Estado: plan (fase 3).** Todavía no se recolectó nada. Este documento fija cómo se va a hacer,
> para que la recolección de la fase 2 sirva y no haya que rehacerla.

## 1. Por qué un modelo propio

La etapa 1 usa un modelo comercial de pago porque es el camino más corto a un prototipo que
funcione. No es el destino:

- **Costo.** Cada instrucción hablada es una consulta paga. Un laboratorio de docencia con varios
  puestos multiplica eso por todo el cuatrimestre.
- **Dependencia.** El sistema deja de funcionar si se cae el servicio, si cambia el modelo detrás
  de la misma versión, o si se corta internet en el laboratorio.
- **Latencia.** Un modelo local en la red del laboratorio responde con latencia previsible.
- **Aporte académico.** Mostrar que un modelo abierto de unos 4 mil millones de parámetros,
  ajustado sobre un conjunto de datos propio, iguala a un modelo comercial mucho mayor **en esta
  tarea acotada** es un resultado publicable. Reproducirlo con el modelo comercial no lo es.

## 2. Qué es un ejemplo

Un par *(enunciado, intención)*, más el contexto necesario para desambiguar:

```json
{
  "enunciado": "poné el canal uno en quinientos milivoltios por división",
  "instrumento": "osciloscopio_generico_4ch",
  "contexto": { "canal_activo": 1 },
  "intencion": {
    "tipo": "accion",
    "accion": "configurar_escala_vertical",
    "parametros": { "canal": 1, "valor": 0.5, "unidad": "V" }
  }
}
```

El campo `contexto` importa más de lo que parece: *"subilo un poco"* solo tiene sentido si se sabe
qué se tocó recién. Sin contexto, ese ejemplo es ruido; con contexto, es de los más valiosos del
conjunto, porque es como habla la gente de verdad.

## 3. De dónde salen los ejemplos

Tres fuentes, y las tres son necesarias:

| Fuente | Aporta | Riesgo |
|---|---|---|
| **Enunciados reales**, registrados durante el uso del prototipo en la fase 2. | El vocabulario que la gente usa de verdad, con sus muletillas, sus elipsis y sus errores. | Son pocos y cuestan tiempo de recolección. |
| **Variaciones escritas a mano** de los ejemplos declarados en el catálogo. | Cobertura sistemática de todas las acciones y de los casos que nadie pidió todavía. | Sesgo del que las escribe: suenan a manual, no a persona. |
| **Generación sintética** a partir de las plantillas, con un modelo grande y variación controlada de sinónimos, unidades y orden. | Volumen. | Empobrecimiento: si el modelo grande tiene un tic, queda impreso en todo el conjunto. |

**Los tres tercios no valen lo mismo.** Los enunciados reales son los que hay que cuidar, y son la
única razón por la que la fase 2 tiene que registrar lo que la gente dice. Se etiqueta el origen de
cada ejemplo, para poder medir cuánto aporta cada fuente.

## 4. Qué tiene que cubrir

Un conjunto de datos que solo tenga pedidos bien formulados produce un modelo que no sabe decir que
no. Tienen que estar representados:

- Las cuatro clases de intención, incluyendo `aclaracion` y `fuera_de_alcance`
  ([`esquema_intencion.md`](esquema_intencion.md)).
- **Pedidos fuera del catálogo**, con su respuesta correcta: el rechazo.
- **Pedidos ambiguos**, con su repregunta correcta.
- **Errores de transcripción** verosímiles, del tipo que produce el ASR elegido en D2. El modelo va
  a recibir texto de un ASR, no texto perfecto: entrenarlo solo con texto limpio es entrenarlo para
  una entrada que nunca va a ver.
- Variantes de unidades y de forma: *"quinientos milivoltios"*, *"500 mV"*, *"medio volt"*, *"0,5
  volt"*.

## 5. Partición y disciplina experimental

| Partición | Proporción orientativa | Para qué |
|---|---|---|
| Entrenamiento | 70 % | Ajuste del modelo. |
| Validación | 15 % | Selección de hiperparámetros y punto de corte del entrenamiento. |
| Prueba | 15 % | Medición final. **Se toca una sola vez.** |

Dos reglas que se fijan ahora para no discutirlas después:

1. **La partición de prueba se define antes de entrenar y no se mira hasta el final.** Un conjunto
   de prueba consultado varias veces deja de medir generalización y pasa a medir cuántas veces se
   lo consultó.
2. **La partición es por enunciado original, no por ejemplo.** Si un enunciado real generó cinco
   variantes sintéticas, las seis van a la misma partición. Repartirlas es filtrar la prueba dentro
   del entrenamiento y obtener un resultado que no significa nada.

## 6. Modelo y procedimiento de ajuste

*(A definir en la fase 3.)* Candidatos: Qwen3-4B, Gemma 3 4B o equivalente. Criterios de selección:
soporte de llamada a herramientas de fábrica, desempeño en español, licencia y viabilidad en el
hardware del laboratorio.

Técnica prevista: ajuste fino eficiente en parámetros (LoRA o similar), que evita reentrenar el
modelo completo y permite hacerlo con el hardware disponible.

Todo lo que se necesite para reproducir el resultado —versión del modelo base, hiperparámetros,
semilla, versión del conjunto de datos— se versiona junto con el modelo ajustado. Un resultado que
no se puede reproducir no es un resultado.

## 7. Publicación

El conjunto de datos es un producto del proyecto por derecho propio y se publica con el
repositorio, siempre que:

- No contenga datos personales identificables de quienes prestaron su voz.
- Se documente cómo se construyó y qué proporción es real, escrita y sintética.
- Se registre el consentimiento de los participantes para el uso de sus grabaciones.
