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
import re
from collections.abc import Iterator

from backend import config
from backend.services import (
    audio_cache,
    personajes_service,
    rag_service,
    settings_service,
    voice_service,
)
from backend.services.rag_service import RespuestaRAG

logger = logging.getLogger(__name__)

# Fin de frase: cualquier texto hasta uno o más signos de cierre (. ! ? …). Sirve para
# trocear el streaming del LLM en FRASES y lanzar el TTS de cada una en cuanto cierra,
# sin esperar a que termine toda la respuesta (baja la latencia percibida, Hito 8).
_RE_FIN_FRASE = re.compile(r".*?[.!?…]+", re.DOTALL)


class RespuestaChat(RespuestaRAG):
    """Retorno de `responder`: la respuesta de texto (RespuestaRAG) MÁS el audio.

    `audio_base64` es el mp3 en base64 (o None si el personaje no tiene voz o el TTS
    falló). Es lo que consume el endpoint /api/ask (schema AskResponse).
    """

    audio_base64: str | None


def _voz_id(personaje_id: str) -> str | None:
    """voz_id del personaje si tiene voz Y hay clave de ElevenLabs; si no, None."""
    ficha = personajes_service.obtener(personaje_id)
    voz_id = ficha["voz_id"] if ficha else None
    if not voz_id or not config.ELEVENLABS_API_KEY:
        return None
    return voz_id


def _sintetizar_cacheado(voz_id: str, texto: str) -> str | None:
    """Sintetiza `texto` a mp3 en base64, usando la CACHÉ en disco. None si falla/ vacío.

    Consulta primero la caché (voz+modelo+texto); si no está, llama a ElevenLabs y
    guarda el resultado. Un fallo del TTS NUNCA rompe el chat (degrada a solo-texto).
    """
    texto = texto.strip()
    if not texto:
        return None
    modelo_tts = settings_service.get("ELEVENLABS_TTS_MODEL")
    clave = audio_cache.clave(voz_id, modelo_tts, texto)

    cacheado = audio_cache.obtener(clave)
    if cacheado is not None:
        if settings_service.get("DEBUG"):
            logger.debug("[VOZ] 🔊 TTS (caché) · voz_id=%s · %s caracteres", voz_id, len(texto))
        return base64.b64encode(cacheado).decode("ascii")

    try:
        audio_bytes = voice_service.sintetizar(texto, voz_id)
    except Exception:
        # La respuesta se entrega SOLO en texto y el chat sigue. Se registra SIEMPRE.
        logger.warning(
            "TTS (síntesis de voz) FALLÓ para voz_id=%s; se entrega sin audio.",
            voz_id,
            exc_info=True,
        )
        return None
    audio_cache.guardar(clave, audio_bytes)
    if settings_service.get("DEBUG"):
        logger.debug(
            "[VOZ] 🔊 TTS OK · voz_id=%s · %s caracteres → mp3 base64 (modelo=%s)",
            voz_id,
            len(texto),
            modelo_tts,
        )
    return base64.b64encode(audio_bytes).decode("ascii")


def _sintetizar_voz(personaje_id: str, respuesta: str) -> str | None:
    """Respuesta completa como mp3 en base64, o None (degradación elegante)."""
    voz_id = _voz_id(personaje_id)
    if not voz_id:
        return None
    return _sintetizar_cacheado(voz_id, respuesta)


def dividir_frases(buffer: str) -> tuple[list[str], str]:
    """Extrae del buffer las frases COMPLETAS (hasta el último .!?…) y el resto pendiente.

    Función pura: acumula tokens del LLM y, en cuanto se cierra una frase, la separa
    para lanzar su TTS mientras el modelo sigue generando. Ej.: "Hola. ¿Qué tal? Bien"
    → (["Hola.", "¿Qué tal?"], " Bien").
    """
    frases: list[str] = []
    pos = 0
    for m in _RE_FIN_FRASE.finditer(buffer):
        frase = m.group().strip()
        if frase:
            frases.append(frase)
        pos = m.end()
    return frases, buffer[pos:]


def responder(
    personaje_id: str,
    pregunta: str,
    nombre_nino: str | None = None,
    sexo_nino: str | None = None,
) -> RespuestaChat:
    """Respuesta completa del chat (de una vez): texto (RAG) + voz (TTS si tiene).

    Propaga los ValueError de `rag_service.responder` (personaje inexistente o falta
    de token) para que el router los mapee a 400. El streaming equivalente es
    `responder_streaming`. `nombre_nino`/`sexo_nino` (opcionales, H9.2c) personalizan.
    """
    resultado = rag_service.responder(personaje_id, pregunta, nombre_nino, sexo_nino)
    audio = _sintetizar_voz(personaje_id, resultado["respuesta"])
    return {**resultado, "audio_base64": audio}


def responder_streaming(
    personaje_id: str,
    pregunta: str,
    nombre_nino: str | None = None,
    sexo_nino: str | None = None,
) -> Iterator[dict]:
    """Orquesta el chat en STREAMING (Hito 8): texto por trozos + voz POR FRASES.

    Emite dicts con `tipo` (los que consume el endpoint SSE):
      - {"tipo": "fuentes", "fuentes": [...], "origen": ...}   una vez, al principio.
      - {"tipo": "token", "texto": <trozo>}                    por cada trozo del LLM.
      - {"tipo": "audio_chunk", "audio_base64": <mp3 b64>}     por cada FRASE sintetizada.
      - {"tipo": "fin", "respuesta": <texto completo>}         al terminar.

    El TTS por frases (con caché) va INTERCALADO: cada vez que el texto cierra una
    frase, se sintetiza y se envía su audio mientras el LLM sigue. Un fallo de voz
    degrada a solo-texto (no se emite audio_chunk) y nunca corta el texto.
    """
    voz_id = _voz_id(personaje_id)
    buffer = ""
    partes: list[str] = []
    for evento in rag_service.responder_streaming(personaje_id, pregunta, nombre_nino, sexo_nino):
        if evento["tipo"] == "meta":
            yield {"tipo": "fuentes", "fuentes": evento["fuentes"], "origen": evento["origen"]}
            continue
        # tipo == "token"
        texto = evento["texto"]
        partes.append(texto)
        yield {"tipo": "token", "texto": texto}
        if voz_id:
            buffer += texto
            frases, buffer = dividir_frases(buffer)
            for frase in frases:
                audio = _sintetizar_cacheado(voz_id, frase)
                if audio:
                    yield {"tipo": "audio_chunk", "audio_base64": audio}

    # Última frase incompleta (sin signo de cierre): también se sintetiza.
    if voz_id and buffer.strip():
        audio = _sintetizar_cacheado(voz_id, buffer)
        if audio:
            yield {"tipo": "audio_chunk", "audio_base64": audio}

    yield {"tipo": "fin", "respuesta": "".join(partes).strip()}
