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
from backend.services import settings_service


class VoiceError(ValueError):
    """Error de voz: ElevenLabs no configurado, o fallo en STT/TTS.

    Hereda de ValueError para que el router lo devuelva como 400.
    """


# Frase fija para el botón "Probar voz" de la pestaña Personajes: la misma
# para todos los personajes, así el adulto compara voces en igualdad de condiciones.
FRASE_PRUEBA_VOZ = "¡Hola! Prueba de sonido, uno, dos, tres. El rápido zorro marrón salta sobre el perro perezoso."


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


def transcribir(audio_bytes: bytes) -> str:
    """Transcribe audio (bytes) a texto en español con ElevenLabs Scribe.

    Scribe deduce el formato de los propios bytes, así que no necesitamos el
    nombre del fichero. Lanza VoiceError si falta la clave o falla la transcripción.
    """
    client = _get_client()
    try:
        modelo_stt = settings_service.get("ELEVENLABS_STT_MODEL")
        idioma = settings_service.get("STT_LANG")
        resultado = client.speech_to_text.convert(
            file=io.BytesIO(audio_bytes),
            model_id=modelo_stt,
            language_code=idioma,
        )
        texto = (resultado.text or "").strip()
    except Exception as exc:
        raise VoiceError(f"Error al transcribir con ElevenLabs: {exc}")

    if settings_service.get("DEBUG"):
        print(
            f"[VOZ] 🎙️ STT OK · {len(audio_bytes)} bytes de audio recibidos del "
            f'frontend → texto transcrito: "{texto}" '
            f"(ElevenLabs modelo={settings_service.get('ELEVENLABS_STT_MODEL')}, "
            f"idioma={settings_service.get('STT_LANG')})"
        )
    return texto


def sintetizar(texto: str, voz_id: str) -> bytes:
    """Sintetiza `texto` a audio mp3 (bytes) con la voz `voz_id` (ElevenLabs Flash).

    Lanza VoiceError si falta la clave o falla la síntesis.
    """
    client = _get_client()
    try:
        stream = client.text_to_speech.convert(
            voice_id=voz_id,
            model_id=settings_service.get("ELEVENLABS_TTS_MODEL"),
            text=texto,
            output_format=settings_service.get("TTS_OUTPUT_FORMAT"),
        )
        # convert() devuelve un iterador de trozos de bytes; algunos SDK devuelven
        # los bytes ya unidos. Cubrimos ambos casos.
        if isinstance(stream, (bytes, bytearray)):
            return bytes(stream)
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


def reiniciar() -> None:
    """Olvida el cliente cacheado para que se recree con la clave nueva (pantalla APIs)."""
    global _client
    _client = None


def _detalle_error(exc: Exception) -> dict:
    """Extrae el `detail` del error del SDK de ElevenLabs (dict), o {} si no hay."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict) and isinstance(body.get("detail"), dict):
        return body["detail"]
    return {}


def probar() -> dict:
    """Prueba de conexión con ElevenLabs para la pantalla de APIs: {ok, mensaje}.

    Hace una llamada ligera autenticada (`models.list()`). Ojo con las claves de
    ElevenLabs con permisos LIMITADOS ("scoped"): una clave válida que solo puede
    hacer TTS/STT devuelve 401 con `missing_permissions` en este endpoint de lectura.
    Eso NO es un fallo de conexión: la clave autenticó bien y sirve para lo que la
    app necesita, así que la damos por válida. Solo una clave realmente INVÁLIDA
    (`invalid_api_key`) se considera error.
    """
    reiniciar()
    if not config.ELEVENLABS_API_KEY:
        return {"ok": False, "mensaje": "Falta ELEVENLABS_API_KEY."}
    try:
        _get_client().models.list()  # llamada ligera autenticada
        return {"ok": True, "mensaje": "ElevenLabs conectado."}
    except Exception as exc:
        detalle = _detalle_error(exc)
        if getattr(exc, "status_code", None) == 401 and detalle.get("status") == "missing_permissions":
            return {"ok": True, "mensaje": "ElevenLabs conectado (clave válida, con permisos limitados)."}
        mensaje = detalle.get("message") or str(exc)
        return {"ok": False, "mensaje": f"No se pudo conectar con ElevenLabs: {mensaje}"}


def listar_voces() -> dict:
    """Lista las voces disponibles en ElevenLabs para el desplegable de personajes.

    Devuelve {disponible, voces, mensaje}, SIN lanzar excepción:
      - disponible: True si se pudo traer la lista.
      - voces: lista de {voz_id, nombre, categoria, espanol} (vacía si no disponible).
        `espanol` = True si ElevenLabs tiene el español ("es") verificado para esa voz
        (campo `verified_languages`); es solo una etiqueta informativa para la UI, NO
        se usa para ocultar voces: cualquier voz multilingüe puede sintetizar español
        igualmente, verificado o no.
      - mensaje: aviso para la UI cuando no se pudo (falta clave / permisos / error).

    Degradación elegante: si falta la clave, o la clave es "scoped" y no tiene el
    permiso de LECTURA de voces (401 missing_permissions), devolvemos la lista vacía
    con un aviso para que el adulto pueda escribir el `voz_id` a mano. Un personaje
    sin voz responde solo en texto (no rompe el chat).
    """
    if not config.ELEVENLABS_API_KEY:
        return {
            "disponible": False,
            "voces": [],
            "mensaje": "Falta ELEVENLABS_API_KEY: no se puede cargar la lista de voces.",
        }
    try:
        respuesta = _get_client().voices.get_all()
    except Exception as exc:
        detalle = _detalle_error(exc)
        if getattr(exc, "status_code", None) == 401 and detalle.get("status") == "missing_permissions":
            return {
                "disponible": False,
                "voces": [],
                "mensaje": "Tu clave de ElevenLabs no tiene permiso para leer la lista de "
                "voces. Puedes escribir el ID de la voz a mano (lo copias desde "
                "elevenlabs.io/voices).",
            }
        mensaje = detalle.get("message") or str(exc)
        return {"disponible": False, "voces": [], "mensaje": f"No se pudieron cargar las voces: {mensaje}"}

    voces = [
        {
            "voz_id": v.voice_id,
            "nombre": getattr(v, "name", None) or v.voice_id,
            "categoria": getattr(v, "category", None),
            "espanol": any(idioma.language == "es" for idioma in (v.verified_languages or [])),
        }
        for v in (respuesta.voices or [])
    ]
    return {"disponible": True, "voces": voces, "mensaje": ""}
