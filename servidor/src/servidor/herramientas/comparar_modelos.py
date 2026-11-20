"""Compara modelos de cualquier proveedor sobre las mismas frases, para elegir cuál usar.

    python -m servidor.herramientas.comparar_modelos opencode-go/glm-5.3-flash openrouter/z-ai/glm-5.3-flash
    python -m servidor.herramientas.comparar_modelos openrouter      # todos los intérpretes de un proveedor
    python -m servidor.herramientas.comparar_modelos --asr openrouter local --audio a.wav

Los modelos se nombran como en proveedores.yaml: `proveedor/modelo`, o solo `proveedor` para
todos los suyos. Un modelo sin declarar se puede probar con `+`: `openrouter/+qwen/qwen3.8-27b`
usa la configuración del proveedor con ese modelo (para elegir qué agregar al YAML).

Intérprete: cada frase del guion de prueba (interpretacion/fake.py), con su intención esperada, más
una fuera de catálogo. Cuenta aciertos y mide la latencia. Los pedidos son reales y consumen
cupo o crédito del proveedor: 9 por modelo.

ASR (--asr): transcribe cada audio con cada modelo e imprime el texto, para compararlo a oído.

Las claves salen de servidor/.env, como en el servidor.
"""

import argparse
import asyncio
import math
import time
from pathlib import Path

from ..catalogo import cargar_catalogo
from ..config import Configuracion
from ..dominio.errores import ErrorDominio
from ..dominio.modelos import Contexto, Grabacion, Intencion, ModeloInfo, TipoIntencion, Transcripcion
from ..interpretacion.fake import GUION_DEMO
from ..proveedores import DeclModelo, Etapa, ModeloDesconocido, RegistroModelos

CASOS = {**GUION_DEMO, "prendé la cafetera": {"tipo": "fuera_de_alcance"}}
_TEXTO = ModeloInfo(nombre="texto", proveedor="-", version="0", ubicacion="local")


def acierta(intencion: Intencion, esperado: dict) -> bool:
    tipo = esperado["tipo"]
    if tipo in ("aclaracion", "fuera_de_alcance"):
        return intencion.tipo == tipo
    # Preguntar una medición se puede leer como acción o como consulta: las dos la ejecutan igual.
    if intencion.tipo != tipo and not (esperado.get("accion") == "medir" and intencion.tipo in ("accion", "consulta")):
        return False
    if intencion.accion != esperado["accion"]:
        return False
    obtenidos, esperados = intencion.parametros, esperado.get("parametros", {})
    return obtenidos.keys() == esperados.keys() and all(
        math.isclose(obtenidos[k], v) if isinstance(v, float) else str(obtenidos[k]) == str(v)
        for k, v in esperados.items()
    )


def _resumen(i: Intencion) -> str:
    if i.tipo in (TipoIntencion.ACLARACION, TipoIntencion.FUERA_DE_ALCANCE):
        return f"{i.tipo}" + (f" «{i.pregunta}»" if i.pregunta else "")
    return f"{i.tipo} {i.accion}{i.parametros} conf={i.confianza:.2f}"


def expandir(registro: RegistroModelos, etapa: Etapa, nombres: list[str]) -> list[str]:
    """`proveedor` → todos sus modelos de la etapa; `proveedor/+modelo` → se declara al vuelo."""
    ids = []
    for nombre in nombres:
        proveedor_id, _, modelo = nombre.partition("/")
        if not modelo:
            ids += [i for i in registro.ids(etapa, visibles=False) if i.startswith(f"{proveedor_id}/")]
        elif modelo.startswith("+"):
            modelo = modelo[1:]
            proveedor = registro.proveedores[proveedor_id]
            protocolo = {"asr": "transcripciones", "interprete": "chat"}[etapa]
            if etapa == "asr" and proveedor_id == "opencode-go":
                protocolo = "chat_audio"
            proveedor.modelos[modelo] = DeclModelo(etapa=etapa, protocolo=protocolo)
            ids.append(f"{proveedor_id}/{modelo}")
        else:
            ids.append(registro.resolver(etapa, nombre))
    return ids


async def comparar_interpretes(registro: RegistroModelos, ids: list[str], c: Configuracion) -> None:
    catalogo = cargar_catalogo(c.catalogo)
    tabla = []
    for modelo in ids:
        interprete = registro.interprete(modelo)
        print(f"\n== {modelo}")
        aciertos, latencias = 0, []
        for frase, esperado in CASOS.items():
            inicio = time.perf_counter()
            try:
                intencion = await interprete.interpretar(Transcripcion(texto=frase, modelo=_TEXTO), catalogo, Contexto())
                ok, detalle = acierta(intencion, esperado), _resumen(intencion)
            except ErrorDominio as e:
                ok, detalle = False, f"ERROR {type(e).__name__}: {e}"
            latencias.append(time.perf_counter() - inicio)
            aciertos += ok
            print(f"  {'✓' if ok else '✗'} {latencias[-1]:5.1f} s  {frase!r}\n             → {detalle}")
        tabla.append((modelo, aciertos, sorted(latencias)[len(latencias) // 2], max(latencias)))

    print(f"\n{'modelo':<44} {'aciertos':>9} {'mediana':>8} {'máx':>7}")
    for modelo, aciertos, mediana, maximo in tabla:
        print(f"{modelo:<44} {aciertos:>4}/{len(CASOS):<4} {mediana:>6.1f} s {maximo:>5.1f} s")


async def comparar_asr(registro: RegistroModelos, ids: list[str], audios: list[Path]) -> None:
    for audio in audios:
        grabacion = Grabacion(contenido=audio.read_bytes(), nombre=audio.name, formato=audio.suffix.lstrip(".") or "wav")
        print(f"\n== {audio}")
        for modelo in ids:
            try:
                t = await registro.asr(modelo).transcribir(grabacion)
                print(f"  {modelo:<44} {t.latencia_s:5.1f} s  {t.texto!r}")
            except ErrorDominio as e:
                print(f"  {modelo:<44} ERROR {type(e).__name__}: {e}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("modelos", nargs="*", help="intérpretes: proveedor/modelo o proveedor")
    p.add_argument("--asr", nargs="*", default=[], help="transcripción: proveedor/modelo o proveedor")
    p.add_argument("--audio", nargs="*", type=Path, default=[], help="WAV para comparar transcripciones")
    args = p.parse_args()
    c = Configuracion()
    registro = RegistroModelos(c.proveedores)
    try:
        interpretes = expandir(registro, "interprete", args.modelos)
        asrs = expandir(registro, "asr", args.asr)
    except (ModeloDesconocido, KeyError) as e:
        p.error(str(e))
    if not args.modelos and not args.asr:
        p.error("indicá al menos un modelo")
    if args.asr and not args.audio:
        p.error("--asr necesita --audio")
    if interpretes:
        asyncio.run(comparar_interpretes(registro, interpretes, c))
    if asrs:
        asyncio.run(comparar_asr(registro, asrs, args.audio))


if __name__ == "__main__":
    main()
