"""
schemas/admin.py — Forma de los datos del acceso de administrador (Hito 7)
==========================================================================

Entradas de los endpoints de administración (PIN de adulto e import/export). La
validación fina (PIN correcto/longitud, datos válidos) la hace `admin_service` y
los servicios de catálogo, que lanzan ValueError (→ HTTP 400).
"""

from typing import Any

from pydantic import BaseModel, Field


class AdminPin(BaseModel):
    """PIN de adulto (para crear el PIN o iniciar sesión)."""

    pin: str = Field(description="PIN de adulto.")


class AdminCambiar(BaseModel):
    """Cambio de PIN: requiere el actual."""

    pin_actual: str = Field(description="PIN actual.")
    pin_nuevo: str = Field(description="PIN nuevo.")


class ImportRequest(BaseModel):
    """Configuración a importar (la que devuelve GET /api/admin/export)."""

    datos: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON de configuración: ajustes + personajes + ubicaciones.",
    )
