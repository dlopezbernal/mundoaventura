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

import logging

import deepl

from backend import config, debug_log

logger = logging.getLogger(__name__)


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
        raise TranslationError(f"No hay conexión con DeepL o la clave no es válida: {exc}") from exc

    _translator = translator
    logger.info("DeepL conectado. ✅")
    return _translator


def traducir_es_en(texto: str) -> str:
    """Traduce un texto del español al inglés. Lanza TranslationError si falla.

    Se usa para traducir la pregunta del niño antes de consultar el RAG. No hay
    fallback: si DeepL no está disponible, preferimos un error claro.
    """
    translator = _get_translator()
    debug_log.trazar_prompt("DeepL · traducción ES→EN", prompt=texto)
    try:
        resultado = translator.translate_text(texto, source_lang="ES", target_lang="EN-US")
        return resultado.text
    except Exception as exc:
        raise TranslationError(f"Error al traducir con DeepL: {exc}") from exc


# Tamaño máximo (caracteres) por petición a DeepL al traducir documentos largos.
# La API tiene un límite de tamaño por request; troceamos por párrafos MUY por
# debajo de ese límite para no fallar y no mandar textos gigantes de una vez.
_MAX_CHARS_LOTE = 40_000


def _trocear_para_traducir(texto: str) -> list[str]:
    """Parte un texto largo en lotes (por párrafos) por debajo de _MAX_CHARS_LOTE.

    Respeta los límites de párrafo (dobles saltos de línea) siempre que puede; si
    un solo párrafo excede el máximo, lo trocea "a lo bruto" por tamaño.
    """
    lotes: list[str] = []
    actual = ""
    for parrafo in texto.split("\n\n"):
        # Un párrafo por sí solo más grande que el máximo: se parte por tamaño.
        if len(parrafo) > _MAX_CHARS_LOTE:
            if actual:
                lotes.append(actual)
                actual = ""
            for i in range(0, len(parrafo), _MAX_CHARS_LOTE):
                lotes.append(parrafo[i : i + _MAX_CHARS_LOTE])
            continue
        # ¿Cabe el párrafo en el lote actual?
        if len(actual) + len(parrafo) + 2 > _MAX_CHARS_LOTE:
            lotes.append(actual)
            actual = parrafo
        else:
            actual = f"{actual}\n\n{parrafo}" if actual else parrafo
    if actual:
        lotes.append(actual)
    return lotes


def traducir_a_ingles(texto: str) -> tuple[str, str]:
    """Traduce un DOCUMENTO a inglés, AUTO-DETECTANDO el idioma de origen.

    Se llama SIEMPRE al guardar un documento del RAG (subida, URL o edición): ya
    no hay checkbox "ya está en inglés" — se detecta solas. DeepL no ofrece un
    endpoint de detección aparte del de traducir, así que la propia llamada de
    traducción sirve también para detectar (`detected_source_lang` de la
    respuesta). A diferencia de `traducir_es_en` (pregunta corta, ES fijo), aquí
    el origen se autodetecta (source_lang=None) y el texto puede ser largo, así
    que lo troceamos por lotes.

    Devuelve (texto_traducido, idioma_detectado en minúsculas, p. ej. "en"/"es"/
    "fr"). El idioma detectado se toma del primer lote (un documento es una sola
    fuente; no debería variar entre lotes del mismo texto).

    Lanza TranslationError si DeepL no está disponible.
    """
    translator = _get_translator()
    lotes = _trocear_para_traducir(texto)
    debug_log.trazar_prompt(
        "DeepL · traducción documento → EN",
        prompt=f"({len(texto)} caracteres en {len(lotes)} lote/s)",
    )
    try:
        # translate_text acepta una lista y devuelve una lista (un resultado por lote).
        resultados = translator.translate_text(lotes, target_lang="EN-US")
        if not isinstance(resultados, list):
            resultados = [resultados]
        texto_traducido = "\n\n".join(r.text for r in resultados)
        idioma_detectado = resultados[0].detected_source_lang.lower()
        return texto_traducido, idioma_detectado
    except Exception as exc:
        raise TranslationError(f"Error al traducir el documento con DeepL: {exc}") from exc


def estado() -> dict:
    """Comprueba el estado de DeepL SIN lanzar excepción (para /health y arranque)."""
    try:
        _get_translator()
        return {"deepl_ok": True, "deepl_mensaje": "DeepL conectado."}
    except TranslationError as exc:
        return {"deepl_ok": False, "deepl_mensaje": str(exc)}


def reiniciar() -> None:
    """Olvida el cliente cacheado para que se recree con la clave nueva.

    Lo usa la pantalla de APIs (Hito 2) tras guardar una clave de DeepL: así la
    siguiente traducción usa la clave recién guardada sin reiniciar el backend.
    """
    global _translator
    _translator = None


def probar() -> dict:
    """Prueba de conexión con DeepL para la pantalla de APIs: {ok, mensaje}.

    Fuerza recrear el cliente (por si la clave cambió) y valida contra la API.
    """
    reiniciar()
    est = estado()
    return {"ok": est["deepl_ok"], "mensaje": est["deepl_mensaje"]}
