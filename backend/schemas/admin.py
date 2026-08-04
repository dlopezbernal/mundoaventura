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
    """Contraseña de administración (crear o iniciar sesión), con código 2FA opcional."""

    pin: str = Field(description="Contraseña de administración.")
    # Segundo factor (Hito 9.2d): solo se envía si el 2FA está activo. En el primer
    # intento de login puede ir vacío; el backend responde 'requiere_2fa' y el frontend
    # lo reenvía con el código.
    codigo: str | None = Field(default=None, description="Código 2FA (TOTP o recuperación).")


class AdminCambiar(BaseModel):
    """Cambio de contraseña de administración: requiere la actual."""

    pin_actual: str = Field(description="Contraseña actual.")
    pin_nuevo: str = Field(description="Contraseña nueva.")


class Admin2FAConfirmar(BaseModel):
    """Confirmación del enrolamiento 2FA con un código del autenticador."""

    codigo: str = Field(description="Código de 6 dígitos del autenticador.")


class Admin2FADesactivar(BaseModel):
    """Desactivación del 2FA: exige la contraseña actual (re-autenticación)."""

    pin: str = Field(description="Contraseña de administración actual.")


class ImportRequest(BaseModel):
    """Configuración a importar (la que devuelve GET /api/admin/export)."""

    datos: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON de configuración: ajustes + personajes + ubicaciones.",
    )
