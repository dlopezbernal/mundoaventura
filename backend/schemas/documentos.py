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
    """Petición de POST /api/personajes/{id}/documentos/url.

    El idioma ya no lo indica el adulto: se detecta automáticamente con DeepL
    (ver documentos_service._preparar_texto) y se traduce si no está en inglés.
    """

    url: str = Field(description="URL del artículo de Wikipedia a ingerir.")
    sobrescribir: bool = Field(
        default=False,
        description="Forzar sobrescritura si ya existe un documento con ese nombre.",
    )


class DocumentoContenidoRequest(BaseModel):
    """Petición de PUT /api/personajes/{id}/documentos/{documento_id}/contenido.

    El idioma se detecta automáticamente con DeepL (igual que al subir).
    """

    contenido: str = Field(description="Texto nuevo del documento.")


class DocumentoCopiarRequest(BaseModel):
    """Petición de POST /api/personajes/{id}/documentos/{documento_id}/copiar."""

    personajes_destino: list[str] = Field(description="IDs de los personajes destino.")
    sobrescribir: bool = Field(
        default=False,
        description="Forzar sobrescritura si ya existe un documento con ese nombre en el destino.",
    )
