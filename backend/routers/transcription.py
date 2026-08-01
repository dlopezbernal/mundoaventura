"""
routers/transcription.py — Endpoint de transcripción de voz (STT)
=================================================================

Una puerta de entrada (la lógica vive en services/voice_service.py):

  POST /api/transcribe → el niño sube el audio de su pregunta (multipart) y
                         recibe el texto transcrito en español (ElevenLabs
                         Scribe), listo para enviarse a /api/ask.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from backend import config
from backend.routers.limites import leer_con_limite
from backend.services import voice_service

router = APIRouter(prefix="/api", tags=["Transcripción (voz)"])


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Transcribe el audio de la pregunta del niño a texto en español."""
    # Lectura del audio async (rápida, con tope de tamaño → 413); la transcripción
    # en ElevenLabs (red, lenta) va al threadpool para no bloquear el event loop.
    audio_bytes = await leer_con_limite(audio, config.MAX_AUDIO_MB, "audio")
    try:
        texto = await run_in_threadpool(voice_service.transcribir, audio_bytes)
    except ValueError as exc:
        # Falta la clave o el audio no se pudo transcribir -> 400.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al transcribir: {exc}") from exc

    return {"texto": texto}
