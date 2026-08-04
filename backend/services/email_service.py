"""
services/email_service.py — Envío de correo (SMTP) con fallback a consola (Hito 9.2)
====================================================================================

La verificación del correo de la familia (OTP) necesita ENVIAR un email. Este módulo
encapsula ese envío para que el resto del backend no sepa de SMTP:

  - Si hay un servidor SMTP configurado (`config.SMTP_HOST`) y NO estamos en DEBUG,
    se envía de verdad con `smtplib` (stdlib, sin dependencias extra).
  - Si NO hay SMTP configurado, o estamos en DEBUG, el mensaje se **escribe en el log**
    del backend (fallback de consola). Así se puede probar el flujo completo —incluido
    el código— sin montar un servidor de correo (mismo espíritu que el fallback de STT).

Devuelve el CANAL usado (`"email"` | `"consola"`) para que la UI pueda decir "revisa
tu correo" o, en modo desarrollo, "mira la consola del backend".
"""

import logging
import smtplib
from email.message import EmailMessage

from backend import config
from backend.services import settings_service

logger = logging.getLogger(__name__)


class EmailError(Exception):
    """No se pudo enviar el correo (SMTP configurado pero el envío falló)."""


def smtp_configurado() -> bool:
    """¿Hay un servidor SMTP configurado para enviar correo de verdad?"""
    return bool(str(settings_service.get("SMTP_HOST")).strip())


def enviar(destinatario: str, asunto: str, cuerpo: str) -> str:
    """Envía un correo. Devuelve el canal usado: ``"email"`` o ``"consola"``.

    Los ajustes SMTP se editan en caliente desde Admin → Correo (host, puerto, usuario,
    remitente, STARTTLS); la CONTRASEÑA es un secreto del `.env` (pestaña APIs), que
    `secrets_service` mantiene en `config.SMTP_PASSWORD`. Cae al log del backend (canal
    ``"consola"``) si no hay SMTP configurado o si DEBUG está activo. Lanza EmailError si
    hay SMTP pero el envío falla.
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
    remitente = str(settings_service.get("SMTP_FROM")).strip() or usuario

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = remitente
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
