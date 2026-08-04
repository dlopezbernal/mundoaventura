"""Tests de services/resiliencia.py — reintentos con backoff (H2, tarea 2).

Cubre la clasificación de errores (qué es transitorio y qué no) y la mecánica de
`reintentar`: reintenta los 429/5xx/timeout, se rinde tras agotar los intentos, y
propaga de inmediato los errores NO transitorios (4xx que no sean 429).
"""

import httpx
import pytest

from backend.services import resiliencia


class _ErrorConStatusCode(Exception):
    """Imita ElevenLabs ApiError / httpx: expone `status_code`."""

    def __init__(self, status_code: int):
        self.status_code = status_code


class _ErrorConStatus(Exception):
    """Imita Replicate ReplicateError: expone `status`."""

    def __init__(self, status: int):
        self.status = status


@pytest.mark.parametrize(
    ("exc", "esperado"),
    [
        (_ErrorConStatusCode(429), True),  # rate limit
        (_ErrorConStatusCode(500), True),  # error de servidor
        (_ErrorConStatusCode(503), True),
        (_ErrorConStatus(502), True),  # variante Replicate (.status)
        (_ErrorConStatusCode(400), False),  # petición inválida: no mejora reintentando
        (_ErrorConStatusCode(401), False),  # no autorizado
        (_ErrorConStatusCode(404), False),
        (httpx.ConnectError("sin red"), True),  # error de transporte
        (httpx.ReadTimeout("lento"), True),  # timeout
        (ValueError("otra cosa"), False),  # error sin código HTTP
    ],
)
def test_es_reintentable(exc, esperado):
    assert resiliencia.es_reintentable(exc) is esperado


@pytest.fixture
def _sin_dormir(monkeypatch):
    """Neutraliza el sleep del backoff para que los tests sean instantáneos."""
    monkeypatch.setattr(resiliencia.time, "sleep", lambda _s: None)


def test_devuelve_a_la_primera_sin_reintentar(_sin_dormir):
    llamadas = {"n": 0}

    def func():
        llamadas["n"] += 1
        return "ok"

    assert resiliencia.reintentar(func, etiqueta="test") == "ok"
    assert llamadas["n"] == 1


def test_reintenta_y_acaba_bien(monkeypatch, _sin_dormir):
    monkeypatch.setattr(resiliencia.config, "HTTP_MAX_INTENTOS", 3)
    llamadas = {"n": 0}

    def func():
        llamadas["n"] += 1
        if llamadas["n"] < 3:
            raise _ErrorConStatusCode(429)  # transitorio las 2 primeras
        return "por fin"

    assert resiliencia.reintentar(func, etiqueta="test") == "por fin"
    assert llamadas["n"] == 3


def test_se_rinde_tras_agotar_intentos(monkeypatch, _sin_dormir):
    monkeypatch.setattr(resiliencia.config, "HTTP_MAX_INTENTOS", 3)
    llamadas = {"n": 0}

    def func():
        llamadas["n"] += 1
        raise _ErrorConStatusCode(429)  # siempre falla

    with pytest.raises(_ErrorConStatusCode):
        resiliencia.reintentar(func, etiqueta="test")
    assert llamadas["n"] == 3  # exactamente HTTP_MAX_INTENTOS intentos, ni uno más


def test_error_no_transitorio_no_se_reintenta(monkeypatch, _sin_dormir):
    monkeypatch.setattr(resiliencia.config, "HTTP_MAX_INTENTOS", 3)
    llamadas = {"n": 0}

    def func():
        llamadas["n"] += 1
        raise _ErrorConStatusCode(400)  # 4xx: no se reintenta

    with pytest.raises(_ErrorConStatusCode):
        resiliencia.reintentar(func, etiqueta="test")
    assert llamadas["n"] == 1  # se propaga a la primera
