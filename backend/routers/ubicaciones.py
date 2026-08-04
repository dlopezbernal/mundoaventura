"""
routers/ubicaciones.py — Endpoints del catálogo de ubicaciones (Hito 6)
=======================================================================

CRUD del catálogo de lugares (la lógica vive en services/ubicaciones_service.py):

  GET    /api/ubicaciones         → catálogo (por defecto solo activos; ?todos=1 incluye inactivos).
  POST   /api/ubicaciones         → alta de una ubicación nueva.
  PUT    /api/ubicaciones/{id}    → editar campos de una ubicación.
  DELETE /api/ubicaciones/{id}    → borrar una ubicación del catálogo.

Lo consumen tanto la pantalla del niño (elegir mundo) como la pestaña de
configuración. Las escrituras (POST/PUT/DELETE) van detrás del control de acceso
admin (`requiere_admin`, enchufado en `main.py`); los `GET` del catálogo siguen
públicos para el flujo del niño.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.schemas.respuestas import (
    OkResponse,
    UbicacionesResponse,
    UbicacionMutacion,
)
from backend.schemas.ubicaciones import UbicacionCrear, UbicacionEditar
from backend.services import admin_service, generation_service, ubicaciones_service

router = APIRouter(prefix="/api", tags=["Configuración · Ubicaciones"])

# El catálogo se LEE en público (lo usa el niño); las escrituras exigen el PIN.
_admin = [Depends(admin_service.requiere_admin)]


@router.get("/ubicaciones", response_model=UbicacionesResponse)
def listar_ubicaciones(todos: bool = False):
    """Catálogo de ubicaciones. Por defecto solo las activas; `?todos=1` incluye inactivas."""
    return {"ubicaciones": ubicaciones_service.listar(incluir_inactivos=todos)}


@router.post("/ubicaciones", dependencies=_admin, response_model=UbicacionMutacion)
def crear_ubicacion(req: UbicacionCrear):
    """Crea una ubicación nueva. 400 si algo es inválido."""
    try:
        ubicacion = ubicaciones_service.crear(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "ubicacion": ubicacion}


@router.put("/ubicaciones/{ubicacion_id}", dependencies=_admin, response_model=UbicacionMutacion)
def editar_ubicacion(ubicacion_id: str, req: UbicacionEditar):
    """Actualiza los campos indicados de una ubicación (el id no cambia). 400 si inválido."""
    try:
        ubicacion = ubicaciones_service.actualizar(ubicacion_id, req.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "ubicacion": ubicacion}


@router.delete("/ubicaciones/{ubicacion_id}", dependencies=_admin, response_model=OkResponse)
def borrar_ubicacion(ubicacion_id: str):
    """Borra una ubicación del catálogo. 400 si no existe."""
    try:
        ubicaciones_service.eliminar(ubicacion_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post(
    "/ubicaciones/{ubicacion_id}/avatar", dependencies=_admin, response_model=UbicacionMutacion
)
def generar_avatar_ubicacion(ubicacion_id: str):
    """Genera (bajo demanda, coste de Replicate) la imagen transparente del carrusel.

    Dos llamadas a Replicate (imagen + recorte); es `def` → threadpool. 400 si la
    ubicación no existe o falta el token.
    """
    try:
        png = generation_service.generar_avatar_ubicacion(ubicacion_id)
        ubicacion = ubicaciones_service.guardar_avatar(ubicacion_id, png)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "ubicacion": ubicacion}


@router.delete(
    "/ubicaciones/{ubicacion_id}/avatar", dependencies=_admin, response_model=UbicacionMutacion
)
def borrar_avatar_ubicacion(ubicacion_id: str):
    """Quita la imagen (vuelve al emoji). 400 si la ubicación no existe."""
    try:
        ubicacion = ubicaciones_service.borrar_avatar(ubicacion_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "ubicacion": ubicacion}


@router.get("/ubicaciones/{ubicacion_id}/avatar")
def obtener_avatar_ubicacion(ubicacion_id: str):
    """Sirve el PNG transparente (público: lo usa el carrusel del niño)."""
    ruta = ubicaciones_service.ruta_avatar(ubicacion_id)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Esta ubicación no tiene imagen.")
    return FileResponse(ruta, media_type="image/png")
