"""
routers/generation.py — Endpoints HTTP de la generación
========================================================

Dos puertas de entrada (la lógica vive en services/generation_service.py):

  POST /api/generate          → escena con ubicación predefinida (JSON).
  POST /api/generate-on-photo → estiliza la foto subida y añade el personaje
                                (multipart: archivo + personaje_id).
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.schemas.generation import GenerateRequest, GenerateResponse
from backend.services import generation_service

router = APIRouter(prefix="/api", tags=["Generación"])


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    """Genera una imagen del personaje en la ubicación predefinida elegidos."""
    try:
        result = generation_service.generar_escena(
            personaje_id=req.personaje_id,
            ubicacion_id=req.ubicacion_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al generar la imagen: {exc}") from exc

    return result


@router.post("/generate-on-photo", response_model=GenerateResponse)
async def generate_on_photo(
    image: UploadFile = File(..., description="Foto que sube el niño."),
    personaje_id: str = Form(..., description="Identificador del personaje a añadir."),
):
    """Estiliza la foto subida a Pixar 3D y añade el personaje (una sola llamada)."""
    image_bytes = await image.read()
    try:
        result = generation_service.generar_en_foto(
            image_bytes=image_bytes,
            personaje_id=personaje_id,
            mime=image.content_type or "image/png",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al generar la imagen: {exc}") from exc

    return result
