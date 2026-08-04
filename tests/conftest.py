"""Configuración común de la suite de tests.

Solo contiene lo que debe valer para TODOS los tests; el aislamiento de la BBDD y
demás sigue declarándose en cada fichero, que es donde se entiende.
"""

import pytest

from backend import config


@pytest.fixture(autouse=True)
def _sin_sesion_de_familia(monkeypatch):
    """Desactiva `EXIGIR_SESION_FAMILIA` en toda la suite salvo donde se pida.

    El toggle (por defecto TRUE en producción) exige `X-Family-Token` en
    /api/generate, /api/ask y /api/transcribe. La mayoría de los tests que llaman a
    esos endpoints no van de autenticación: van de rate limit, de validación de
    entrada, de saneado de errores o de frames SSE. Montarles una sesión de familia
    real solo para llegar al código que sí quieren probar añadiría ruido a cada
    fichero y escondería lo que cada test afirma.

    Los tests que SÍ ejercen la puerta la reactivan explícitamente con
    `monkeypatch.setattr(config, "EXIGIR_SESION_FAMILIA", True)` (ver
    `test_acceso.py`), que es donde debe leerse esa intención.
    """
    monkeypatch.setattr(config, "EXIGIR_SESION_FAMILIA", False)
