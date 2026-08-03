"""Tests de las cuentas de familia (Hito 9.2): alta, login, sesión persistente.

Se aísla la BBDD en un fichero temporal por test (monkeypatch de config.CONFIG_DB_PATH
+ reinicio del motor de SQLModel), así que cada test arranca con la tabla `familias`
vacía y no ensucia el SQLite real de configuración. El retardo fijo del login se pone
a 0 para que los tests sean instantáneos.
"""

import pytest
from fastapi.testclient import TestClient

from backend import config, db
from backend.main import app
from backend.services import familias_service, seguridad

_CLIENTE = TestClient(app)


@pytest.fixture(autouse=True)
def _bbdd_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "test_familias.sqlite3")
    monkeypatch.setattr(db, "_engine", None)  # fuerza recrear el motor sobre la BBDD temporal
    monkeypatch.setattr(familias_service, "_RETARDO_LOGIN", 0)
    familias_service._fallos_login.clear()
    db.init_db()
    yield
    monkeypatch.setattr(db, "_engine", None)
    familias_service._fallos_login.clear()


# ---------------------------------------------------------------------------
# Hashing (seguridad.py)
# ---------------------------------------------------------------------------
def test_hash_no_guarda_la_contrasena_en_claro():
    guardado = seguridad.hashear("secreta123")
    assert "secreta123" not in guardado
    assert seguridad.verificar("secreta123", guardado)
    assert not seguridad.verificar("otra", guardado)


def test_hash_usa_sal_distinta_cada_vez():
    assert seguridad.hashear("misma") != seguridad.hashear("misma")


# ---------------------------------------------------------------------------
# Alta (signup)
# ---------------------------------------------------------------------------
def test_signup_crea_familia_y_devuelve_token():
    familia, token = familias_service.crear("Padre@Ejemplo.com", "contrasena1", "Los García")
    assert familia["email"] == "padre@ejemplo.com"  # normalizado a minúsculas
    assert familia["nombre_familia"] == "Los García"
    assert "password_hash" not in familia  # nunca se expone el hash
    assert token
    # La sesión recién creada es válida.
    assert familias_service.validar_sesion(token)["id"] == familia["id"]


def test_signup_email_duplicado_falla():
    familias_service.crear("dup@ejemplo.com", "contrasena1", "Uno")
    with pytest.raises(ValueError):
        familias_service.crear("DUP@ejemplo.com", "contrasena2", "Dos")


def test_signup_valida_email_y_password():
    with pytest.raises(ValueError):
        familias_service.crear("no-es-email", "contrasena1", "X")
    with pytest.raises(ValueError):
        familias_service.crear("ok@ejemplo.com", "corta", "X")  # < 8 caracteres
    with pytest.raises(ValueError):
        familias_service.crear("ok@ejemplo.com", "contrasena1", "   ")  # sin nombre


def test_hay_familias():
    assert familias_service.hay_familias() is False
    familias_service.crear("a@ejemplo.com", "contrasena1", "A")
    assert familias_service.hay_familias() is True


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def test_login_correcto():
    familias_service.crear("login@ejemplo.com", "contrasena1", "L")
    familia, token = familias_service.login("LOGIN@ejemplo.com", "contrasena1")
    assert familia["email"] == "login@ejemplo.com"
    assert familias_service.validar_sesion(token) is not None


def test_login_password_incorrecta():
    familias_service.crear("x@ejemplo.com", "contrasena1", "X")
    with pytest.raises(ValueError):
        familias_service.login("x@ejemplo.com", "mala")


def test_login_email_inexistente():
    with pytest.raises(ValueError):
        familias_service.login("nadie@ejemplo.com", "loquesea")


def test_login_bloquea_por_fuerza_bruta():
    familias_service.crear("bf@ejemplo.com", "contrasena1", "BF")
    ip = "9.9.9.9"
    for _ in range(familias_service._MAX_FALLOS):
        with pytest.raises(ValueError):
            familias_service.login("bf@ejemplo.com", "mala", ip)
    with pytest.raises(familias_service.BloqueoLoginError):
        familias_service.login("bf@ejemplo.com", "contrasena1", ip)  # bloqueado aunque acierte


# ---------------------------------------------------------------------------
# Sesión: validar, logout
# ---------------------------------------------------------------------------
def test_validar_sesion_token_invalido():
    assert familias_service.validar_sesion(None) is None
    assert familias_service.validar_sesion("token-que-no-existe") is None


def test_logout_invalida_la_sesion():
    _, token = familias_service.crear("out@ejemplo.com", "contrasena1", "O")
    assert familias_service.validar_sesion(token) is not None
    familias_service.logout(token)
    assert familias_service.validar_sesion(token) is None


def test_sesion_caducada_se_rechaza(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from backend.models import SesionFamilia

    _, token = familias_service.crear("exp@ejemplo.com", "contrasena1", "E")
    # Forzamos la caducidad al pasado directamente en la BBDD.
    with db.get_session() as sesion:
        fila = sesion.get(SesionFamilia, familias_service._hash_token(token))
        fila.expira_en = datetime.now(UTC) - timedelta(seconds=1)
        sesion.add(fila)
        sesion.commit()
    assert familias_service.validar_sesion(token) is None


# ---------------------------------------------------------------------------
# Endpoints (contrato de salida: valida los response_model + cabecera X-Family-Token)
# ---------------------------------------------------------------------------
def test_endpoint_signup_login_me_logout(monkeypatch):
    monkeypatch.setattr(familias_service, "_RETARDO_LOGIN", 0)

    # Sin familias todavía.
    assert _CLIENTE.get("/api/familias/estado").json() == {"hay_familias": False}

    # Alta → token + datos de la familia.
    r = _CLIENTE.post(
        "/api/familias/signup",
        json={"email": "api@ejemplo.com", "password": "contrasena1", "nombre_familia": "API"},
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["ok"] and cuerpo["familia"]["nombre_familia"] == "API"
    token = cuerpo["token"]

    # /me con el token devuelve la familia.
    me = _CLIENTE.get("/api/familias/me", headers={"X-Family-Token": token}).json()
    assert me["autenticada"] is True and me["familia"]["email"] == "api@ejemplo.com"

    # /me sin token → no autenticada.
    assert _CLIENTE.get("/api/familias/me").json()["autenticada"] is False

    # Logout invalida el token.
    _CLIENTE.post("/api/familias/logout", headers={"X-Family-Token": token})
    assert (
        _CLIENTE.get("/api/familias/me", headers={"X-Family-Token": token}).json()["autenticada"]
        is False
    )


def test_endpoint_signup_email_duplicado_da_400():
    _CLIENTE.post(
        "/api/familias/signup",
        json={"email": "dup2@ejemplo.com", "password": "contrasena1", "nombre_familia": "A"},
    )
    r = _CLIENTE.post(
        "/api/familias/signup",
        json={"email": "dup2@ejemplo.com", "password": "otra12345", "nombre_familia": "B"},
    )
    assert r.status_code == 400
