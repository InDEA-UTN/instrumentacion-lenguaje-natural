# Documentación del proyecto

Un documento por tema, y cada tema en un solo documento. Si algo ya está escrito en otro lado, acá
va el enlace y no la copia: de dos copias, una siempre queda desactualizada.

| Documento | De qué trata |
|---|---|
| [`arquitectura.md`](arquitectura.md) | Las etapas de la cascada, qué hace cada una, las alternativas evaluadas y las decisiones abiertas. |
| [`esquema_intencion.md`](esquema_intencion.md) | El contrato entre el modelo de lenguaje y la capa de ejecución: qué forma tiene una intención y cómo se valida. |
| [`modelo_dominio.md`](modelo_dominio.md) | Entidades del servidor, la interfaz común de los modelos (ASR, LLM) y cómo se intercambian por configuración. |
| [`scpi.md`](scpi.md) | Qué es SCPI, cómo se descubre el conjunto de comandos de un instrumento, y el catálogo acotado de la etapa 1. |
| [`estado_del_arte.md`](estado_del_arte.md) | Relevamiento de antecedentes: trabajos previos, modelos de reconocimiento del habla y bibliotecas de instrumentación. |
| [`dataset.md`](dataset.md) | Plan de construcción del conjunto de datos y de ajuste fino del modelo abierto (etapa 3). |
| [`evaluacion.md`](evaluacion.md) | Qué se mide, cómo y contra qué. Protocolo experimental común a todas las etapas. |

Los documentos se escriben **en español**, expandiendo las siglas la primera vez que aparecen, y se
actualizan en el mismo pull request que el trabajo que documentan.
