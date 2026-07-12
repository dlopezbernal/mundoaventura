"""
routers/documentos.py — Endpoints de documentos del RAG por personaje (Hito 5)
==============================================================================

Gestión de la base de conocimiento sin terminal (la lógica vive en
services/documentos_service.py):

  GET    /api/personajes/{id}/documentos          → lista los documentos del personaje.
  POST   /api/personajes/{id}/documentos          → sube un fichero (.pdf/.txt/.md, multipart).
  POST   /api/personajes/{id}/documentos/url      → ingesta desde una URL de Wikipedia.
  DELETE /api/personajes/{id}/documentos/{doc_id} → borra un documento.
  POST   /api/personajes/{id}/reindex             → reindexa (incremental) ese personaje.
  POST   /api/reindex                             → reindexa TODO (global).

Al subir/ingerir/borrar se reindexa automáticamente al personaje afectado (solo
sus chunks). El control de acceso admin llega en el Hito 7.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.schemas.documentos import DocumentoUrlRequest
from backend.services import documentos_service

router = APIRouter(prefix="/api", tags=["Configuración · Documentos"])


@router.get("/personajes/{personaje_id}/documentos")
def listar_documentos(personaje_id: str):
    """Lista los documentos (metadatos) de un personaje."""
    return {"documentos": documentos_service.listar(personaje_id)}


@router.post("/personajes/{personaje_id}/documentos")
async def subir_documento(
    personaje_id: str,
    archivo: UploadFile = File(...),
    ya_en_ingles: bool = Form(False),
):
    """Sube un documento (.pdf/.txt/.md). Si no está en inglés, lo traduce (DeepL)."""
    contenido = await archivo.read()
    try:
        documento = documentos_service.subir(
            personaje_id, archivo.filename or "documento", contenido, ya_en_ingles
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "documento": documento}


@router.post("/personajes/{personaje_id}/documentos/url")
def ingerir_url(personaje_id: str, req: DocumentoUrlRequest):
    """Ingesta un artículo de Wikipedia desde su URL (opcionalmente traducido)."""
    try:
        documento = documentos_service.ingesta_url(personaje_id, req.url, req.ya_en_ingles)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "documento": documento}


@router.delete("/personajes/{personaje_id}/documentos/{documento_id}")
def borrar_documento(personaje_id: str, documento_id: int):
    """Borra un documento (fichero + metadatos) y reindexa al personaje."""
    try:
        documentos_service.eliminar(personaje_id, documento_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/personajes/{personaje_id}/reindex")
def reindexar_personaje(personaje_id: str):
    """Reindexado INCREMENTAL de un personaje (solo sus chunks)."""
    return {"ok": True, "resultado": documentos_service.reindexar_personaje(personaje_id)}


@router.post("/reindex")
def reindexar_todo():
    """Reindexado GLOBAL: borra y reconstruye toda la colección."""
    return {"ok": True, "resultado": documentos_service.reindexar_todo()}
