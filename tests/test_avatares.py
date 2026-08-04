"""Tests del avatar del carrusel (Hito 10): fichero en disco + DTO + endpoints.

NO se llama a Replicate: la generación (`generation_service.generar_avatar`) se
mockea. Se aísla la BBDD y los directorios (avatares/documentos) en un tmp por test,
igual que `test_familias.py`.
"""

import pytest
from fastapi.testclient import TestClient

from backend import config, db
from backend.main import app
from backend.services import admin_service, generation_service, personajes_service

_CLIENTE = TestClient(app)

# Bytes cualquiera que hagan de "PNG" (no se decodifican en ningún sitio).
_PNG_FAKE = b"\x89PNG\r\n\x1a\n-avatar-transparente-de-prueba"


@pytest.fixture(autouse=True)
def _entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "test_avatares.sqlite3")
    monkeypatch.setattr(config, "AVATARES_DIR", tmp_path / "avatares")
    monkeypatch.setattr(config, "DOCUMENTOS_DIR", tmp_path / "documentos")
    monkeypatch.setattr(db, "_engine", None)  # recrea el motor sobre la BBDD temporal
    personajes_service._invalidar()
    db.init_db()
    personajes_service.crear({"id": "leo", "nombre": "Leo", "prompt_imagen": "a kind inventor"})
    yield
    monkeypatch.setattr(db, "_engine", None)
    personajes_service._invalidar()


def test_sin_avatar_el_dto_y_la_ruta_son_none():
    assert personajes_service.obtener("leo")["avatar_url"] is None
    assert personajes_service.ruta_avatar("leo") is None


def test_guardar_avatar_escribe_fichero_y_marca_el_dto():
    p = personajes_service.guardar_avatar("leo", _PNG_FAKE)
    assert p["avatar_url"].startswith("/api/personajes/leo/avatar?v=")
    ruta = personajes_service.ruta_avatar("leo")
    assert ruta is not None
    assert ruta.read_bytes() == _PNG_FAKE


def test_regenerar_cambia_el_token_de_version(monkeypatch):
    monkeypatch.setattr(personajes_service.time, "time", lambda: 1000.0)
    url1 = personajes_service.guardar_avatar("leo", _PNG_FAKE)["avatar_url"]
    monkeypatch.setattr(personajes_service.time, "time", lambda: 2000.0)
    url2 = personajes_service.guardar_avatar("leo", _PNG_FAKE)["avatar_url"]
    assert url1.endswith("v=1000")
    assert url2.endswith("v=2000")


def test_borrar_avatar_elimina_fichero_y_dto():
    personajes_service.guardar_avatar("leo", _PNG_FAKE)
    p = personajes_service.borrar_avatar("leo")
    assert p["avatar_url"] is None
    assert personajes_service.ruta_avatar("leo") is None


def test_eliminar_personaje_borra_su_avatar():
    personajes_service.guardar_avatar("leo", _PNG_FAKE)
    ruta = personajes_service.ruta_avatar("leo")
    assert ruta.exists()
    personajes_service.eliminar("leo")
    assert not ruta.exists()


def test_guardar_avatar_personaje_inexistente_falla():
    with pytest.raises(ValueError):
        personajes_service.guardar_avatar("fantasma", _PNG_FAKE)


# --- Endpoints ---
def test_get_avatar_404_si_no_hay():
    assert _CLIENTE.get("/api/personajes/leo/avatar").status_code == 404


def test_get_avatar_sirve_el_png():
    personajes_service.guardar_avatar("leo", _PNG_FAKE)
    r = _CLIENTE.get("/api/personajes/leo/avatar")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == _PNG_FAKE


def test_post_avatar_genera_guarda_y_devuelve_dto(monkeypatch):
    app.dependency_overrides[admin_service.requiere_admin] = lambda: None
    monkeypatch.setattr(generation_service, "generar_avatar", lambda pid: _PNG_FAKE)
    try:
        r = _CLIENTE.post("/api/personajes/leo/avatar")
        assert r.status_code == 200
        assert r.json()["personaje"]["avatar_url"].startswith("/api/personajes/leo/avatar?v=")
        assert personajes_service.ruta_avatar("leo").read_bytes() == _PNG_FAKE
    finally:
        app.dependency_overrides.pop(admin_service.requiere_admin, None)


def test_delete_avatar_lo_quita(monkeypatch):
    app.dependency_overrides[admin_service.requiere_admin] = lambda: None
    try:
        personajes_service.guardar_avatar("leo", _PNG_FAKE)
        r = _CLIENTE.delete("/api/personajes/leo/avatar")
        assert r.status_code == 200
        assert r.json()["personaje"]["avatar_url"] is None
        assert personajes_service.ruta_avatar("leo") is None
    finally:
        app.dependency_overrides.pop(admin_service.requiere_admin, None)
