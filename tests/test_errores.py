"""Tests del saneado de errores internos (H2, tarea 7).

Un error interno NUNCA debe filtrar el mensaje del SDK (puede llevar URLs, claves
parciales, config). El cliente recibe un mensaje genérico + error_id; el detalle
real se queda en el log del servidor.
"""

from fastapi.testclient import TestClient

from backend import config, ratelimit
from backend.main import app
from backend.routers import errores
from backend.services import rag_service

_SECRETO = "SECRETO-INTERNO https://api.interna/key=abcd1234"


def test_error_500_no_filtra_el_detalle():
    exc = RuntimeError(_SECRETO)
    http = errores.error_500(exc, "contexto de prueba")
    assert http.status_code == 500
    assert "SECRETO" not in http.detail
    assert "api.interna" not in http.detail
    assert "código" in http.detail.lower()  # mensaje genérico con el error_id


def test_ask_error_interno_devuelve_generico_sin_filtrar(monkeypatch):
    ratelimit.limiter.reset()
    monkeypatch.setattr(config, "ACCESS_CODE", "")  # candado desactivado

    def _revienta(personaje_id, pregunta):
        raise RuntimeError(_SECRETO)

    monkeypatch.setattr(rag_service, "responder", _revienta)

    cliente = TestClient(app)
    r = cliente.post("/api/ask", json={"personaje_id": "t-rex", "pregunta": "hola"})

    assert r.status_code == 500
    cuerpo = r.text
    # Nada del mensaje interno del SDK aparece en la respuesta.
    assert "SECRETO" not in cuerpo
    assert "api.interna" not in cuerpo
    # Sí aparece el mensaje genérico con un error_id (12 hex).
    detail = r.json()["detail"]
    assert "código" in detail.lower()
