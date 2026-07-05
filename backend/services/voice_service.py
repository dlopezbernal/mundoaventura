"""
services/voice_service.py — Voz con ElevenLabs (STT Scribe + TTS Flash)
=======================================================================

Dos mitades, un solo proveedor y una sola clave (ELEVENLABS_API_KEY):

  - transcribir(...)  voz del niño (bytes de audio) → texto en español  (Scribe)
  - sintetizar(...)   texto de la respuesta → audio mp3 (bytes)          (Flash)

Igual que translation_service (DeepL), la clave se valida de forma perezosa y los
errores se lanzan como VoiceError (subclase de ValueError) para que el router los
devuelva como HTTP 400 con un mensaje claro, en vez de un 500 genérico.
"""

import io

from elevenlabs.client import ElevenLabs

from backend import config


class VoiceError(ValueError):
    """Error de voz: ElevenLabs no configurado, o fallo en STT/TTS.

    Hereda de ValueError para que el router lo devuelva como 400.
    """


# Cliente de ElevenLabs, creado una sola vez (singleton perezoso).
_client: ElevenLabs | None = None


def _get_client() -> ElevenLabs:
    """Devuelve el cliente de ElevenLabs, o lanza VoiceError si falta la clave."""
    global _client
    if _client is not None:
        return _client
    if not config.ELEVENLABS_API_KEY:
        raise VoiceError(
            "Falta ELEVENLABS_API_KEY en el .env. La voz (transcripción y síntesis) "
            "la provee ElevenLabs. Consigue una clave en https://elevenlabs.io y "
            "añádela al .env."
        )
    _client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
    return _client


def transcribir(audio_bytes: bytes, filename: str = "audio.mp3") -> str:
    """Transcribe audio (bytes) a texto en español con ElevenLabs Scribe.

    Lanza VoiceError si falta la clave o falla la transcripción.
    """
    client = _get_client()
    try:
        resultado = client.speech_to_text.convert(
            file=io.BytesIO(audio_bytes),
            model_id=config.ELEVENLABS_STT_MODEL,
            language_code=config.STT_LANG,
        )
        texto = (resultado.text or "").strip()
    except Exception as exc:
        raise VoiceError(f"Error al transcribir con ElevenLabs: {exc}")

    if config.DEBUG:
        print(f'[VOZ] 🎙️ STT · {len(audio_bytes)} bytes → "{texto}"')
    return texto


def sintetizar(texto: str, voz_id: str) -> bytes:
    """Sintetiza `texto` a audio mp3 (bytes) con la voz `voz_id` (ElevenLabs Flash).

    Lanza VoiceError si falta la clave o falla la síntesis.
    """
    client = _get_client()
    try:
        stream = client.text_to_speech.convert(
            voice_id=voz_id,
            model_id=config.ELEVENLABS_TTS_MODEL,
            text=texto,
            output_format=config.TTS_OUTPUT_FORMAT,
        )
        # convert() devuelve un iterador de trozos de bytes: los unimos.
        return b"".join(stream)
    except Exception as exc:
        raise VoiceError(f"Error al sintetizar con ElevenLabs: {exc}")


def estado() -> dict:
    """Estado de ElevenLabs SIN lanzar excepción (para /health y arranque).

    Comprueba solo que la clave esté presente (no hace llamada de red, para no
    gastar cuota en cada /health).
    """
    if not config.ELEVENLABS_API_KEY:
        return {
            "elevenlabs_ok": False,
            "elevenlabs_mensaje": "Falta ELEVENLABS_API_KEY (voz desactivada).",
        }
    return {"elevenlabs_ok": True, "elevenlabs_mensaje": "ElevenLabs configurado."}
