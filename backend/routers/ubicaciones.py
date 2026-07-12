"""
routers/ubicaciones.py — Endpoints del catálogo de ubicaciones (Hito 6)
=======================================================================

CRUD del catálogo de lugares (la lógica vive en services/ubicaciones_service.py):

  GET    /api/ubicaciones         → catálogo (por defecto solo activos; ?todos=1 incluye inactivos).
  POST   /api/ubicaciones         → alta de una ubicación nueva.
  PUT    /api/ubicaciones/{id}    → editar campos de una ubicación.
  DELETE /api/ubicaciones/{id}    → borrar una ubicación del catálogo.

Lo consumen tanto la pantalla del niño (elegir mundo) como la pestaña de
configuración. El control de acceso admin a la edición llega en el Hito 7.
"""

from fastapi import APIRouter, HTTPException

from backend.schemas.ubicaciones import UbicacionCrear, UbicacionEditar
from backend.services import ubicaciones_service

router = APIRouter(prefix="/api", tags=["Configuración · Ubicaciones"])


@router.get("/ubicaciones")
def listar_ubicaciones(todos: bool = False):
    """Catálogo de ubicaciones. Por defecto solo las activas; `?todos=1` incluye inactivas."""
    return {"ubicaciones": ubicaciones_service.listar(incluir_inactivos=todos)}


@router.post("/ubicaciones")
def crear_ubicacion(req: UbicacionCrear):
    """Crea una ubicación nueva. 400 si algo es inválido."""
    try:
        ubicacion = ubicaciones_service.crear(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "ubicacion": ubicacion}


@router.put("/ubicaciones/{ubicacion_id}")
def editar_ubicacion(ubicacion_id: str, req: UbicacionEditar):
    """Actualiza los campos indicados de una ubicación (el id no cambia). 400 si inválido."""
    try:
        ubicacion = ubicaciones_service.actualizar(
            ubicacion_id, req.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "ubicacion": ubicacion}


@router.delete("/ubicaciones/{ubicacion_id}")
def borrar_ubicacion(ubicacion_id: str):
    """Borra una ubicación del catálogo. 400 si no existe."""
    try:
        ubicaciones_service.eliminar(ubicacion_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}
