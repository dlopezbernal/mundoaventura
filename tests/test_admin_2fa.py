"""Tests del doble factor (2FA TOTP) del acceso de administración (Hito 9.2d).

Se aísla la BBDD en un fichero temporal por test (como en test_familias) para no tocar
el SQLite real, y se usa `pyotp` para generar códigos TOTP válidos. El retardo fijo del
login se pone a 0. Por defecto el 2FA está DESACTIVADO: los tests que lo ejercen lo
activan enrolando + confirmando.
"""

import pyotp
import pytest
from fastapi.testclient import TestClient

from backend import config, db
from backend.main import app
from backend.services import admin_service

_CLIENTE = TestClient(app)


@pytest.fixture(autouse=True)
def _bbdd_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "test_admin.sqlite3")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(admin_service, "_RETARDO_LOGIN", 0)
    admin_service._tokens.clear()
    admin_service._fallos_login.clear()
    db.init_db()
    yield
    monkeypatch.setattr(db, "_engine", None)
    admin_service._tokens.clear()
    admin_service._fallos_login.clear()


def _crear_admin(pwd="contrasena-larga"):
    """Crea la contraseña de admin (setup)."""
    admin_service.configurar(pwd)


# ---------------------------------------------------------------------------
# Contraseña robusta (mínimo 8)
# ---------------------------------------------------------------------------
def test_contrasena_corta_se_rechaza():
    with pytest.raises(ValueError):
        admin_service.configurar("1234")  # < 8 caracteres


def test_login_sin_2fa_funciona_con_solo_contrasena():
    _crear_admin()
    assert admin_service.login("contrasena-larga", "1.1.1.1")  # token no vacío


# ---------------------------------------------------------------------------
# Enrolamiento + confirmación
# ---------------------------------------------------------------------------
def _activar_2fa() -> str:
    """Enrola y confirma el 2FA; devuelve el secreto TOTP."""
    datos = admin_service.iniciar_enrolamiento_2fa()
    secreto = datos["secret"]
    admin_service.confirmar_enrolamiento_2fa(pyotp.TOTP(secreto).now())
    return secreto


def test_enrolar_devuelve_qr_y_no_activa_todavia():
    _crear_admin()
    datos = admin_service.iniciar_enrolamiento_2fa()
    assert datos["secret"] and datos["qr_svg"].startswith("data:image/svg+xml")
    assert "otpauth://" in datos["otpauth_uri"]
    assert admin_service.dos_factor_activo() is False  # aún sin confirmar


def test_confirmar_activa_y_da_codigos_de_recuperacion():
    _crear_admin()
    datos = admin_service.iniciar_enrolamiento_2fa()
    codigos = admin_service.confirmar_enrolamiento_2fa(pyotp.TOTP(datos["secret"]).now())
    assert admin_service.dos_factor_activo() is True
    assert len(codigos) == admin_service._NUM_RECOVERY


def test_confirmar_con_codigo_malo_no_activa():
    _crear_admin()
    admin_service.iniciar_enrolamiento_2fa()
    with pytest.raises(ValueError):
        admin_service.confirmar_enrolamiento_2fa("000000")
    assert admin_service.dos_factor_activo() is False


# ---------------------------------------------------------------------------
# Login con 2FA
# ---------------------------------------------------------------------------
def test_login_con_2fa_requiere_codigo():
    _crear_admin()
    _activar_2fa()
    with pytest.raises(admin_service.Requiere2FAError):
        admin_service.login("contrasena-larga", "1.1.1.1")  # sin código


def test_login_con_2fa_codigo_valido_da_token():
    _crear_admin()
    secreto = _activar_2fa()
    token = admin_service.login("contrasena-larga", "1.1.1.1", pyotp.TOTP(secreto).now())
    assert admin_service.validar_token(token)


def test_login_con_2fa_codigo_invalido_falla():
    _crear_admin()
    _activar_2fa()
    with pytest.raises(ValueError):
        admin_service.login("contrasena-larga", "1.1.1.1", "000000")


def test_contrasena_mala_no_llega_a_pedir_2fa():
    _crear_admin()
    _activar_2fa()
    # Con la contraseña incorrecta se falla ANTES del 2FA (no revela que hay segundo factor).
    with pytest.raises(ValueError):
        admin_service.login("mala-contrasena", "1.1.1.1")


# ---------------------------------------------------------------------------
# Códigos de recuperación (un solo uso)
# ---------------------------------------------------------------------------
def test_codigo_de_recuperacion_entra_y_se_consume():
    _crear_admin()
    datos = admin_service.iniciar_enrolamiento_2fa()
    codigos = admin_service.confirmar_enrolamiento_2fa(pyotp.TOTP(datos["secret"]).now())
    uno = codigos[0]
    assert admin_service.login("contrasena-larga", "1.1.1.1", uno)  # entra con recovery
    # El mismo código ya no vale (un solo uso).
    with pytest.raises(ValueError):
        admin_service.login("contrasena-larga", "1.1.1.1", uno)


# ---------------------------------------------------------------------------
# Desactivación
# ---------------------------------------------------------------------------
def test_desactivar_requiere_contrasena():
    _crear_admin()
    _activar_2fa()
    with pytest.raises(ValueError):
        admin_service.desactivar_2fa("mala")
    assert admin_service.dos_factor_activo() is True
    admin_service.desactivar_2fa("contrasena-larga")
    assert admin_service.dos_factor_activo() is False
    # Tras desactivar, se entra solo con la contraseña.
    assert admin_service.login("contrasena-larga", "1.1.1.1")


# ---------------------------------------------------------------------------
# Integración por HTTP (endpoints + response_model + flag requiere_2fa)
# ---------------------------------------------------------------------------
def test_endpoints_flujo_2fa_completo():
    # Setup crea la contraseña y devuelve un token (auto-login).
    r = _CLIENTE.post("/api/admin/setup", json={"password": "contrasena-larga"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    h = {"X-Admin-Token": token}

    # Enrolar (protegido): devuelve QR + clave, sin activar aún.
    r = _CLIENTE.post("/api/admin/2fa/enrolar", headers=h)
    assert r.status_code == 200, r.text
    secreto = r.json()["secret"]
    assert _CLIENTE.get("/api/admin/status").json()["dos_factor_activo"] is False

    # Confirmar con un código válido → activa y devuelve códigos de recuperación.
    r = _CLIENTE.post(
        "/api/admin/2fa/confirmar", headers=h, json={"codigo": pyotp.TOTP(secreto).now()}
    )
    assert r.status_code == 200 and len(r.json()["recovery_codes"]) == admin_service._NUM_RECOVERY
    assert _CLIENTE.get("/api/admin/status").json()["dos_factor_activo"] is True

    # Login sin código: 200 con requiere_2fa=true y sin token.
    r = _CLIENTE.post("/api/admin/login", json={"password": "contrasena-larga"})
    assert r.status_code == 200 and r.json()["requiere_2fa"] is True and r.json()["token"] == ""

    # Login con código válido: token.
    r = _CLIENTE.post(
        "/api/admin/login",
        json={"password": "contrasena-larga", "codigo": pyotp.TOTP(secreto).now()},
    )
    assert r.status_code == 200 and r.json()["token"]
