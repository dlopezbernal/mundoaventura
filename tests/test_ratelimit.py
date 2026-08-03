"""Tests del rate limit por IP y su degradación amable (H2, tarea 5).

- /api/ask: al superar el límite, el personaje responde EN PERSONAJE (200 con
  origen 'LIMITE' y MENSAJE_LIMITE), no un 429 crudo.
- /api/generate: al superar el límite o agotar el cupo diario, se devuelve 429 con
  el mensaje amable.

Se stubean los servicios (sin red) y se usa una BBDD temporal para el cupo. El
limiter (singleton en memoria) se resetea antes de cada test para no arrastrar
cuentas entre pruebas.
"""

import pytest
from fastapi.testclient import TestClient

from backend import config, db, ratelimit
from backend.main import app
from backend.services import cuota_service, generation_service, rag_service

_CLIENTE = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_limiter():
    ratelimit.limiter.reset()
    yield
    ratelimit.limiter.reset()


@pytest.fixture
def _db_temp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "rl_test.sqlite3")
    monkeypatch.setattr(db, "_engine", None)
    yield
    monkeypatch.setattr(db, "_engine", None)


def test_ask_degrada_en_personaje_al_superar_el_limite(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_ASK", "2/minute")
    monkeypatch.setattr(
        rag_service,
        "responder",
        lambda personaje_id, pregunta, *a: {
            "success": True,
            "personaje_id": personaje_id,
            "pregunta": pregunta,
            "respuesta": "real",
            "origen": "RAG",
        },
    )
    cuerpo = {"personaje_id": "t-rex", "pregunta": "hola"}
    r1 = _CLIENTE.post("/api/ask", json=cuerpo)
    r2 = _CLIENTE.post("/api/ask", json=cuerpo)
    r3 = _CLIENTE.post("/api/ask", json=cuerpo)  # supera el límite

    assert (r1.status_code, r1.json()["origen"]) == (200, "RAG")
    assert (r2.status_code, r2.json()["origen"]) == (200, "RAG")
    # El 3º NO es un 429 crudo: 200 en personaje con el mensaje de "descanso".
    assert r3.status_code == 200
    assert r3.json()["origen"] == "LIMITE"
    assert r3.json()["respuesta"] == config.MENSAJE_LIMITE


def test_generate_429_al_agotar_el_cupo_diario(_db_temp, monkeypatch):
    # Rate limit holgado (que no interfiera) y cupo diario de 2.
    monkeypatch.setattr(config, "RATE_LIMIT_GENERATE", "100/minute")
    monkeypatch.setattr(config, "MAX_IMAGENES_DIA", 2)
    monkeypatch.setattr(
        generation_service,
        "generar_escena",
        lambda personaje_id, ubicacion_id: {
            "success": True,
            "personaje_id": personaje_id,
            "ubicacion_id": ubicacion_id,
            "result_png_base64": "AAAA",
        },
    )
    cuerpo = {"personaje_id": "t-rex", "ubicacion_id": "laboratorio"}
    r1 = _CLIENTE.post("/api/generate", json=cuerpo)
    r2 = _CLIENTE.post("/api/generate", json=cuerpo)
    r3 = _CLIENTE.post("/api/generate", json=cuerpo)  # cupo agotado

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["detail"] == config.MENSAJE_LIMITE
    # Solo se contaron las 2 que salieron bien.
    assert cuota_service.estado()["imagenes_hoy"] == 2
