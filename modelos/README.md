# Modelos

Directorio para los archivos de los modelos con los que se experimenta —motores de ASR, y más
adelante modelos de lenguaje locales de la fase 3—. Es insumo de la decisión **D2**
([`../docs/estado_del_arte.md`](../docs/estado_del_arte.md)) y de la fase 3
([`../docs/dataset.md`](../docs/dataset.md)).

**Los binarios no se versionan** (ver `../.gitignore`): pesan demasiado para git y se pueden volver
a descargar. Lo que sí se versiona acá es de dónde sale cada uno y qué se midió.

## Organización

Una carpeta por familia de modelo, por ejemplo:

```
modelos/
├── whisper/          # binarios de whisper.cpp (.bin), ignorados por git
└── README.md
```

## Registro de modelos probados

| Modelo                                       | Familia | De dónde sale | Para qué | Resultado |
| -------------------------------------------- | ------- | ------------- | -------- | --------- |
| _(vacío — se completa al probar el primero)_ |         |               |          |           |

Cada fila enlaza, cuando corresponda, a la entrada de [`../BITACORA.md`](../BITACORA.md) donde se
registró la prueba y a los números en [`../docs/evaluacion.md`](../docs/evaluacion.md).
