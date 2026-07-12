"""
schemas/ubicaciones.py — Forma de los datos del CRUD de ubicaciones (Hito 6)
============================================================================

Entradas de POST /api/ubicaciones (crear) y PUT /api/ubicaciones/{id} (editar).
La validación fina (id válido/único, campos obligatorios) la hace
`ubicaciones_service`, que lanza ValueError (→ HTTP 400).
"""

from pydantic import BaseModel, Field


class UbicacionCrear(BaseModel):
    """Petición de POST /api/ubicaciones: alta de una ubicación nueva."""

    id: str = Field(description="Id de la ubicación. Minúsculas, números, - y _.")
    nombre: str = Field(description="Nombre visible en la carta.")
    prompt_imagen: str = Field(description="Descripción en inglés del fondo de la escena.")
    emoji: str | None = Field(default=None, description="Emoji de la carta (miniatura).")
    activo: bool = Field(default=True, description="Si aparece en el catálogo del niño.")


class UbicacionEditar(BaseModel):
    """Petición de PUT /api/ubicaciones/{id}: solo los campos a cambiar (el id no)."""

    nombre: str | None = None
    prompt_imagen: str | None = None
    emoji: str | None = None
    activo: bool | None = None
