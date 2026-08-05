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
        # Con multipart, `get_content()` falla: se guarda el mensaje entero y cada
        # test mira la parte que le interesa (ver los ayudantes de abajo).
        _SMTPFalso.registro.append(("mensaje", msg["From"], msg["To"], msg))


def _parte(msg, subtipo):
    """Devuelve el texto de la parte `text/<subtipo>` del mensaje (o None)."""
    for parte in msg.walk():
        if parte.get_content_type() == f"text/{subtipo}":
            return parte.get_content()
    return None


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
def _mensaje(smtp_falso):
    return [e for e in smtp_falso.registro if e[0] == "mensaje"][0][3]


def test_el_codigo_otp_va_en_el_cuerpo(smtp_falso):
    """El OTP tiene que verse en el correo: si no, la familia no puede darse de alta."""
    _config_smtp()
    email_service.enviar_codigo("a@b.com", "Los Pérez", "482913", 15)
    cuerpo = _parte(_mensaje(smtp_falso), "plain")
    assert "482913" in cuerpo
    assert "Los Pérez" in cuerpo
    assert "15 minutos" in cuerpo


def test_el_correo_va_en_multipart_con_html_y_texto(smtp_falso):
    """El texto plano NO se pierde: es el respaldo de quien no renderiza HTML, y los
    filtros antispam penalizan los correos que van solo en HTML."""
    _config_smtp()
    email_service.enviar_codigo("a@b.com", "Los Pérez", "482913", 15)
    msg = _mensaje(smtp_falso)
    assert msg.get_content_type() == "multipart/alternative"
    assert _parte(msg, "plain") is not None
    assert _parte(msg, "html") is not None


def test_el_html_lleva_cada_digito_en_su_caja(smtp_falso):
    _config_smtp()
    email_service.enviar_codigo("a@b.com", "Los Pérez", "482913", 15)
    html = _parte(_mensaje(smtp_falso), "html")
    assert "{{" not in html  # ningún placeholder sin sustituir
    assert "Los Pérez" in html
    assert "CADUCA EN 15 MINUTOS" in html
    # Los seis dígitos, cada uno dentro de su celda de dígito.
    import re

    celdas = re.findall(r'class="digit"[^>]*>(\d)</td>', html)
    assert celdas == ["4", "8", "2", "9", "1", "3"]


def test_sin_url_de_app_no_se_manda_un_boton_muerto(smtp_falso):
    _config_smtp()
    settings_service.set_many({"APP_URL": ""})
    email_service.enviar_codigo("a@b.com", "Los Pérez", "482913", 15)
    html = _parte(_mensaje(smtp_falso), "html")
    assert "ABRIR MUNDOAVENTURA" not in html
    assert "{{ url_app }}" not in html


def test_con_url_de_app_aparece_el_boton(smtp_falso):
    _config_smtp()
    settings_service.set_many({"APP_URL": "https://chatmundoaventura.com"})
    email_service.enviar_codigo("a@b.com", "Los Pérez", "482913", 15)
    html = _parte(_mensaje(smtp_falso), "html")
    assert 'href="https://chatmundoaventura.com"' in html
    assert "ABRIR MUNDOAVENTURA" in html


def test_el_nombre_de_familia_se_escapa(smtp_falso):
    """Lo escribe el adulto: sin escapar, un `<` le rompería la maquetación al correo."""
    _config_smtp()
    email_service.enviar_codigo("a@b.com", "<script>x</script>", "482913", 15)
    html = _parte(_mensaje(smtp_falso), "html")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_un_codigo_de_otra_longitud_cae_a_texto_plano(smtp_falso):
    """Mejor un correo feo que uno con `{{ d5 }}` a la vista del usuario."""
    _config_smtp()
    email_service.enviar_codigo("a@b.com", "Los Pérez", "1234", 15)
    msg = _mensaje(smtp_falso)
    assert msg.get_content_type() == "text/plain"
    assert "1234" in _parte(msg, "plain")
