# Instrumentos

Una ficha por instrumento soportado. La ficha es la fuente de verdad de qué se puede pedirle a ese
equipo y con qué límites: la capa de validación no consulta ningún otro lado.

**Estado:** vacío. La decisión D1 —qué instrumento se usa en la etapa 1— está abierta.

## Advertencia sobre el instrumental disponible

Al momento de crear este repositorio, **el inventario del laboratorio no registra ningún
instrumento con interfaz SCPI**. El instrumental cargado es analógico o carece de interfaz de
control remoto.

Esto no frena el proyecto, pero define cómo arranca:

1. La fase 1 se desarrolla contra un **instrumento simulado** (`pyvisa-sim`), declarando el
   comportamiento del equipo objetivo en un archivo YAML. Esto además deja el sistema con pruebas
   automáticas que corren sin hardware — algo que se quiere tener de todos modos.
2. En paralelo, el director gestiona el acceso a un instrumento real: compra, préstamo o uso en
   otra cátedra de la facultad.

Un simulador no reemplaza a la validación sobre hardware real, y la fase 1 no se da por cumplida
sin ella. Sirve para no quedarse quieto mientras tanto.

## Qué lleva la ficha de un instrumento

Un archivo por instrumento, nombrado `fabricante_modelo.md`:

```markdown
# Fabricante Modelo

- **Respuesta a `*IDN?`:** la cadena exacta que devuelve el equipo.
- **Interfaz:** USB / LAN / GPIB / serie. Cadena de recurso VISA.
- **Manual de programación:** enlace. (El PDF no se sube al repositorio.)
- **Versión de firmware verificada:** los rangos pueden cambiar entre versiones.
- **Estado:** verificado sobre hardware / solo simulado.

## Catálogo de acciones

| Acción | Parámetros y rango **verificado** | Plantilla SCPI | Consulta de verificación | Sensible |
|---|---|---|---|---|

## Particularidades

Comandos que el manual documenta y el equipo no acepta, redondeos silenciosos, tiempos de
respuesta largos, y todo lo que se descubra probando y no esté en el manual.

## Simulador

Ruta al archivo de `pyvisa-sim` que imita a este instrumento.
```

La sección de particularidades es la que más valor acumula con el tiempo: es lo que un manual no
dice y que, si no se anota, se vuelve a descubrir a fuerza de perder una tarde.

## Cómo se incorpora un instrumento

El procedimiento —identificar, conseguir el manual de programación, elegir el subconjunto,
**verificar cada comando a mano** y anotar los rangos reales— está en
[`../docs/scpi.md`](../docs/scpi.md), sección 4.
