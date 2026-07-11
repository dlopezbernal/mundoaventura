"""
routers/config.py — Endpoints de configuración (ajustes en caliente)
=====================================================================

Dos puertas de entrada (la lógica vive en services/settings_service.py):

  GET /api/config → ajustes vigentes + metadatos, y el estado de los secretos
                    (claves API) SIEMPRE enmascarado (nunca se envía la clave
                    completa al frontend).
  PUT /api/config → guarda ajustes y los aplica en caliente (sin reiniciar).
                    Devuelve qué ajustes cambiados requieren REINDEXAR ChromaDB.

Los secretos NO se editan aquí: eso llega en la pestaña "APIs" (Hito 2). Aquí solo
se muestran enmascarados (para pintar "configurado / falta").
"""

from fastapi import APIRouter, HTTPException

from backend import config as cfg
from backend.schemas.config import ConfigUpdateRequest
from backend.services import settings_service

router = APIRouter(prefix="/api", tags=["Configuración"])


def _enmascarar(secreto: str) -> str | None:
    """Devuelve el secreto enmascarado (solo los últimos 4), o None si está vacío."""
    if not secreto:
        return None
    if len(secreto) <= 4:
        return "•" * len(secreto)
    return "••••••" + secreto[-4:]


def _estado_secretos() -> list[dict]:
    """Estado de los 3 proveedores: configurado (bool) + valor enmascarado."""
    proveedores = [
        ("replicate", "REPLICATE_API_TOKEN", cfg.REPLICATE_API_TOKEN),
        ("deepl", "DEEPL_API_KEY", cfg.DEEPL_API_KEY),
        ("elevenlabs", "ELEVENLABS_API_KEY", cfg.ELEVENLABS_API_KEY),
    ]
    return [
        {
            "proveedor": proveedor,
            "variable": variable,
            "configurado": bool(valor),
            "enmascarado": _enmascarar(valor),
        }
        for proveedor, variable, valor in proveedores
    ]


@router.get("/config")
def obtener_config():
    """Devuelve los ajustes vigentes (con metadatos) y el estado de los secretos."""
    return {
        "ajustes": settings_service.exportar(),
        "secretos": _estado_secretos(),
    }


@router.put("/config")
def guardar_config(req: ConfigUpdateRequest):
    """Guarda ajustes y los aplica en caliente. Lanza 400 si algún valor es inválido."""
    try:
        reindex = settings_service.set_many(req.ajustes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "reindex_necesario": reindex}
