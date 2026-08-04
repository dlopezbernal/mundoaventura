"""
backend/logging_config.py — Configuración central de logging del backend
========================================================================

Un único punto para configurar el logging de todo el backend (servidor y scripts
CLI como `python -m backend.ingest`). Sustituye a las llamadas sueltas de consola
que había antes por `logging`, con estas ventajas:

  - Cada mensaje lleva marca de tiempo, nivel y el módulo que lo emite.
  - El nivel se controla por la variable de entorno LOG_LEVEL (DEBUG/INFO/
    WARNING/ERROR), sin tocar código.
  - Se silencia el ruido de las librerías de terceros (chromadb, httpx…), que en
    DEBUG llenarían la consola.

Relación con el ajuste DEBUG (settings_service, editable en caliente): DEBUG es un
flag de PRODUCTO (traza los prompts del RAG y muestra las fuentes al niño), no el
nivel de logging. Para que al activar DEBUG se vean también esas trazas por
consola, `aplicar_nivel_debug()` pone el logger `backend` en DEBUG mientras DEBUG
esté activo, y set_many lo resincroniza al cambiarlo (así el toggle en caliente
sigue surtiendo efecto sin reiniciar).
"""

import logging
import os

# Loggers de terceros que en DEBUG son puro ruido: se fijan a WARNING.
_TERCEROS_RUIDOSOS = (
    "chromadb",
    "httpx",
    "httpcore",
    "urllib3",
    "hpack",
    "watchfiles",
    # El SDK de DeepL loguea cada request/response HTTP a INFO; es redundante con
    # nuestra propia traza (debug_log) y ensucia la consola en cada pregunta.
    "deepl",
)

_FORMATO = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_FECHA = "%H:%M:%S"


def nivel_por_defecto() -> int:
    """Nivel base de logging desde LOG_LEVEL (por defecto INFO)."""
    nombre = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, nombre, logging.INFO)


def configurar_logging() -> None:
    """Configura el logging raíz. Idempotente: llamar una vez al arrancar."""
    logging.basicConfig(level=nivel_por_defecto(), format=_FORMATO, datefmt=_FECHA)
    for nombre in _TERCEROS_RUIDOSOS:
        logging.getLogger(nombre).setLevel(logging.WARNING)


def aplicar_nivel_debug() -> None:
    """Sincroniza el nivel del logger `backend` con el ajuste DEBUG (en caliente).

    Con DEBUG activo, el logger `backend` baja a DEBUG (se ven las trazas de
    prompts/RAG/voz); con DEBUG inactivo, vuelve al nivel de LOG_LEVEL. Se llama al
    arrancar (tras preparar la BBDD) y cada vez que set_many cambia DEBUG.

    Import perezoso de settings_service para no forzar el acceso a la BBDD al
    importar este módulo (que se usa muy temprano, antes de que la BBDD exista).
    """
    from backend.services import settings_service

    activo = bool(settings_service.get("DEBUG"))
    nivel = logging.DEBUG if activo else nivel_por_defecto()
    logging.getLogger("backend").setLevel(nivel)
