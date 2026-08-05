"""
services/email_service.py — Envío de correo (SMTP) con fallback a consola (Hito 9.2)
====================================================================================

La verificación del correo de la familia (OTP) necesita ENVIAR un email. Este módulo
encapsula ese envío para que el resto del backend no sepa de SMTP:

  - Si hay un servidor SMTP configurado (`SMTP_HOST`) y NO estamos en DEBUG, se envía
    de verdad con `smtplib` (stdlib, sin dependencias extra). En producción el relé es
    **Brevo** (`smtp-relay.brevo.com`), enviando desde el dominio propio de la app.
  - Si NO hay SMTP configurado, o estamos en DEBUG, el mensaje se **escribe en el log**
    del backend (fallback de consola). Así se puede probar el flujo completo —incluido
    el código— sin montar un servidor de correo (mismo espíritu que el fallback de STT).

Devuelve el CANAL usado (`"email"` | `"consola"`) para que la UI pueda decir "revisa
tu correo" o, en modo desarrollo, "mira la consola del backend".

Dos cosas que no se ven en el código y hacen fallar el envío en un servidor:
  · Muchos proveedores de VPS BLOQUEAN el SMTP saliente (25/465/587) de serie, y el
    síntoma es un `timed out` que no delata su causa.
  · El dominio del remitente tiene que estar VERIFICADO en el relé; si no, el envío se
    rechaza. Con el dominio verificado, Brevo se encarga de la autenticación (SPF/DKIM)
    y el correo llega a la bandeja de entrada sin publicar registros propios.
Ambas están documentadas en `docs/DESPLIEGUE.md`.
"""

import logging
import smtplib
from email.headerregistry import Address
from email.message import EmailMessage

from backend import config
from backend.services import settings_service

logger = logging.getLogger(__name__)


class EmailError(Exception):
    """No se pudo enviar el correo (SMTP configurado pero el envío falló)."""


def smtp_configurado() -> bool:
    """¿Hay un servidor SMTP configurado para enviar correo de verdad?"""
    return bool(str(settings_service.get("SMTP_HOST")).strip())


def _remitente() -> tuple[str, str]:
    """(dirección, nombre visible) del remitente. La dirección cae a SMTP_USER."""
    direccion = str(settings_service.get("SMTP_FROM")).strip()
    if not direccion:
        direccion = str(settings_service.get("SMTP_USER")).strip()
    return direccion, str(settings_service.get("EMAIL_FROM_NAME") or "").strip()


def enviar(destinatario: str, asunto: str, cuerpo: str) -> str:
    """Envía un correo. Devuelve el canal usado: ``"email"`` o ``"consola"``.

    Los ajustes SMTP se editan en caliente desde Admin → Correo (host, puerto, usuario,
    remitente, nombre visible, STARTTLS); la CLAVE es un secreto del `.env` (pestaña
    APIs), que `secrets_service` mantiene en `config.SMTP_PASSWORD`. Cae al log del
    backend (canal ``"consola"``) si no hay SMTP configurado o si DEBUG está activo.
    Lanza EmailError si hay SMTP pero el envío falla.
    """
    depurando = bool(settings_service.get("DEBUG"))
    if depurando or not smtp_configurado():
        # Fallback de consola: el código queda visible en el log para poder probar.
        logger.warning(
            "[EMAIL · consola] Para: %s | Asunto: %s\n%s\n(No se envió por SMTP: %s.)",
            destinatario,
            asunto,
            cuerpo,
            "DEBUG activo" if depurando else "SMTP no configurado",
        )
        return "consola"

    host = str(settings_service.get("SMTP_HOST")).strip()
    usuario = str(settings_service.get("SMTP_USER")).strip()
    direccion, nombre = _remitente()

    msg = EmailMessage()
    msg["Subject"] = asunto
    # Con nombre visible se construye "Nombre <dirección>"; sin él, solo la dirección.
    if nombre and "@" in direccion:
        local, _, dominio = direccion.partition("@")
        msg["From"] = Address(nombre, local, dominio)
    else:
        msg["From"] = direccion
    msg["To"] = destinatario
    msg.set_content(cuerpo)
    try:
        with smtplib.SMTP(host, int(settings_service.get("SMTP_PORT")), timeout=10) as servidor:
            if settings_service.get("SMTP_STARTTLS"):
                servidor.starttls()
            if usuario:
                servidor.login(usuario, config.SMTP_PASSWORD)
            servidor.send_message(msg)
    except Exception as exc:  # noqa: BLE001 — cualquier fallo de SMTP se envuelve
        # El detalle (host, código SMTP, motivo) se queda en el log del backend, que es
        # donde sirve para arreglarlo; al usuario le llega un mensaje genérico.
        logger.warning("Fallo al enviar correo a %s: %s", destinatario, exc)
        raise EmailError("No se pudo enviar el correo de verificación.") from exc
    logger.info("Correo enviado a %s (asunto: %s).", destinatario, asunto)
    return "email"


def enviar_codigo(destinatario: str, nombre_familia: str, codigo: str, minutos: int) -> str:
    """Envía el código de verificación (OTP) de una familia. Devuelve el canal usado."""
    asunto = "Tu código de MundoAventura"
    cuerpo = (
        f"¡Hola, {nombre_familia}!\n\n"
        f"Tu código para activar la cuenta de MundoAventura es:\n\n"
        f"    {codigo}\n\n"
        f"Escríbelo en la aplicación para terminar el registro. "
        f"Caduca en {minutos} minutos.\n\n"
        f"Si no has sido tú, puedes ignorar este mensaje."
    )
    return enviar(destinatario, asunto, cuerpo)
