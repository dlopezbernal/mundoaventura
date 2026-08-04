"""
schemas/apis.py — Forma de los datos de la pantalla "APIs"
==========================================================

Define la ENTRADA de PUT /api/apis: un diccionario {proveedor: clave} con solo los
proveedores que se quieran actualizar. La validación (proveedor válido, clave no
vacía, sin saltos de línea) la hace `secrets_service.guardar`, que lanza ValueError
(→ HTTP 400) si algo falla. Las claves NUNCA se devuelven completas en las respuestas.
"""

from pydantic import BaseModel, Field


class ApisUpdateRequest(BaseModel):
    """Petición de PUT /api/apis: claves API a guardar en el .env."""

    claves: dict[str, str] = Field(
        default_factory=dict,
        description='Pares proveedor→clave, p. ej. {"deepl": "xxxx:fx"}. '
        "Solo los proveedores incluidos se actualizan.",
    )
