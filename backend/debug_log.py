"""
backend/debug_log.py — Traza de prompts en modo DEBUG
======================================================

Cuando el ajuste DEBUG está activo, este módulo imprime por la consola del backend
TODOS los prompts que enviamos a un servicio externo, para tenerlos a la vista de
un vistazo y poder depurarlos/ajustarlos rápido:

  - LLM (Replicate): los tres usos del modelo de lenguaje —RAG, GENERAL y el
    Evaluator/juez— con sus dos partes:
      • SYSTEM → el ROL y las reglas ("Eres Leonardo da Vinci, responde en
                 español para un niño de 8-12 años, no inventes…").
      • USER   → la pregunta del niño + las fichas recuperadas.
  - Generación de imagen (Replicate): el prompt de la escena (texto→imagen) y la
    instrucción de edición del modo "usar mi foto".
  - Traducción (DeepL): el texto que mandamos a traducir.

Si DEBUG está desactivado no hace absolutamente nada (coste cero en producción).
"""

import logging

from backend.services import settings_service

logger = logging.getLogger(__name__)

# Longitud de las líneas separadoras (solo estético).
_ANCHO = 72


def trazar_prompt(destino: str, **secciones: str | None) -> None:
    """Emite por el log (nivel DEBUG) los prompts enviados a `destino` (SOLO si DEBUG).

    Mantiene la API pública de siempre (`trazar_prompt`), pero en vez de `print`
    construye el bloque formateado y lo emite con `logger.debug`, de modo que se
    integra con el resto del logging (formato, nivel, redirección). El ajuste DEBUG
    de settings_service sigue siendo la puerta: si está desactivado, no hace nada
    (coste cero en producción).

    Parámetros
    ----------
    destino : str
        Etiqueta legible del servicio receptor, p. ej. "LLM · RAG",
        "Replicate · escena" o "DeepL · traducción ES→EN".
    **secciones : str | None
        Pares nombre→texto con cada parte del prompt. Los nombres habituales son
        `system` (rol/reglas del personaje), `user` (pregunta + fichas) y `prompt`
        (texto único de imagen/traducción), pero admite cualquiera. Las secciones
        con valor None se omiten.

    Ejemplo:
        trazar_prompt("LLM · RAG", system=system, user=user)
    """
    if not settings_service.get("DEBUG"):
        return

    lineas = [f"┌─ PROMPT → {destino} " + "─" * _ANCHO]
    for nombre, texto in secciones.items():
        if texto is None:
            continue
        lineas.append(f"│ [{nombre.upper()}]")
        for linea in str(texto).splitlines() or [""]:
            lineas.append(f"│   {linea}")
    lineas.append("└" + "─" * (_ANCHO + 12))
    logger.debug("\n%s", "\n".join(lineas))
