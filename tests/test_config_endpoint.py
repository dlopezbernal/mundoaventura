"""Tests de los endpoints de configuración que exponen ajustes (contrato de salida).

Su razón de ser es de REGRESIÓN: al autogenerar los tipos (H9.1) los endpoints ganaron
`response_model`, que solo VALIDA la respuesta si un test llama al endpoint. Sin estos
tests, un modelo demasiado estrecho (p. ej. `valor` sin `float`) rompía GET /api/config
en caliente y nadie se enteraba hasta abrir la pantalla de configuración. Aquí se ejercita
la validación real contra los ajustes de verdad, que incluyen decimales (umbrales,
temperatura del LLM).
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import admin_service

_CLIENTE = TestClient(app)


@pytest.fixture(autouse=True)
def _sortear_admin():
    """La zona de config va tras la contraseña de adulto: se sortea la dependencia solo
    en estos tests y se restaura después (el `app` es un singleton compartido)."""
    app.dependency_overrides[admin_service.requiere_admin] = lambda: None
    yield
    app.dependency_overrides.pop(admin_service.requiere_admin, None)


def test_get_config_valida_response_model_con_floats():
    """GET /api/config devuelve 200 y el response_model acepta ajustes decimales."""
    r = _CLIENTE.get("/api/config")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert "ajustes" in cuerpo and "secretos" in cuerpo
    # Debe haber al menos un ajuste con valor float (umbral/temperatura); si el
    # response_model no aceptara float, este endpoint habría dado 500 arriba.
    valores = [a["valor"] for a in cuerpo["ajustes"]]
    assert any(isinstance(v, float) for v in valores), "se esperaban ajustes decimales"


def test_get_admin_export_valida_response_model():
    """GET /api/admin/export serializa ajustes (con floats) + catálogos sin romper."""
    r = _CLIENTE.get("/api/admin/export")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["version"] == 1
    assert isinstance(cuerpo["ajustes"], dict)
    assert isinstance(cuerpo["personajes"], list)
