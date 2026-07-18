"""
routers/documentos.py — Endpoints de documentos del RAG por personaje (Hito 5/8)
=================================================================================

Gestión de la base de conocimiento sin terminal (la lógica vive en
services/documentos_service.py):

  GET    /api/personajes/{id}/documentos                    → lista los documentos del personaje.
  POST   /api/personajes/{id}/documentos                     → sube uno o varios ficheros (.pdf/.txt/.md, multipart).
  POST   /api/personajes/{id}/documentos/url                 → ingesta desde una URL de Wikipedia.
  GET    /api/personajes/{id}/documentos/{doc_id}/contenido  → texto actual (visor).
  PUT    /api/personajes/{id}/documentos/{doc_id}/contenido  → edita el texto (no PDF).
  GET    /api/personajes/{id}/documentos/{doc_id}/descargar  → descarga el fichero original.
  POST   /api/personajes/{id}/documentos/{doc_id}/copiar     → copia (independiente) a otro(s) personaje(s).
  DELETE /api/personajes/{id}/documentos/{doc_id}            → borra un documento.
  POST   /api/personajes/{id}/reindex                        → reindexa (incremental) ese personaje.
  POST   /api/reindex                                        → reindexa TODO (global).
  GET    /api/reindex/estado                                 → progreso del reindexado global en curso (sondeo).

Al subir/ingerir/editar/copiar/borrar se reindexa automáticamente al/los personaje(s)
afectado(s) (solo sus chunks). Todo el router va detrás del PIN de adulto (Hito 7,
aplicado en bloque desde main.py).

Un nombre de documento repetido para el mismo personaje se señaliza con
ConflictoDocumentoError → HTTP 409 (no 400), para que el frontend pueda distinguir
con fiabilidad "¿sobrescribir?" de cualquier otro error de validación.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.schemas.documentos import (
    DocumentoContenidoRequest,
    DocumentoCopiarRequest,
    DocumentoUrlRequest,
)
from backend.services import documentos_service

router = APIRouter(prefix="/api", tags=["Configuración · Documentos"])


@router.get("/personajes/{personaje_id}/documentos")
def listar_documentos(personaje_id: str):
    """Lista los documentos (metadatos) de un personaje."""
    return {"documentos": documentos_service.listar(personaje_id)}


@router.post("/personajes/{personaje_id}/documentos")
async def subir_documento(
    personaje_id: str,
    archivos: list[UploadFile] = File(...),
    sobrescribir: bool = Form(False),
):
    """Sube uno o varios documentos (.pdf/.txt/.md). El idioma se detecta con DeepL
    y se traducen a inglés automáticamente si hace falta.

    Con un único fichero responde `{"documento": ...}` (compatible con el shape
    anterior). Con varios, `{"documentos": [...], "errores": [...]}` (mejor
    esfuerzo: un fichero inválido no aborta el resto).
    """
    pares = [(archivo.filename or "documento", await archivo.read()) for archivo in archivos]
    if len(pares) == 1:
        nombre, contenido = pares[0]
        try:
            documento = documentos_service.subir(personaje_id, nombre, contenido, sobrescribir=sobrescribir)
        except documentos_service.ConflictoDocumentoError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "documento": documento}

    resultado = documentos_service.subir_varios(personaje_id, pares, sobrescribir=sobrescribir)
    return {"ok": True, **resultado}


@router.post("/personajes/{personaje_id}/documentos/url")
def ingerir_url(personaje_id: str, req: DocumentoUrlRequest):
    """Ingesta un artículo de Wikipedia desde su URL (traducido automáticamente si hace falta)."""
    try:
        documento = documentos_service.ingesta_url(personaje_id, req.url, sobrescribir=req.sobrescribir)
    except documentos_service.ConflictoDocumentoError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "documento": documento}


@router.get("/personajes/{personaje_id}/documentos/{documento_id}/contenido")
def obtener_contenido(personaje_id: str, documento_id: int):
    """Devuelve el texto actual de un documento (para el visor)."""
    try:
        return documentos_service.obtener_contenido(personaje_id, documento_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/personajes/{personaje_id}/documentos/{documento_id}/contenido")
def actualizar_contenido(personaje_id: str, documento_id: int, req: DocumentoContenidoRequest):
    """Edita el texto de un documento .txt/.md existente y reindexa al personaje."""
    try:
        documento = documentos_service.actualizar_contenido(personaje_id, documento_id, req.contenido)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "documento": documento}


@router.get("/personajes/{personaje_id}/documentos/{documento_id}/descargar")
def descargar_documento(personaje_id: str, documento_id: int):
    """Descarga el fichero original tal cual está en disco."""
    try:
        ruta = documentos_service.ruta_fichero(personaje_id, documento_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(ruta, filename=ruta.name)


@router.post("/personajes/{personaje_id}/documentos/{documento_id}/copiar")
def copiar_documento(personaje_id: str, documento_id: int, req: DocumentoCopiarRequest):
    """Copia (de forma independiente) un documento a uno o varios personajes destino.

    Mejor esfuerzo POR DESTINO (igual que la subida múltiple): un destino que
    falle (no existe, o conflicto de nombre sin `sobrescribir`) no aborta los
    demás, y su motivo queda en `errores` dentro de la respuesta 200 — no se
    traduce a un 409 global, porque con varios destinos un único código de estado
    no podría representar "unos sí, otros no". Solo el documento de ORIGEN
    inexistente aborta la petición entera (→ 400).
    """
    try:
        resultado = documentos_service.copiar_a(
            personaje_id, documento_id, req.personajes_destino, sobrescribir=req.sobrescribir
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **resultado}


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


@router.get("/reindex/estado")
def estado_reindex_todo():
    """Progreso del reindexado GLOBAL en curso (sondeado por el frontend para la barra)."""
    return documentos_service.estado_reindexado_todo()
