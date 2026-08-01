"""
evals/metricas.py — Métricas DETERMINISTAS de evaluación (Hito 3)
=================================================================

Todo lo que se puede medir sin un juez LLM: legibilidad para niños, idioma,
longitud, recall@3 y "roto de personaje". Deterministas y gratis, así que se
pueden correr en cada commit sin gastar en APIs.

La métrica estrella es la LEGIBILIDAD en español, que casi nadie usa:
  - Índice de perspicuidad de Szigriszt-Pazos (base de la escala INFLESZ):
        IPP = 206.835 − 62.3·(sílabas/palabras) − (palabras/frases)
    Escala INFLESZ: ≥80 "muy fácil" (primaria) · 65-80 "bastante fácil" ·
    55-65 "normal" · 40-55 "algo difícil" · <40 "muy difícil".
  - Fernández Huerta (adaptación validada de Flesch al español):
        FH = 206.84 − 60·(sílabas/palabras) − 102·(frases/palabras)

Se implementan a mano (sílabas con pyphen) en vez de con textstat: textstat arrastra
nltk/regex y no aporta; la fórmula explícita es además más transparente para la memoria.
"""

import re

import pyphen
from lingua import Language, LanguageDetectorBuilder

# Silabador español (pyphen) y detector de idioma (lingua), creados una sola vez.
_dic = pyphen.Pyphen(lang="es_ES")
_detector = LanguageDetectorBuilder.from_languages(Language.SPANISH, Language.ENGLISH).build()

# Frases que delatan que el modelo se ha salido del personaje (habla "como IA",
# cita el andamiaje del prompt, o se rinde con fórmulas de asistente).
_PATRONES_ROTO = [
    r"como (una |un )?ia\b",
    r"\bcomo modelo\b",
    r"modelo de lenguaje",
    r"inteligencia artificial",
    r"como asistente",
    r"seg[uú]n el (contexto|texto|documento)",
    r"no puedo (responder|ayudar|proporcionar)",
    r"no tengo (informaci[oó]n|acceso|datos)",
    r"\bas an ai\b",
]
_ROTO = [re.compile(p, re.IGNORECASE) for p in _PATRONES_ROTO]

_RE_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
_RE_FRASE = re.compile(r"[.!?…]+")


def contar_palabras(texto: str) -> int:
    return len(_RE_PALABRA.findall(texto))


def contar_frases(texto: str) -> int:
    """Cuenta frases por los signos de fin (., !, ?, …). Mínimo 1 si hay texto."""
    n = len([t for t in _RE_FRASE.split(texto) if t.strip()])
    return max(n, 1) if texto.strip() else 0


def contar_silabas(texto: str) -> int:
    """Suma de sílabas de todas las palabras (pyphen). Cada palabra, mínimo 1 sílaba."""
    total = 0
    for palabra in _RE_PALABRA.findall(texto):
        total += len(_dic.positions(palabra)) + 1
    return total


def inflesz(texto: str) -> float | None:
    """Índice de perspicuidad de Szigriszt-Pazos (escala INFLESZ). None si no hay texto."""
    palabras = contar_palabras(texto)
    frases = contar_frases(texto)
    if palabras == 0 or frases == 0:
        return None
    silabas = contar_silabas(texto)
    return round(206.835 - 62.3 * (silabas / palabras) - (palabras / frases), 1)


def fernandez_huerta(texto: str) -> float | None:
    """Índice de Fernández Huerta (Flesch adaptado al español). None si no hay texto."""
    palabras = contar_palabras(texto)
    frases = contar_frases(texto)
    if palabras == 0 or frases == 0:
        return None
    silabas = contar_silabas(texto)
    return round(206.84 - 60 * (silabas / palabras) - 102 * (frases / palabras), 1)


def banda_inflesz(score: float | None) -> str:
    """Traduce el índice INFLESZ a su banda de dificultad."""
    if score is None:
        return "sin_texto"
    if score >= 80:
        return "muy_facil"
    if score >= 65:
        return "bastante_facil"
    if score >= 55:
        return "normal"
    if score >= 40:
        return "algo_dificil"
    return "muy_dificil"


def idioma(texto: str) -> str:
    """Detecta el idioma (offline, lingua). Devuelve 'es', 'en' o '?'."""
    if not texto.strip():
        return "?"
    lang = _detector.detect_language_of(texto)
    if lang == Language.SPANISH:
        return "es"
    if lang == Language.ENGLISH:
        return "en"
    return "?"


def es_espanol(texto: str) -> bool:
    return idioma(texto) == "es"


def roto_de_personaje(texto: str) -> list[str]:
    """Devuelve las coincidencias de 'roto de personaje' (vacío = bien en personaje)."""
    encontrados = []
    for patron in _ROTO:
        m = patron.search(texto)
        if m:
            encontrados.append(m.group(0))
    return encontrados


def recall_at_k(chunk_esperado: str | list[str] | None, fuentes: list[str | None]) -> bool | None:
    """¿Está alguno de los ficheros `chunk_esperado` entre las fuentes recuperadas?

    `chunk_esperado` puede ser un fichero o una lista (el dato vive en varios). Hay
    "acierto" si el retriever trajo un chunk de CUALQUIERA de ellos. Devuelve None si
    la pregunta no tiene chunk_esperado (no aplica recall).
    """
    if not chunk_esperado:
        return None
    esperados = {chunk_esperado} if isinstance(chunk_esperado, str) else set(chunk_esperado)
    return any(f in esperados for f in fuentes if f)


def recall_chunk(respuesta_contiene: str | list[str] | None, chunks: list[str]) -> bool | None:
    """recall@k a nivel de CHUNK: ¿algún fragmento recuperado CONTIENE la respuesta?

    A diferencia del recall de fichero (que se satura al 100 % con pocos documentos),
    este discrimina la calidad real del retrieval: exige que el texto de la respuesta
    (una palabra clave en inglés) aparezca en alguno de los chunks recuperados.
    Devuelve None si la pregunta no lleva `respuesta_contiene`.
    """
    if not respuesta_contiene:
        return None
    claves = [respuesta_contiene] if isinstance(respuesta_contiene, str) else respuesta_contiene
    blob = " ".join(chunks).lower()
    return any(c.lower() in blob for c in claves)
