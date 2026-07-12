"""
schemas/personajes.py — Forma de los datos del CRUD de personajes (Hito 4)
==========================================================================

Entradas de POST /api/personajes (crear) y PUT /api/personajes/{id} (editar). La
validación fina (id válido/único, campos obligatorios, categoría permitida) la hace
`personajes_service`, que lanza ValueError (→ HTTP 400) si algo no cuadra.

En la creación, `id`, `nombre` y `prompt_imagen` son obligatorios; el resto es
opcional (un personaje sin `voz_id` responde solo en texto). En la edición, todos
los campos son opcionales: solo se actualiza lo que llega.
"""

from pydantic import BaseModel, Field


class PersonajeCrear(BaseModel):
    """Petición de POST /api/personajes: alta de un personaje nuevo."""

    id: str = Field(description="Id del personaje (invariante). Minúsculas, números, - y _.")
    nombre: str = Field(description="Nombre con el que se presenta en el chat.")
    prompt_imagen: str = Field(description="Descripción en inglés para generar su imagen.")
    categoria: str | None = Field(
        default=None, description="prehistorico | historico | ficticio (agrupa la carta)."
    )
    emoji: str | None = Field(default=None, description="Emoji de la carta (miniatura).")
    voz_id: str | None = Field(
        default=None, description="Voz de ElevenLabs (voz_id). Vacío = solo texto."
    )
    prompt_sistema_override: str | None = Field(
        default=None, description="Prompt de sistema propio (opcional; si no, usa el general)."
    )
    activo: bool = Field(default=True, description="Si aparece en el catálogo del niño.")


class PersonajeEditar(BaseModel):
    """Petición de PUT /api/personajes/{id}: solo los campos a cambiar (el id no)."""

    nombre: str | None = None
    prompt_imagen: str | None = None
    categoria: str | None = None
    emoji: str | None = None
    voz_id: str | None = None
    prompt_sistema_override: str | None = None
    activo: bool | None = None
