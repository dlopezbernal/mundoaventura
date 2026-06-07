"""
services/translation_service.py — Traducción ES→EN con DeepL (OBLIGATORIO)
==========================================================================

¿Por qué traducir? Los documentos del RAG (backend/documentos/) están en INGLÉS,
porque el modelo de embeddings de ChromaDB entiende mucho mejor el inglés. Para
que la búsqueda funcione, traducimos la pregunta del niño (español) a inglés ANTES
de buscar.

¿Por qué es OBLIGATORIO (y no opcional)? Lo comprobamos midiendo distancias: sin
traducir, no solo empeora la distancia, sino que **se recupera la ficha
equivocada** (p. ej. "¿dónde vives?" en español recuperaba "resuelvo misterios"
en vez de la de Baker Street). Sin DeepL el RAG da respuestas malas, así que
preferimos fallar con un mensaje claro a responder mal.

Arquitectura de 1 sola traducción:
  - Solo traducimos la PREGUNTA (ES→EN), para el retrieval.
  - La RESPUESTA NO se traduce: el LLM lee las fichas en inglés y responde
    directamente en español (es multilingüe).
"""

import deepl

from backend import config
from backend import debug_log


class TranslationError(ValueError):
    """Error de traducción: DeepL no está configurado o no hay conexión.

    Hereda de ValueError para que el router lo devuelva como 400 con un mensaje
    claro, en vez de un 500 genérico.
    """


# Cliente de DeepL, creado y validado una sola vez (singleton perezoso).
_translator: deepl.Translator | None = None


def _get_translator() -> deepl.Translator:
    """Devuelve el cliente de DeepL ya validado, o lanza TranslationError.

    La primera vez valida la conexión llamando a get_usage(): así detectamos al
    instante una clave ausente o inválida, en vez de fallar en mitad de un chat.
    """
    global _translator
    if _translator is not None:
        return _translator

    if not config.DEEPL_API_KEY:
        raise TranslationError(
            "Falta DEEPL_API_KEY en el .env. La traducción es OBLIGATORIA: sin "
            "ella la búsqueda del RAG recupera fichas equivocadas. Consigue una "
            "clave gratis en https://www.deepl.com/pro-api y añádela al .env."
        )

    try:
        translator = deepl.Translator(config.DEEPL_API_KEY)
        translator.get_usage()  # comprueba que la clave funciona y hay conexión
    except Exception as exc:
        raise TranslationError(
            f"No hay conexión con DeepL o la clave no es válida: {exc}"
        )

    _translator = translator
    print("[Traducción] DeepL conectado. ✅")
    return _translator


def traducir_es_en(texto: str) -> str:
    """Traduce un texto del español al inglés. Lanza TranslationError si falla.

    Se usa para traducir la pregunta del niño antes de consultar el RAG. No hay
    fallback: si DeepL no está disponible, preferimos un error claro.
    """
    translator = _get_translator()
    debug_log.trazar_prompt("DeepL · traducción ES→EN", prompt=texto)
    try:
        resultado = translator.translate_text(
            texto, source_lang="ES", target_lang="EN-US"
        )
        return resultado.text
    except Exception as exc:
        raise TranslationError(f"Error al traducir con DeepL: {exc}")


def estado() -> dict:
    """Comprueba el estado de DeepL SIN lanzar excepción (para /health y arranque)."""
    try:
        _get_translator()
        return {"deepl_ok": True, "deepl_mensaje": "DeepL conectado."}
    except TranslationError as exc:
        return {"deepl_ok": False, "deepl_mensaje": str(exc)}
