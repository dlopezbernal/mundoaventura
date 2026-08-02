"""
services/stt_service.py — Capa de proveedor de transcripción (STT) (Hito 7)
===========================================================================

Un ÚNICO punto por el que pasa TODA la transcripción de voz→texto, para poder mover
la voz del niño a LOCAL cambiando CONFIGURACIÓN, no código (mismo patrón que
`llm_service` en H5). La motivación es de PRIVACIDAD: con STT local, la voz del niño
**nunca sale del PC** — es el eje del capítulo de RGPD, no una nota al pie.

Tres dialectos detrás de la misma interfaz (`STT_PROVIDER`):

  - `elevenlabs` (por defecto, LEGACY): Scribe en la nube. Reproduce la línea base;
    usa el cliente y la clave (ELEVENLABS_API_KEY) que ya gestiona `voice_service`.
  - `local`: `faster-whisper` (CTranslate2, GPU/CPU, SIN torch). Dependencia OPCIONAL
    (extra `stt-local`), importada de forma perezosa. La voz no sale del equipo.
  - `groq`: Whisper en Groq (nube, endpoint openai-compatible). Candidato de latencia.

**Fallback automático:** si `local` no carga (paquete ausente, o DLLs de cuBLAS/cuDNN
que faltan en Windows) o falla, se AVISA por `logger.warning` y se cae a `elevenlabs`.
Así la app NUNCA se queda muda por un problema de DLLs.

El proveedor, el modelo y el dispositivo son ajustes en caliente (`settings_service`);
la clave de Groq es un secreto (`config.GROQ_API_KEY`, .env). Los clientes/modelos
perezosos se reconstruyen solos cuando cambia su configuración (firma cacheada).
"""

import io
import logging

from backend import config
from backend.services import resiliencia, settings_service

logger = logging.getLogger(__name__)


class STTError(ValueError):
    """Error de transcripción. Hereda de ValueError para que el router lo dé como 400."""


_PROVEEDORES_VALIDOS = ("elevenlabs", "local", "groq")

# Modelo local de faster-whisper y cliente de Groq: singletons perezosos, con la FIRMA
# de la config con la que se crearon. Si la firma cambia (ajuste en caliente), se
# reconstruyen en la siguiente llamada — sin necesidad de reiniciar el backend.
_modelo_local = None
_modelo_local_firma: tuple | None = None
_cliente_groq = None
_cliente_groq_firma: tuple | None = None


def _provider() -> str:
    """Proveedor vigente (cae a 'elevenlabs' si el ajuste trae algo raro)."""
    p = settings_service.get("STT_PROVIDER")
    return p if p in _PROVEEDORES_VALIDOS else "elevenlabs"


def transcribir(audio_bytes: bytes) -> str:
    """Transcribe audio (bytes) a texto en español, según STT_PROVIDER.

    Con `local`, cualquier fallo (paquete ausente, DLLs, error de decodificación) NO
    rompe el chat: se AVISA y se transcribe con ElevenLabs. Lanza STTError solo si el
    proveedor de nube elegido tampoco puede (p. ej. falta la clave).
    """
    provider = _provider()
    if provider == "local":
        try:
            return _transcribir_local(audio_bytes)
        except Exception as exc:  # noqa: BLE001 — la resiliencia es a propósito amplia
            logger.warning(
                "STT local (faster-whisper) no disponible o falló (%s). "
                "Cae a ElevenLabs para no dejar el chat sin voz.",
                exc,
            )
            return _transcribir_elevenlabs(audio_bytes)
    if provider == "groq":
        return _transcribir_groq(audio_bytes)
    return _transcribir_elevenlabs(audio_bytes)


# ---------------------------------------------------------------------------
# Dialecto LOCAL — faster-whisper (CTranslate2, sin torch)
# ---------------------------------------------------------------------------
def _cargar_modelo_local():
    """Carga (o reutiliza) el WhisperModel local. Lo reconstruye si cambió la config.

    Lanza si `faster-whisper` no está instalado (extra `stt-local`) — el llamador lo
    captura y cae a la nube. Import perezoso: el backend base no arrastra la dependencia.
    """
    global _modelo_local, _modelo_local_firma
    firma = (
        settings_service.get("STT_LOCAL_MODEL"),
        settings_service.get("STT_LOCAL_DEVICE"),
        settings_service.get("STT_LOCAL_COMPUTE"),
    )
    if _modelo_local is not None and _modelo_local_firma == firma:
        return _modelo_local

    from faster_whisper import WhisperModel  # perezoso: solo si STT_PROVIDER=local

    modelo, device, compute = firma
    logger.info("Cargando faster-whisper (%s, %s, %s)…", modelo, device, compute)
    _modelo_local = WhisperModel(modelo, device=device, compute_type=compute)
    _modelo_local_firma = firma
    return _modelo_local


def _transcribir_local(audio_bytes: bytes) -> str:
    """Transcribe con faster-whisper. `transcribe` devuelve un generador de segmentos."""
    modelo = _cargar_modelo_local()
    idioma = settings_service.get("STT_LANG")
    segmentos, _info = modelo.transcribe(io.BytesIO(audio_bytes), language=idioma)
    texto = "".join(seg.text for seg in segmentos).strip()
    _trazar("local", audio_bytes, texto, settings_service.get("STT_LOCAL_MODEL"))
    return texto


# ---------------------------------------------------------------------------
# Dialecto ELEVENLABS — Scribe en la nube (reutiliza el cliente de voice_service)
# ---------------------------------------------------------------------------
def _transcribir_elevenlabs(audio_bytes: bytes) -> str:
    """Transcribe con ElevenLabs Scribe. Usa el cliente único de `voice_service`.

    Import perezoso de voice_service para evitar el ciclo (voice_service.transcribir
    delega en este módulo). Traduce el fallo a STTError (→ HTTP 400).
    """
    from backend.services import voice_service

    client = voice_service._get_client()  # lanza VoiceError (→400) si falta la clave
    try:
        modelo_stt = settings_service.get("ELEVENLABS_STT_MODEL")
        idioma = settings_service.get("STT_LANG")
        resultado = resiliencia.reintentar(
            lambda: client.speech_to_text.convert(
                file=io.BytesIO(audio_bytes),
                model_id=modelo_stt,
                language_code=idioma,
            ),
            etiqueta="ElevenLabs · STT",
        )
        texto = (resultado.text or "").strip()
    except Exception as exc:
        raise STTError(f"Error al transcribir con ElevenLabs: {exc}") from exc
    _trazar("elevenlabs", audio_bytes, texto, settings_service.get("ELEVENLABS_STT_MODEL"))
    return texto


# ---------------------------------------------------------------------------
# Dialecto GROQ — Whisper en la nube (endpoint openai-compatible)
# ---------------------------------------------------------------------------
def _cliente_openai_groq():
    """Cliente openai apuntando a Groq (singleton perezoso, rehecho si cambia la firma)."""
    global _cliente_groq, _cliente_groq_firma
    firma = (config.GROQ_API_KEY, config.GROQ_BASE_URL)
    if _cliente_groq is not None and _cliente_groq_firma == firma:
        return _cliente_groq
    if not config.GROQ_API_KEY:
        raise STTError("Falta GROQ_API_KEY en el .env para transcribir con Groq.")
    from openai import OpenAI

    _cliente_groq = OpenAI(
        api_key=config.GROQ_API_KEY,
        base_url=config.GROQ_BASE_URL,
        timeout=config.ELEVENLABS_TIMEOUT,
        max_retries=max(config.HTTP_MAX_INTENTOS - 1, 0),
    )
    _cliente_groq_firma = firma
    return _cliente_groq


def _transcribir_groq(audio_bytes: bytes) -> str:
    modelo = settings_service.get("GROQ_STT_MODEL")
    idioma = settings_service.get("STT_LANG")
    try:
        resp = _cliente_openai_groq().audio.transcriptions.create(
            model=modelo,
            file=("audio.webm", io.BytesIO(audio_bytes)),
            language=idioma,
        )
        texto = (resp.text or "").strip()
    except STTError:
        raise
    except Exception as exc:
        raise STTError(f"Error al transcribir con Groq: {exc}") from exc
    _trazar("groq", audio_bytes, texto, modelo)
    return texto


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _trazar(proveedor: str, audio_bytes: bytes, texto: str, modelo: str) -> None:
    """Traza la transcripción cuando DEBUG está activo (consola del backend)."""
    if settings_service.get("DEBUG"):
        logger.debug(
            '[VOZ] 🎙️ STT OK (%s) · %s bytes → "%s" (modelo=%s)',
            proveedor,
            len(audio_bytes),
            texto,
            modelo,
        )


def info() -> dict:
    """Describe el STT vigente (proveedor + modelo). NUNCA incluye claves."""
    provider = _provider()
    modelo = {
        "local": settings_service.get("STT_LOCAL_MODEL"),
        "groq": settings_service.get("GROQ_STT_MODEL"),
    }.get(provider, settings_service.get("ELEVENLABS_STT_MODEL"))
    return {"provider": provider, "model": modelo}


def reiniciar() -> None:
    """Olvida el modelo local y el cliente de Groq cacheados (tras cambiar clave/config)."""
    global _modelo_local, _modelo_local_firma, _cliente_groq, _cliente_groq_firma
    _modelo_local = None
    _modelo_local_firma = None
    _cliente_groq = None
    _cliente_groq_firma = None


def probar() -> dict:
    """Prueba ligera para la pantalla de APIs (solo aplica al proveedor Groq)."""
    if _provider() != "groq":
        return {"ok": True, "mensaje": "STT no-Groq (se prueba en su propia tarjeta)."}
    try:
        _cliente_openai_groq().models.list()
        return {"ok": True, "mensaje": "Groq (STT) conectado."}
    except Exception as exc:  # noqa: BLE001 — informe de estado, no propagamos
        return {"ok": False, "mensaje": f"No se pudo conectar con Groq: {exc}"}
