"""
services/safety_service.py — Filtro de salida para la vía GENERAL (Hito 9)
==========================================================================

La vía RAG está ANCLADA a los documentos (y, desde H9, con las fichas delimitadas
como datos). La vía GENERAL, en cambio, devuelve texto LIBRE del LLM a un niño, sin
nada que lo fundamente: es el único camino donde el modelo puede irse de tema. Este
filtro es la última comprobación antes de entregar una respuesta GENERAL:

  - LONGITUD: una respuesta larguísima suele ser una generación desbocada.
  - IDIOMA: debe estar en español (si sale en otro idioma, algo ha ido mal).
  - TÉRMINOS: una lista MÍNIMA y curada de contenido claramente inapropiado para un
    niño (sexual, drogas duras, autolesión, insultos fuertes). NO es exhaustiva —un
    producto real usaría un servicio de moderación—; corta lo evidente sin castigar el
    vocabulario normal de dinosaurios/historia (no se bloquean verbos como "matar").

Si la respuesta no pasa el filtro, `revisar_general` la sustituye por el mensaje
seguro "no lo sé" (el mismo de SIN_INFO), en vez de entregar el texto dudoso.
"""

import logging
import re

from lingua import Language, LanguageDetectorBuilder

from backend.services import settings_service

logger = logging.getLogger(__name__)

# Detector de idioma (offline, lingua), creado una sola vez.
_detector = LanguageDetectorBuilder.from_languages(Language.SPANISH, Language.ENGLISH).build()

# Máximo de palabras de una respuesta al niño (2-4 frases; con margen). Por encima,
# es una generación desbocada y se descarta.
_MAX_PALABRAS = 150

# Mínimo de palabras para fiarse de la detección de idioma (textos muy cortos engañan).
_MIN_PALABRAS_IDIOMA = 4

# Lista MÍNIMA de términos inapropiados (raíces; se comparan por prefijo de palabra).
# Deliberadamente NO incluye violencia genérica ("matar", "guerra"): en una app de
# dinosaurios e historia es vocabulario normal, y el filtro debe cortar lo inapropiado,
# no empobrecer las respuestas legítimas.
_TERMINOS_BLOQUEADOS = [
    "sexo",
    "sexual",
    "porno",
    "violaci",  # violación/violaciones
    "suicid",  # suicidio/suicidarse
    "autolesi",  # autolesión
    "cocain",
    "cocaín",
    "heroína",
    "heroina",
    "droga",
    "puta",
    "puto",
    "polla",
    "coño",
    "joder",
    "mierda",
]
_RE_BLOQUEADOS = re.compile(r"\b(?:" + "|".join(_TERMINOS_BLOQUEADOS) + r")", re.IGNORECASE)

_RE_PALABRA = re.compile(r"\w+", re.UNICODE)


def filtrar_salida(texto: str) -> tuple[bool, str]:
    """¿Es segura esta respuesta para un niño? Devuelve (es_segura, motivo_si_no)."""
    t = (texto or "").strip()
    if not t:
        return False, "respuesta vacía"
    palabras = _RE_PALABRA.findall(t)
    if len(palabras) > _MAX_PALABRAS:
        return False, "demasiado larga"
    if _RE_BLOQUEADOS.search(t):
        return False, "contiene un término inapropiado"
    if len(palabras) >= _MIN_PALABRAS_IDIOMA:
        idioma = _detector.detect_language_of(t)
        if idioma is not None and idioma != Language.SPANISH:
            return False, "no está en español"
    return True, ""


def revisar_general(texto: str, nombre: str) -> str:
    """Devuelve `texto` si pasa el filtro; si no, el mensaje seguro 'no lo sé'.

    Se aplica SOLO a la vía GENERAL (texto no fundamentado). La vía RAG está anclada a
    los documentos y no pasa por aquí. El rechazo se registra (para poder auditarlo).
    """
    ok, motivo = filtrar_salida(texto)
    if ok:
        return texto
    logger.warning(
        "Filtro de salida (vía GENERAL) RECHAZÓ una respuesta (%s); se entrega el "
        "mensaje seguro en su lugar.",
        motivo,
    )
    return settings_service.rellenar(settings_service.get("MENSAJE_SIN_INFORMACION"), nombre=nombre)
