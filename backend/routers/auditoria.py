"""
routers/auditoria.py — Informe de auditoría de uso (Admin)
==========================================================

Detrás del acceso admin. Deja consultar el registro de actividad de las familias
(auditoria_service), filtrarlo y exportarlo a CSV. La configuración (activar,
contenido, retención) se edita en la pestaña "Auditoría" con el ConfigForm normal
(categoría `auditoria`), no aquí.

  GET  /api/auditoria          → página de eventos (filtros: tipo, familia_id).
  GET  /api/auditoria/export   → CSV de todos los eventos que cumplen el filtro.
  POST /api/auditoria/purgar   → aplica la retención ahora (borra los antiguos).
"""

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from backend.schemas.respuestas import AuditoriaLista
from backend.services import admin_service, auditoria_service

router = APIRouter(
    prefix="/api/auditoria",
    tags=["Auditoría"],
    dependencies=[Depends(admin_service.requiere_admin)],
)


@router.get("", response_model=AuditoriaLista)
def listar(
    limite: int = 200,
    offset: int = 0,
    tipo: str | None = None,
    familia_id: str | None = None,
):
    """Eventos de auditoría (más recientes primero), con filtros y total."""
    return auditoria_service.listar(
        limite=min(max(limite, 1), 1000), offset=max(offset, 0), tipo=tipo, familia_id=familia_id
    )


@router.get("/export")
def exportar(tipo: str | None = None, familia_id: str | None = None):
    """Exporta a CSV los eventos que cumplen el filtro (el 'fichero LOG' descargable)."""
    csv = auditoria_service.exportar_csv(tipo=tipo, familia_id=familia_id)
    return PlainTextResponse(
        csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=auditoria.csv"},
    )


@router.post("/purgar")
def purgar():
    """Aplica la retención ahora: borra los registros más antiguos que el límite."""
    return {"ok": True, "purgados": auditoria_service.purgar_antiguos()}
