"""
routers/generation.py — Endpoints HTTP de la generación
========================================================

Dos puertas de entrada (la lógica vive en services/generation_service.py):

  POST /api/generate          → escena con ubicación predefinida (JSON).
  POST /api/generate-on-photo → estiliza la foto subida y añade el personaje
                                (multipart: archivo + personaje_id).
"""

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from backend import config
from backend.ratelimit import limiter
from backend.routers import errores
from backend.routers.limites import leer_con_limite
from backend.schemas.generation import GenerateRequest, GenerateResponse
from backend.services import cuota_service, generation_service

router = APIRouter(prefix="/api", tags=["Generación"])


def _exigir_cupo_diario() -> None:
    """Corta ANTES de gastar en Replicate si se agotó el cupo diario de imágenes."""
    if not cuota_service.hay_cupo():
        raise HTTPException(status_code=429, detail=config.MENSAJE_LIMITE)


# `def` (no `async def`) A PROPÓSITO: generar_escena llama a replicate.run (I/O de
# red síncrona). Como `def`, FastAPI lo ejecuta en su threadpool y el event loop no
# se bloquea. Ver docs/mediciones/H2-concurrencia.md.
#
# Rate limit por IP (restrictivo: la imagen es lo caro) + tope diario en SQLite.
# `request` es obligatorio para que slowapi identifique al cliente.
@router.post("/generate", response_model=GenerateResponse)
@limiter.limit(lambda: config.RATE_LIMIT_GENERATE)
def generate(request: Request, req: GenerateRequest):
    """Genera una imagen del personaje en la ubicación predefinida elegidos."""
    _exigir_cupo_diario()
    try:
        result = generation_service.generar_escena(
            personaje_id=req.personaje_id,
            ubicacion_id=req.ubicacion_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise errores.error_500(exc, "generar la imagen") from exc

    cuota_service.registrar()  # solo se cuenta la generación que sale bien
    return result


@router.post("/generate-on-photo", response_model=GenerateResponse)
@limiter.limit(lambda: config.RATE_LIMIT_GENERATE)
async def generate_on_photo(
    request: Request,
    image: UploadFile = File(..., description="Foto que sube el niño."),
    personaje_id: str = Form(..., description="Identificador del personaje a añadir."),
):
    """Estiliza la foto subida a Pixar 3D y añade el personaje (una sola llamada)."""
    _exigir_cupo_diario()
    # La lectura del fichero (I/O local rápida) se queda async; la generación en
    # Replicate (I/O de red LENTA y bloqueante) se delega al threadpool con
    # run_in_threadpool para no congelar el event loop mientras dura la llamada.
    image_bytes = await leer_con_limite(image, config.MAX_IMAGEN_MB, "imagen")
    try:
        result = await run_in_threadpool(
            generation_service.generar_en_foto,
            image_bytes=image_bytes,
            personaje_id=personaje_id,
            mime=image.content_type or "image/png",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise errores.error_500(exc, "generar la imagen") from exc

    cuota_service.registrar()
    return result
