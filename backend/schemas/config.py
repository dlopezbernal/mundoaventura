"""
schemas/config.py — Forma de los datos del endpoint de configuración
=====================================================================

Define la ENTRADA de PUT /api/config: un diccionario de pares clave→valor con los
ajustes a guardar. La validación fina (tipos, rangos, coherencia de umbrales) la
hace `settings_service.set_many`, que lanza ValueError (→ HTTP 400) si algo falla.
"""

from typing import Any

from pydantic import BaseModel, Field


class ConfigUpdateRequest(BaseModel):
    """Petición de PUT /api/config: ajustes a guardar (aplican en caliente)."""

    ajustes: dict[str, Any] = Field(
        default_factory=dict,
        description="Pares clave→valor a guardar, p. ej. "
        '{"EVALUATOR_UMBRAL_BAJO": 0.7, "EVALUATOR_MODE": "hibrido"}.',
    )
