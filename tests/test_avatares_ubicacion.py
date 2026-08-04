"""Tests de la imagen del carrusel de UBICACIONES (Hito 10): fichero + DTO + endpoints.

Espejo de test_avatares.py (personajes). NO se llama a Replicate: la generación se
mockea. Se aísla la BBDD y los directorios (avatares/documentos) en un tmp por test.
"""

import pytest
from fastapi.testclient import TestClient

from backend import config, db
from backend.main import app
from backend.services import admin_service, generation_service, ubicaciones_service

_CLIENTE = TestClient(app)

_PNG_FAKE = b"\x89PNG\r\n\x1a\n-imagen-ubicacion-de-prueba"


@pytest.fixture(autouse=True)
def _entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "test_avatares_ubi.sqlite3")
    monkeypatch.setattr(config, "AVATARES_DIR", tmp_path / "avatares")
    monkeypatch.setattr(db, "_engine", None)
    ubicaciones_service._invalidar()
    db.init_db()
    ubicaciones_service.crear({"id": "egipto", "nombre": "Egipto", "prompt_imagen": "a temple"})
    yield
    monkeypatch.setattr(db, "_engine", None)
    ubicaciones_service._invalidar()


def test_sin_imagen_el_dto_y_la_ruta_son_none():
    assert ubicaciones_service.obtener("egipto")["avatar_url"] is None
    assert ubicaciones_service.ruta_avatar("egipto") is None


def test_guardar_escribe_fichero_y_marca_el_dto():
    u = ubicaciones_service.guardar_avatar("egipto", _PNG_FAKE)
    assert u["avatar_url"].startswith("/api/ubicaciones/egipto/avatar?v=")
    ruta = ubicaciones_service.ruta_avatar("egipto")
    assert ruta is not None
    assert ruta.read_bytes() == _PNG_FAKE


def test_borrar_elimina_fichero_y_dto():
    ubicaciones_service.guardar_avatar("egipto", _PNG_FAKE)
    u = ubicaciones_service.borrar_avatar("egipto")
    assert u["avatar_url"] is None
    assert ubicaciones_service.ruta_avatar("egipto") is None


def test_eliminar_ubicacion_borra_su_imagen():
    ubicaciones_service.guardar_avatar("egipto", _PNG_FAKE)
    ruta = ubicaciones_service.ruta_avatar("egipto")
    assert ruta.exists()
    ubicaciones_service.eliminar("egipto")
    assert not ruta.exists()


def test_guardar_ubicacion_inexistente_falla():
    with pytest.raises(ValueError):
        ubicaciones_service.guardar_avatar("fantasma", _PNG_FAKE)


# --- Endpoints ---
def test_get_avatar_404_si_no_hay():
    assert _CLIENTE.get("/api/ubicaciones/egipto/avatar").status_code == 404


def test_get_avatar_sirve_el_png():
    ubicaciones_service.guardar_avatar("egipto", _PNG_FAKE)
    r = _CLIENTE.get("/api/ubicaciones/egipto/avatar")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == _PNG_FAKE


def test_post_avatar_genera_guarda_y_devuelve_dto(monkeypatch):
    app.dependency_overrides[admin_service.requiere_admin] = lambda: None
    monkeypatch.setattr(generation_service, "generar_avatar_ubicacion", lambda uid: _PNG_FAKE)
    try:
        r = _CLIENTE.post("/api/ubicaciones/egipto/avatar")
        assert r.status_code == 200
        assert r.json()["ubicacion"]["avatar_url"].startswith("/api/ubicaciones/egipto/avatar?v=")
        assert ubicaciones_service.ruta_avatar("egipto").read_bytes() == _PNG_FAKE
    finally:
        app.dependency_overrides.pop(admin_service.requiere_admin, None)


def test_delete_avatar_lo_quita():
    app.dependency_overrides[admin_service.requiere_admin] = lambda: None
    try:
        ubicaciones_service.guardar_avatar("egipto", _PNG_FAKE)
        r = _CLIENTE.delete("/api/ubicaciones/egipto/avatar")
        assert r.status_code == 200
        assert r.json()["ubicacion"]["avatar_url"] is None
        assert ubicaciones_service.ruta_avatar("egipto") is None
    finally:
        app.dependency_overrides.pop(admin_service.requiere_admin, None)
