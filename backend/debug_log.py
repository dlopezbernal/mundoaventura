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

from backend.services import settings_service

# Longitud de las líneas separadoras (solo estético).
_ANCHO = 72


def trazar_prompt(destino: str, **secciones: str | None) -> None:
    """Imprime en consola los prompts enviados a `destino` (SOLO si DEBUG).

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

    print(f"\n┌─ PROMPT → {destino} " + "─" * _ANCHO)
    for nombre, texto in secciones.items():
        if texto is None:
            continue
        print(f"│ [{nombre.upper()}]")
        for linea in str(texto).splitlines() or [""]:
            print(f"│   {linea}")
    print("└" + "─" * (_ANCHO + 12) + "\n")
