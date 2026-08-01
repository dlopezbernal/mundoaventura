"""Tests del candado del túnel por código de acceso (H2, tarea 5).

Cuando ACCESS_CODE está configurado, los endpoints del niño (chat, generación,
voz) exigen la cabecera X-Access-Code correcta; si no, 401. Con ACCESS_CODE vacío
el candado queda desactivado. Se usa TestClient SIN context manager (no dispara el
lifespan → ni red ni seeding); el 401 lo produce la dependencia antes del cuerpo.
"""

from fastapi.testclient import TestClient

from backend import config
from backend.main import app

_CLIENTE = TestClient(app)


def test_sin_codigo_es_401(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_CODE", "secreto")
    r = _CLIENTE.post("/api/ask", json={"personaje_id": "t-rex", "pregunta": "hola"})
    assert r.status_code == 401


def test_codigo_incorrecto_es_401(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_CODE", "secreto")
    r = _CLIENTE.post(
        "/api/ask",
        json={"personaje_id": "t-rex", "pregunta": "hola"},
        headers={"X-Access-Code": "otro"},
    )
    assert r.status_code == 401


def test_generate_tambien_esta_protegido(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_CODE", "secreto")
    r = _CLIENTE.post(
        "/api/generate", json={"personaje_id": "t-rex", "ubicacion_id": "laboratorio"}
    )
    assert r.status_code == 401


def test_codigo_correcto_pasa_el_candado(monkeypatch):
    # Con el código correcto, el candado deja pasar y ya se aplica la validación
    # del cuerpo: una pregunta demasiado larga da 422 (NO 401), lo que prueba que
    # el candado se superó.
    monkeypatch.setattr(config, "ACCESS_CODE", "secreto")
    r = _CLIENTE.post(
        "/api/ask",
        json={"personaje_id": "t-rex", "pregunta": "x" * 1000},
        headers={"X-Access-Code": "secreto"},
    )
    assert r.status_code == 422


def test_candado_desactivado_no_pide_codigo(monkeypatch):
    # ACCESS_CODE vacío = sin candado: sin cabecera NO da 401 (llega a validación).
    monkeypatch.setattr(config, "ACCESS_CODE", "")
    r = _CLIENTE.post("/api/ask", json={"personaje_id": "t-rex", "pregunta": "x" * 1000})
    assert r.status_code == 422  # 422 por la pregunta larga, no 401
