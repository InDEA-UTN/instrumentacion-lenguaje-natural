"""Adaptadores del puerto Interprete: texto → intención.

Hay uno de prueba (`fake`), uno en la nube (`gemini`) y uno local (`llama_cpp`). Los que usan un
modelo de lenguaje comparten prompt y esquema (`comun.py`). Un modelo nuevo es un archivo acá y una
línea en registro.py.
"""
