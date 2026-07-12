"""
schemas/documentos.py — Forma de los datos de los documentos del RAG (Hito 5)
=============================================================================

La subida de ficheros va por multipart (UploadFile + Form), así que aquí solo se
modela la ENTRADA de la ingesta desde URL. La validación (URL de Wikipedia válida,
artículo existente, DeepL disponible al traducir) la hace `documentos_service`,
que lanza ValueError (→ HTTP 400).
"""

from pydantic import BaseModel, Field


class DocumentoUrlRequest(BaseModel):
    """Petición de POST /api/personajes/{id}/documentos/url."""

    url: str = Field(description="URL del artículo de Wikipedia a ingerir.")
    ya_en_ingles: bool = Field(
        default=False,
        description="Si el contenido ya está en inglés (no se traduce con DeepL).",
    )
