"""Adaptadores del puerto Interprete (texto → intención), uno por protocolo.

`chat` (API de OpenAI: llama.cpp, OpenCode Go, OpenRouter), `gemini` y `fake` (guion fijo). Los que
usan un modelo de lenguaje comparten prompt y esquema (`comun.py`). Qué modelos y proveedores hay
se declara en ../proveedores.yaml; un protocolo nuevo es un archivo acá y una línea en
../proveedores.py.
"""
