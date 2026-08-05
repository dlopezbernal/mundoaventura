"""Tests del envío de correo (`email_service`).

Ninguno envía un correo de verdad: `smtplib.SMTP` se sustituye por un doble, así que
la suite no depende de la red ni de tener credenciales del relé. Lo que se comprueba es
lo que puede romperse en silencio: cuándo se envía y cuándo se cae al log, cómo se
compone la cabecera `From`, que el código OTP viaje en el cuerpo, y que un fallo del
relé no filtre detalles al usuario.

La BBDD de ajustes se aísla en un fichero temporal por test, igual que en
`test_familias.py`: `settings_service` lee de ahí, y no debe tocarse el SQLite real.
"""

import smtplib

import pytest

from backend import config, db
from backend.services import email_service, settings_service


@pytest.fixture(autouse=True)
def _bbdd_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "test_email.sqlite3")
    monkeypatch.setattr(db, "_engine", None)
    settings_service._cache = None
    db.init_db()
    # Sin DEBUG: si estuviera activo, TODO caería al fallback de consola y estos
    # tests no probarían nada.
    settings_service.set_many({"DEBUG": False})
    yield
    monkeypatch.setattr(db, "_engine", None)
    settings_service._cache = None


def _config_smtp(**extra):
    """Deja configurado un relé como el de producción (Brevo)."""
    ajustes = {
        "SMTP_HOST": "smtp-relay.brevo.com",
        "SMTP_PORT": 587,
        "SMTP_USER": "b487d4001@smtp-brevo.com",
        "SMTP_FROM": "no-reply@chatmundoaventura.com",
        "EMAIL_FROM_NAME": "MundoAventura",
        "SMTP_STARTTLS": True,
    }
    ajustes.update(extra)
    settings_service.set_many(ajustes)


class _SMTPFalso:
    """Doble de `smtplib.SMTP`: registra lo que se le pide, sin tocar la red."""

    registro: list = []
    fallo: Exception | None = None

    def __init__(self, host, port, timeout=None):
        _SMTPFalso.registro.append(("conexion", host, port))
        if _SMTPFalso.fallo is not None:
            raise _SMTPFalso.fallo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        _SMTPFalso.registro.append(("starttls",))

    def login(self, usuario, clave):
        _SMTPFalso.registro.append(("login", usuario, clave))

    def send_message(self, msg):
        _SMTPFalso.registro.append(("mensaje", msg["From"], msg["To"], msg.get_content()))


@pytest.fixture
def smtp_falso(monkeypatch):
    _SMTPFalso.registro = []
    _SMTPFalso.fallo = None
    monkeypatch.setattr(email_service.smtplib, "SMTP", _SMTPFalso)
    monkeypatch.setattr(config, "SMTP_PASSWORD", "clave-del-rele")
    return _SMTPFalso


# ---------------------------------------------------------------------------
# Cuándo se envía y cuándo no
# ---------------------------------------------------------------------------
def test_sin_servidor_configurado_cae_a_consola(smtp_falso):
    settings_service.set_many({"SMTP_HOST": ""})
    assert email_service.enviar("a@b.com", "Hola", "cuerpo") == "consola"
    assert smtp_falso.registro == []  # no se abrió ninguna conexión


def test_con_debug_no_se_envia_aunque_haya_servidor(smtp_falso):
    """DEBUG manda: en desarrollo el código va al log, no al correo de nadie."""
    _config_smtp()
    settings_service.set_many({"DEBUG": True})
    assert email_service.enviar("a@b.com", "Hola", "cuerpo") == "consola"
    assert smtp_falso.registro == []


def test_smtp_configurado_lo_reporta(smtp_falso):
    settings_service.set_many({"SMTP_HOST": ""})
    assert email_service.smtp_configurado() is False
    _config_smtp()
    assert email_service.smtp_configurado() is True


# ---------------------------------------------------------------------------
# Envío
# ---------------------------------------------------------------------------
def test_envia_por_el_rele_con_starttls_y_login(smtp_falso):
    _config_smtp()
    assert email_service.enviar("familia@ejemplo.com", "Asunto", "cuerpo") == "email"

    assert ("conexion", "smtp-relay.brevo.com", 587) in smtp_falso.registro
    assert ("starttls",) in smtp_falso.registro
    assert ("login", "b487d4001@smtp-brevo.com", "clave-del-rele") in smtp_falso.registro


def test_el_from_lleva_el_nombre_visible(smtp_falso):
    """La familia debe ver 'MundoAventura', no una dirección pelada."""
    _config_smtp()
    email_service.enviar("familia@ejemplo.com", "Asunto", "cuerpo")
    mensaje = [e for e in smtp_falso.registro if e[0] == "mensaje"][0]
    assert mensaje[1] == "MundoAventura <no-reply@chatmundoaventura.com>"
    assert mensaje[2] == "familia@ejemplo.com"


def test_sin_nombre_visible_va_solo_la_direccion(smtp_falso):
    _config_smtp(EMAIL_FROM_NAME="")
    email_service.enviar("a@b.com", "Asunto", "cuerpo")
    mensaje = [e for e in smtp_falso.registro if e[0] == "mensaje"][0]
    assert mensaje[1] == "no-reply@chatmundoaventura.com"


def test_sin_remitente_explicito_se_usa_el_usuario(smtp_falso):
    _config_smtp(SMTP_FROM="", EMAIL_FROM_NAME="")
    email_service.enviar("a@b.com", "Asunto", "cuerpo")
    mensaje = [e for e in smtp_falso.registro if e[0] == "mensaje"][0]
    assert mensaje[1] == "b487d4001@smtp-brevo.com"


def test_sin_usuario_no_se_hace_login(smtp_falso):
    """Un relay local abierto no pide credenciales; no debe intentarse el login."""
    _config_smtp(SMTP_USER="")
    email_service.enviar("a@b.com", "Asunto", "cuerpo")
    assert not [e for e in smtp_falso.registro if e[0] == "login"]


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------
def test_un_fallo_del_rele_no_filtra_el_detalle(smtp_falso):
    """El puerto bloqueado (el fallo típico en un VPS) llega como mensaje genérico."""
    _config_smtp()
    smtp_falso.fallo = TimeoutError("timed out")
    with pytest.raises(email_service.EmailError) as exc:
        email_service.enviar("a@b.com", "Asunto", "cuerpo")
    assert "timed out" not in str(exc.value)
    assert "correo de verificación" in str(exc.value)


def test_un_rechazo_de_credenciales_tambien_se_envuelve(smtp_falso):
    _config_smtp()
    smtp_falso.fallo = smtplib.SMTPAuthenticationError(535, b"authentication failed")
    with pytest.raises(email_service.EmailError):
        email_service.enviar("a@b.com", "Asunto", "cuerpo")


# ---------------------------------------------------------------------------
# El correo del OTP
# ---------------------------------------------------------------------------
def test_el_codigo_otp_va_en_el_cuerpo(smtp_falso):
    """El OTP tiene que verse en el correo: si no, la familia no puede darse de alta."""
    _config_smtp()
    email_service.enviar_codigo("a@b.com", "Los Pérez", "482913", 15)
    cuerpo = [e for e in smtp_falso.registro if e[0] == "mensaje"][0][3]
    assert "482913" in cuerpo
    assert "Los Pérez" in cuerpo
    assert "15 minutos" in cuerpo
