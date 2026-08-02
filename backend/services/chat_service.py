"""
services/chat_service.py — Orquestador del chat: texto (RAG) + voz (TTS) (Hito 5)
=================================================================================

`rag_service` genera solo TEXTO (recupera, enruta, genera). La VOZ es de otro
proveedor (ElevenLabs) y de otra capa: mezclar el TTS dentro de rag_service era la
fuga de capas principal del backend. Este orquestador fino junta las dos mitades:

  1) pide la respuesta de texto a `rag_service.responder`,
  2) si el personaje tiene voz y hay clave, la sintetiza con `voice_service`,
  3) devuelve el diccionario completo (texto + `audio_base64`).

Separarlo así, además, prepara H8 (streaming): el texto estará listo ANTES que el
audio, que es justo lo que el streaming necesita. Un fallo de voz degrada a
solo-texto (`audio_base64=None`) y NUNCA rompe el chat.
"""

import base64
import logging

from backend import config
from backend.services import personajes_service, rag_service, settings_service, voice_service

logger = logging.getLogger(__name__)


def _sintetizar_voz(personaje_id: str, respuesta: str) -> str | None:
    """Devuelve la respuesta como mp3 en base64, o None (degradación elegante).

    Devuelve None si el personaje no tiene voz_id, si falta la clave de ElevenLabs,
    o si el TTS falla. El texto de la respuesta NUNCA se rompe por un fallo de voz.
    """
    ficha = personajes_service.obtener(personaje_id)
    voz_id = ficha["voz_id"] if ficha else None
    if not voz_id or not config.ELEVENLABS_API_KEY:
        return None
    try:
        audio_bytes = voice_service.sintetizar(respuesta, voz_id)
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    except Exception:
        # La respuesta se entrega SOLO en texto y el chat sigue. El fallo se registra
        # SIEMPRE (no solo en DEBUG) para no perderlo; exc_info guarda la traza.
        logger.warning(
            "TTS (síntesis de voz) FALLÓ para el personaje '%s' (voz_id=%s); la "
            "respuesta se entrega solo en texto (audio_base64=null).",
            personaje_id,
            voz_id,
            exc_info=True,
        )
        return None
    if settings_service.get("DEBUG"):
        logger.debug(
            "[VOZ] 🔊 TTS OK · personaje=%s · voz_id=%s · %s caracteres → mp3 base64 "
            "(ElevenLabs modelo=%s)",
            personaje_id,
            voz_id,
            len(respuesta),
            settings_service.get("ELEVENLABS_TTS_MODEL"),
        )
    return audio_b64


def responder(personaje_id: str, pregunta: str) -> dict:
    """Respuesta completa del chat: texto (RAG) + voz (TTS si el personaje tiene).

    Propaga los ValueError de `rag_service.responder` (personaje inexistente o falta
    de token) para que el router los mapee a 400.
    """
    resultado = rag_service.responder(personaje_id, pregunta)
    resultado["audio_base64"] = _sintetizar_voz(personaje_id, resultado["respuesta"])
    return resultado
