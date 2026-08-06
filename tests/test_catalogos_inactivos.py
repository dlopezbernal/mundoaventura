"""Los catálogos se leen en público, pero `?todos=1` NO.

Un personaje o una ubicación desactivados lo están porque un adulto decidió
retirarlos: su existencia es información de administración. La lista de ACTIVOS
sigue siendo pública a propósito, porque la SPA la necesita para pintar el
carrusel antes de que el niño tenga sesión.

Este fichero fija esa frontera para que no se reabra por descuido al tocar los
routers de catálogo.
"""

import pytest
from fastapi.testclient import TestClient

from backend import config, db
from backend.main import app
from backend.services import admin_service

_CLIENTE = TestClient(app)


@pytest.fixture(autouse=True)
def _bbdd_temporal(tmp_path, monkeypatch):
    """BBDD nueva por test: si no, la credencial de admin del entorno real
    contaminaría el resultado (y estos tests van justo de esa credencial)."""
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "test_catalogos.sqlite3")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(admin_service, "_RETARDO_LOGIN", 0)
    admin_service._tokens.clear()
    db.init_db()
    yield
    monkeypatch.setattr(db, "_engine", None)
    admin_service._tokens.clear()


def _token_admin() -> str:
    """Configura la credencial de admin en la BBDD temporal y devuelve un token."""
    r = _CLIENTE.post("/api/admin/setup", json={"password": "contrasena-de-prueba"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---------------------------------------------------------------------------
# Lo público sigue siendo público
# ---------------------------------------------------------------------------
def test_catalogos_activos_son_publicos():
    """Sin ninguna credencial se pueden leer los catálogos: lo necesita el niño."""
    r = _CLIENTE.get("/api/personajes")
    assert r.status_code == 200
    assert "personajes" in r.json()

    r = _CLIENTE.get("/api/ubicaciones")
    assert r.status_code == 200
    assert "ubicaciones" in r.json()


# ---------------------------------------------------------------------------
# `?todos=1` exige credencial de administración
# ---------------------------------------------------------------------------
def test_personajes_todos_sin_token_da_401():
    r = _CLIENTE.get("/api/personajes", params={"todos": 1})
    assert r.status_code == 401, r.text


def test_ubicaciones_todos_sin_token_da_401():
    r = _CLIENTE.get("/api/ubicaciones", params={"todos": 1})
    assert r.status_code == 401, r.text


def test_todos_con_token_de_admin_funciona():
    cabeceras = {"X-Admin-Token": _token_admin()}

    r = _CLIENTE.get("/api/personajes", params={"todos": 1}, headers=cabeceras)
    assert r.status_code == 200, r.text
    assert "personajes" in r.json()

    r = _CLIENTE.get("/api/ubicaciones", params={"todos": 1}, headers=cabeceras)
    assert r.status_code == 200, r.text
    assert "ubicaciones" in r.json()


def test_token_invalido_no_cuela():
    cabeceras = {"X-Admin-Token": "no-es-un-token"}
    assert (
        _CLIENTE.get("/api/personajes", params={"todos": 1}, headers=cabeceras).status_code == 401
    )
    assert (
        _CLIENTE.get("/api/ubicaciones", params={"todos": 1}, headers=cabeceras).status_code == 401
    )


def test_todos_falso_no_pide_credencial():
    """`?todos=0` es equivalente a no pasarlo: sigue siendo público."""
    assert _CLIENTE.get("/api/personajes", params={"todos": 0}).status_code == 200
    assert _CLIENTE.get("/api/ubicaciones", params={"todos": 0}).status_code == 200
