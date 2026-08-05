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

import html as html_lib
import logging
import re
import smtplib
from email.headerregistry import Address
from email.message import EmailMessage
from pathlib import Path

from backend import config
from backend.services import settings_service

logger = logging.getLogger(__name__)

# Plantilla del correo de verificación (diseño arcade del producto). Se lee UNA vez al
# importar: es un fichero pequeño que no cambia en caliente, y así un fallo de ruta
# aparece al arrancar y no en mitad de un alta de familia.
_PLANTILLA_VERIFICACION = (
    Path(__file__).resolve().parent.parent / "templates" / "verificacion_email.html"
).read_text(encoding="utf-8")


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


def enviar(destinatario: str, asunto: str, cuerpo: str, cuerpo_html: str | None = None) -> str:
    """Envía un correo. Devuelve el canal usado: ``"email"`` o ``"consola"``.

    Con `cuerpo_html` se manda un **multipart/alternative**: el cliente de correo elige
    la versión HTML y el `cuerpo` de texto queda como respaldo para quien no la renderiza
    (lectores de texto, previsualizaciones, filtros antispam — que además penalizan a los
    correos que van SOLO en HTML).

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
    msg.set_content(cuerpo)  # respaldo en texto plano (se conserva siempre)
    if cuerpo_html:
        msg.add_alternative(cuerpo_html, subtype="html")
    # Declara el idioma del mensaje. Sin esto, Gmail adivina por el contenido y con un
    # texto corto lleno de mayúsculas y siglas se equivoca: enseña el aviso "parece que
    # este mensaje está en inglés" y ofrece traducirlo, encima de un correo en español.
    # Va DESPUÉS de componer el cuerpo a propósito: `add_alternative` reestructura el
    # mensaje a multipart y se lleva las cabeceras `Content-*` a la subparte, así que
    # puesto antes acabaría dentro del text/plain en vez de en el mensaje.
    msg["Content-Language"] = "es-ES"
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


def _html_verificacion(nombre_familia: str, codigo: str, minutos: int) -> str | None:
    """Rellena la plantilla del correo de verificación. None si el código no encaja.

    La plantilla tiene SEIS cajas de dígito, una por carácter del código. Si algún día
    cambia la longitud del OTP, devolver None hace que el correo salga en texto plano
    —feo pero correcto— en vez de mandar un HTML con placeholders `{{ d5 }}` a la vista.
    """
    if len(codigo) != 6:
        logger.warning(
            "El código de verificación tiene %s dígitos y la plantilla espera 6: "
            "se envía solo en texto plano.",
            len(codigo),
        )
        return None

    url_app = str(settings_service.get("APP_URL") or "").strip().rstrip("/")
    html = _PLANTILLA_VERIFICACION
    if url_app:
        html = html.replace("{{ url_app }}", html_lib.escape(url_app, quote=True))
        # El logo real solo puede ponerse si sabemos desde dónde servirlo: un correo
        # NO carga ficheros del proyecto, necesita una URL pública. La imagen la sirve
        # Caddy junto a la SPA (frontend-react/public/logo-email.png).
        html = re.sub(
            r"<!-- LOGO:inicio -->.*?<!-- LOGO:fin -->",
            f'<img src="{html_lib.escape(url_app, quote=True)}/logo-email.png" width="46" '
            f'height="46" alt="MundoAventura" style="display:block; border-radius:12px;">',
            html,
            flags=re.DOTALL,
        )
    else:
        # Sin URL configurada no dejamos un botón que no lleva a ninguna parte: se
        # recorta el bloque entero entre sus marcadores. El logo se queda como el
        # emoji de la plantilla, que no depende de ningún servidor.
        html = re.sub(r"<!-- CTA:inicio -->.*?<!-- CTA:fin -->", "", html, flags=re.DOTALL)

    # El nombre de familia lo escribe el adulto: se ESCAPA antes de meterlo en el HTML.
    # Sin esto, un nombre con `<` o comillas rompería la maquetación del correo.
    html = html.replace("{{ nombre_familia }}", html_lib.escape(nombre_familia))
    html = html.replace("{{ minutos }}", str(minutos))
    for i, digito in enumerate(codigo, start=1):
        html = html.replace(f"{{{{ d{i} }}}}", digito)
    return html


def enviar_codigo(destinatario: str, nombre_familia: str, codigo: str, minutos: int) -> str:
    """Envía el código de verificación (OTP) de una familia. Devuelve el canal usado.

    Va en multipart: la versión HTML lleva el diseño del producto (cajas de neón con el
    código) y el texto plano se conserva como respaldo. El fallback de consola (DEBUG o
    sin SMTP) registra SOLO el texto: en el log el HTML sería ruido ilegible.
    """
    asunto = "Tu código de MundoAventura"
    cuerpo = (
        f"¡Hola, {nombre_familia}!\n\n"
        f"Tu código para activar la cuenta de MundoAventura es:\n\n"
        f"    {codigo}\n\n"
        f"Escríbelo en la aplicación para terminar el registro. "
        f"Caduca en {minutos} minutos.\n\n"
        f"Si no has sido tú, puedes ignorar este mensaje."
    )
    return enviar(
        destinatario,
        asunto,
        cuerpo,
        cuerpo_html=_html_verificacion(nombre_familia, codigo, minutos),
    )
