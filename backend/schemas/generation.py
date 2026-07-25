"""
schemas/generation.py — Forma de los datos de la generación
============================================================

La petición ahora es JSON sencillo (sin archivos): el niño solo elige un
personaje y una ubicación. Aquí definimos la ENTRADA y la SALIDA del endpoint
POST /api/generate.
"""

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Petición del endpoint POST /api/generate."""

    personaje_id: str = Field(..., description="Identificador del personaje (ej. 't-rex').")
    ubicacion_id: str = Field(..., description="Identificador de la ubicación (ej. 'laboratorio').")


class GenerateResponse(BaseModel):
    """Respuesta del endpoint POST /api/generate."""

    success: bool = Field(..., description="True si se generó la imagen correctamente.")

    # Eco de lo que se pidió (útil para el frontend).
    personaje_id: str = Field(..., description="Identificador del personaje generado.")
    ubicacion_id: str = Field(..., description="Identificador de la ubicación generada.")

    # La escena generada, como imagen (PNG/JPG según config) codificada en base64.
    result_png_base64: str = Field(
        ..., description="Escena generada (personaje + ubicación), codificada en base64."
    )
