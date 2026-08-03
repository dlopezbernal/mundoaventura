"""
schemas/familias.py — Entrada de los endpoints de cuentas de familia (Hito 9.2)
================================================================================

Formularios de alta e inicio de sesión de una familia. La validación fina (email
válido, longitud de contraseña, email ya registrado, credenciales) la hace
`familias_service`, que lanza ValueError (→ HTTP 400).
"""

from pydantic import BaseModel, Field


class FamiliaSignup(BaseModel):
    """Alta de una familia (self-signup)."""

    email: str = Field(description="Correo del adulto (credencial de acceso).")
    password: str = Field(description="Contraseña de la familia.")
    nombre_familia: str = Field(description="Nombre de la familia, para personalizar la app.")


class FamiliaLogin(BaseModel):
    """Inicio de sesión de una familia."""

    email: str = Field(description="Correo del adulto.")
    password: str = Field(description="Contraseña de la familia.")
