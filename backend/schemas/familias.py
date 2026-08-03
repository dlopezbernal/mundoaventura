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


class FamiliaVerificar(BaseModel):
    """Verificación del correo con el código (OTP) recibido."""

    email: str = Field(description="Correo del adulto.")
    codigo: str = Field(description="Código de verificación recibido por correo.")


class FamiliaReenviar(BaseModel):
    """Reenvío del código de verificación a un alta pendiente."""

    email: str = Field(description="Correo del adulto.")


class FamiliaPerfilUpdate(BaseModel):
    """Edición del perfil de la familia (nombre + nombres de los niños)."""

    nombre_familia: str | None = Field(default=None, description="Nuevo nombre de la familia.")
    ninos: list[str] | None = Field(default=None, description="Lista de nombres de los niños.")


class FamiliaPinSet(BaseModel):
    """Poner o cambiar el PIN de familia (4 dígitos). Requiere el actual si ya existe."""

    pin_nuevo: str = Field(description="Nuevo PIN de familia (4 dígitos).")
    pin_actual: str | None = Field(default=None, description="PIN actual (si ya había uno).")


class FamiliaPinVerificar(BaseModel):
    """Comprobación del PIN de familia (consentimiento de foto / editar perfil)."""

    pin: str = Field(description="PIN de familia a comprobar.")
