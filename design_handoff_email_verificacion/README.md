# Handoff: Correo de verificación de familia (rediseño visual)

## Resumen
El correo con el código de verificación (OTP) que se envía al dar de alta una **cuenta de
familia** en MundoAventura es hoy **texto plano**. Este paquete lo sustituye por una versión
**HTML** con la piel arcade-holo de la marca, manteniendo el texto plano como *fallback*
(multipart/alternative). El código se muestra dígito a dígito en cajas de neón.

Repo destino: `dlopezbernal/mundoaventura` (rama `main`).
Fichero a tocar: **`backend/services/email_service.py`** (funciones `enviar` y `enviar_codigo`).

## Sobre los ficheros de este paquete
- `verificacion_email.html` — **plantilla de correo lista para enviar** (tablas +
  estilos inline, compatible con Gmail / Outlook / Apple Mail). A diferencia de un mockup de
  UI, este HTML **sí está pensado para usarse casi tal cual**: guárdalo en el backend y
  rellena sus placeholders. No lo "recrees" en otra tecnología.
- `logo.svg` — el isotipo de marca (mismo del favicon del producto). Ver nota de assets.

## Fidelidad
**Alta (hifi) y send-ready.** Colores, tipografía y estructura son definitivos y ya
verificados contra las restricciones de clientes de correo (tablas, inline, sin JS, sin
flex/grid, degradado con *fallback* a color sólido para Outlook).

## Qué hay que implementar

### 1. `enviar(...)` — admitir cuerpo HTML opcional
Hoy hace `msg.set_content(cuerpo)` (texto). Añade un parámetro opcional `cuerpo_html` y, si
llega, adjúntalo como alternativa HTML. El fallback de consola (DEBUG / sin SMTP) sigue
registrando SOLO el texto plano — no cambia.

```python
def enviar(destinatario: str, asunto: str, cuerpo: str, cuerpo_html: str | None = None) -> str:
    ...  # toda la lógica de canal/SMTP igual
    msg.set_content(cuerpo)                      # fallback texto plano (se conserva)
    if cuerpo_html:
        msg.add_alternative(cuerpo_html, subtype="html")
    ...
```

### 2. `enviar_codigo(...)` — construir y pasar el HTML
Mantén el `cuerpo` de texto actual intacto. Carga la plantilla, trocea el código en 6
dígitos y sustituye los placeholders.

```python
from pathlib import Path

_PLANTILLA = (Path(__file__).parent.parent / "templates" / "verificacion_email.html").read_text(encoding="utf-8")

def enviar_codigo(destinatario, nombre_familia, codigo, minutos):
    asunto = "Tu código de MundoAventura"
    cuerpo = (  # === texto plano actual, SIN cambios ===
        f"¡Hola, {nombre_familia}!\n\n"
        f"Tu código para activar la cuenta de MundoAventura es:\n\n"
        f"    {codigo}\n\n"
        f"Escríbelo en la aplicación para terminar el registro. "
        f"Caduca en {minutos} minutos.\n\n"
        f"Si no has sido tú, puedes ignorar este mensaje."
    )
    html = (_PLANTILLA
        .replace("{{ nombre_familia }}", nombre_familia)
        .replace("{{ minutos }}", str(minutos))
        .replace("{{ url_app }}", "https://tu-dominio/app"))  # ajusta a tu enlace real
    for i, d in enumerate(codigo, start=1):        # asume código de 6 dígitos
        html = html.replace("{{ d%d }}" % i, d)
    return enviar(destinatario, asunto, cuerpo, cuerpo_html=html)
```

Guarda `verificacion_email.html` en `backend/templates/verificacion_email.html`.

## Placeholders de la plantilla
| Placeholder | Valor |
| --- | --- |
| `{{ nombre_familia }}` | nombre de la familia (saludo) |
| `{{ d1 }}` … `{{ d6 }}` | los 6 dígitos del código, uno por caja |
| `{{ minutos }}` | minutos hasta caducar |
| `{{ url_app }}` | URL del botón "ABRIR MUNDOAVENTURA" (opcional; quítalo si no procede) |

> Si el código pudiera no tener 6 dígitos, ajusta el número de cajas en el HTML y el bucle.

## Assets
- **Logo**: en la plantilla está como emoji 🌀 de marcador (`<div>…🌀</div>` en la cabecera).
  Los correos **no cargan ficheros locales del proyecto**, así que hay que servir el logo
  desde una **URL https pública**. Convierte `logo.svg` a PNG (los clientes de correo no
  renderizan SVG de forma fiable), súbelo a un host/CDN y reemplaza ese `<div>` por:
  `<img src="https://.../logo.png" width="46" height="46" alt="MundoAventura" style="border-radius:12px;">`

## Design tokens (arcade holo, ya aplicados en el HTML)
- Colores: void `#040a1c`, void-2 `#0a1440`, panel `#0b1338`, caja dígito `#071033`,
  cian holo `#3ef2ff`, lima `#8dffcf`, ámbar `#ffcf6b`, texto `#e8f4ff`, muted `#8fa3e0`,
  borde cian `#2bd8e6`, línea `#17335f`.
- Tipografías (con fallback email-safe): Orbitron → `Tahoma/Verdana`; Press Start 2P →
  `'Courier New'`; Chakra Petch → `Arial`. Se enlazan desde Google Fonts (las cargan Apple
  Mail y algunos webmail; el resto usa el fallback, que ya se ve correcto).
- Cajas de dígito: 52×66px, radio 10, borde `#2bd8e6`, dígito 32px Orbitron 900 cian.
- CTA: fondo degradado cian→lima con *fallback* sólido `#3ef2ff`, radio 12, texto `#04121f`.

## Comportamiento / pruebas
- Con `EMAIL_VERIFICACION=true` + SMTP configurado: da de alta una familia y confirma que
  el correo llega con las cajas de dígitos y el botón.
- Con DEBUG o sin SMTP: sigue cayendo al log (texto plano), como hasta ahora.
- Outlook (motor Word): las esquinas redondeadas y el degradado degradan a cuadrado / color
  sólido — es lo esperado y ya contemplado.
- Gmail recorta mensajes > ~100KB; esta plantilla está muy por debajo.

## Ficheros de este paquete
- `verificacion_email.html` — plantilla del correo (fuente de la verdad del diseño).
- `logo.svg` — isotipo para convertir a PNG y alojar.
