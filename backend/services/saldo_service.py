"""
services/saldo_service.py — Cuánto queda en cada proveedor (pestaña APIs)
=========================================================================

Alimenta el botón "Consultar saldo" de 🛡️ Admin → APIs, al lado de "Probar
conexión". Responde a una pregunta operativa concreta: *¿me voy a quedar sin
cuota a mitad de una demostración?*. "Probar conexión" solo dice si la clave
vale; esto dice cuánto queda.

**No todos los proveedores lo exponen, y eso se dice en claro en vez de
inventar un número.** Comprobado contra las APIs reales (2026-08-07):

  · DeepL       → SÍ. `get_usage()` da caracteres usados/límite del periodo.
  · ElevenLabs  → SÍ, pero exige una clave con el permiso `user_read`. Una clave
                  "scoped" sin ese permiso devuelve 401 `missing_permissions`;
                  se traduce a un mensaje que dice qué añadir, porque el error
                  crudo del SDK no lo explica.
  · LLM         → SÍ para endpoints openai-compatibles que devuelven cabeceras
                  `x-ratelimit-*` (Groq las manda). OJO: solo llegan en una
                  llamada de INFERENCIA; `GET /models` no las trae (medido). Por
                  eso aquí se gasta una petición mínima (`max_tokens=1`).
  · Groq (STT)  → SÍ, al mismo precio: hay que transcribir algo. Se manda 1 segundo
                  de silencio generado al vuelo. Informa de PETICIONES (no de
                  segundos de audio, aunque Groq documente ese límite).
  · Replicate   → NO. Su cliente solo tiene accounts/models/predictions; no hay
                  endpoint de crédito. Ni se ofrece el botón: solo el panel web.
  · SMTP/Brevo  → NO con la clave SMTP: los créditos van por la API v3, que es otra
                  credencial distinta. No se ofrece nada; no aplica.

Qué proveedores se pueden consultar es una POLÍTICA que vive aquí (`_CONSULTABLES`)
y que `secrets_service.estado()` publica como `saldo_consultable`: así la pestaña
APIs decide si pinta el botón, un enlace al panel o nada, sin repetir la lista de
proveedores en el frontend.

Las claves se leen de `config` (no de `_PROVEEDORES` de secrets_service) porque
`secrets_service.guardar` actualiza esa copia en memoria: así, consultar el saldo
justo después de pegar una clave nueva usa la nueva sin reiniciar.

No se envuelve en `resiliencia.reintentar`: es una consulta manual de un adulto
mirando la pantalla, no una petición del niño en el camino crítico. Si falla, el
mensaje lo dice y se vuelve a pulsar.
"""

import logging
from datetime import UTC, datetime

from backend import config

logger = logging.getLogger(__name__)

# Panel web de cada proveedor: dónde SÍ se ve el saldo cuando la API no lo da.
# Sin esto, un "no disponible" deja al adulto sin salida.
# SMTP queda fuera a propósito: el saldo de correo no se consulta con esta clave y
# mandar al adulto al panel de Brevo a buscarlo es más ruido que ayuda.
_PANELES: dict[str, str] = {
    "replicate": "https://replicate.com/account/billing",
    "deepl": "https://www.deepl.com/your-account/usage",
    "elevenlabs": "https://elevenlabs.io/app/subscription",
    "groq": "https://console.groq.com/settings/limits",
}


# ---------------------------------------------------------------------------
# Piezas puras (sin red: se prueban directamente en tests/test_saldo_service.py)
# ---------------------------------------------------------------------------
def _mil(n: int) -> str:
    """Formatea un entero con puntos de millar al estilo español (1000000 → 1.000.000)."""
    return f"{n:,}".replace(",", ".")


def _entero(valor: str | None) -> int | None:
    """Convierte una cabecera a entero, o None si falta o no es numérica.

    Las cabeceras son texto libre del proveedor: `x-ratelimit-remaining-tokens`
    puede llegar como "11963", vacía, o ausente. Nunca debe reventar la consulta.
    """
    if valor is None:
        return None
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def _medida(
    etiqueta: str, usado: int | None, limite: int | None, renueva: str | None = None
) -> dict:
    """Una dimensión de consumo (caracteres, tokens, peticiones…) con su porcentaje.

    El porcentaje solo se calcula si hay ambos números y el límite es positivo:
    con `limite=None` (plan sin tope declarado) se deja en None y el frontend
    pinta el número suelto, sin barra que no significaría nada.

    `renueva` es una FRASE YA MONTADA ("se reinicia en 185ms", "se renueva el
    08/09/2026") y no un dato crudo, a propósito: unos proveedores dan una fecha
    y otros un tiempo restante, así que el frontend tendría que adivinar cuál es
    para redactarla. Lo sabe quien lo consulta; se decide aquí.
    """
    porcentaje: float | None = None
    if usado is not None and limite is not None and limite > 0:
        porcentaje = round(usado / limite * 100, 1)
    return {
        "etiqueta": etiqueta,
        "usado": usado,
        "limite": limite,
        "porcentaje": porcentaje,
        "renueva": renueva,
    }


def _medidas_desde_cabeceras(cabeceras: dict[str, str]) -> list[dict]:
    """Traduce las cabeceras `x-ratelimit-*` de un endpoint openai-compatible.

    Devuelve una medida por dimensión presente (tokens y/o peticiones). Se omite
    la dimensión que el proveedor no informe, en vez de pintarla vacía. Las claves
    se comparan en minúsculas porque no todos los clientes normalizan igual.
    """
    normalizadas = {str(k).lower(): v for k, v in cabeceras.items()}
    medidas: list[dict] = []
    # "audio-seconds" es la dimensión de Whisper. Groq NO la mandó al transcribir
    # (medido el 2026-08-07) aunque la documente; se deja declarada porque el bucle
    # omite lo que no llega, así que si algún día aparece se pinta sola.
    for etiqueta, clave in (
        ("Tokens", "tokens"),
        ("Peticiones", "requests"),
        ("Segundos de audio", "audio-seconds"),
    ):
        limite = _entero(normalizadas.get(f"x-ratelimit-limit-{clave}"))
        restante = _entero(normalizadas.get(f"x-ratelimit-remaining-{clave}"))
        if limite is None and restante is None:
            continue
        usado = limite - restante if (limite is not None and restante is not None) else None
        reinicio = normalizadas.get(f"x-ratelimit-reset-{clave}")
        medidas.append(
            _medida(
                etiqueta,
                usado,
                limite,
                renueva=f"se reinicia en {reinicio}" if reinicio else None,
            )
        )
    return medidas


def _resumen(medidas: list[dict]) -> str:
    """Frase legible a partir de las medidas ("Tokens: 37 de 12.000 (0,3 %)")."""
    partes: list[str] = []
    for m in medidas:
        if m["usado"] is not None and m["limite"] is not None:
            texto = f"{m['etiqueta']}: {_mil(m['usado'])} de {_mil(m['limite'])}"
            if m["porcentaje"] is not None:
                texto += f" ({str(m['porcentaje']).replace('.', ',')} %)"
        elif m["limite"] is not None:
            texto = f"{m['etiqueta']}: límite {_mil(m['limite'])}"
        elif m["usado"] is not None:
            texto = f"{m['etiqueta']}: {_mil(m['usado'])} usados"
        else:
            continue
        partes.append(texto)
    return " · ".join(partes)


def _sin_api(proveedor: str, motivo: str) -> dict:
    """Resultado para un proveedor que NO permite consultar el saldo por API."""
    return {
        "proveedor": proveedor,
        "disponible": False,
        "ok": False,
        "mensaje": motivo,
        "medidas": [],
        "panel_url": _PANELES.get(proveedor),
    }


def _error(proveedor: str, mensaje: str) -> dict:
    """Resultado cuando el proveedor SÍ lo expone pero la consulta ha fallado."""
    return {
        "proveedor": proveedor,
        "disponible": True,
        "ok": False,
        "mensaje": mensaje,
        "medidas": [],
        "panel_url": _PANELES.get(proveedor),
    }


def _fecha_unix(marca: int | None) -> str | None:
    """Convierte una marca de tiempo UNIX a 'dd/mm/aaaa', o None si no viene."""
    if not marca:
        return None
    try:
        return datetime.fromtimestamp(int(marca), tz=UTC).strftime("%d/%m/%Y")
    except (OSError, OverflowError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Consulta por proveedor (llamadas de red)
# ---------------------------------------------------------------------------
def _saldo_deepl() -> dict:
    if not config.DEEPL_API_KEY:
        return _error("deepl", "Falta la clave de DeepL.")
    try:
        import deepl

        deepl.http_client.min_connection_timeout = config.DEEPL_TIMEOUT
        uso = deepl.Translator(config.DEEPL_API_KEY).get_usage()
    except Exception as exc:  # noqa: BLE001
        return _error("deepl", f"No se pudo consultar el uso de DeepL: {exc}")

    detalle = uso.character
    if not detalle.valid:
        return _error("deepl", "DeepL no informa del consumo de caracteres para esta cuenta.")
    medidas = [_medida("Caracteres", detalle.count, detalle.limit)]
    aviso = " ⚠️ Límite alcanzado." if uso.any_limit_reached else ""
    return {
        "proveedor": "deepl",
        "disponible": True,
        "ok": True,
        "mensaje": f"{_resumen(medidas)} en el periodo actual.{aviso}",
        "medidas": medidas,
        "panel_url": _PANELES["deepl"],
    }


def _saldo_elevenlabs() -> dict:
    if not config.ELEVENLABS_API_KEY:
        return _error("elevenlabs", "Falta la clave de ElevenLabs.")
    try:
        from elevenlabs.client import ElevenLabs

        cliente = ElevenLabs(api_key=config.ELEVENLABS_API_KEY, timeout=config.ELEVENLABS_TIMEOUT)
        sus = cliente.user.subscription.get()
    except Exception as exc:  # noqa: BLE001
        texto = str(exc)
        # Caso REAL y frecuente: clave "scoped" sin el permiso de lectura de usuario.
        # El error del SDK no dice qué hacer; este mensaje sí.
        if "user_read" in texto or "missing_permissions" in texto:
            return _error(
                "elevenlabs",
                "Tu clave de ElevenLabs no tiene el permiso 'user_read', que es el que "
                "deja consultar el consumo. Añádeselo en ElevenLabs (o usa una clave sin "
                "restricciones) y vuelve a intentarlo. La voz sigue funcionando igual.",
            )
        return _error("elevenlabs", f"No se pudo consultar el consumo de ElevenLabs: {texto}")

    fecha = _fecha_unix(sus.next_character_count_reset_unix)
    medidas = [
        _medida(
            "Caracteres",
            sus.character_count,
            sus.character_limit,
            renueva=f"se renueva el {fecha}" if fecha else None,
        )
    ]
    plan = f" Plan: {sus.tier}." if getattr(sus, "tier", None) else ""
    cuando = f" Se renueva el {fecha}." if fecha else ""
    return {
        "proveedor": "elevenlabs",
        "disponible": True,
        "ok": True,
        "mensaje": f"{_resumen(medidas)}.{plan}{cuando}",
        "medidas": medidas,
        "panel_url": _PANELES["elevenlabs"],
    }


def _saldo_llm() -> dict:
    """Lee las cabeceras `x-ratelimit-*` gastando la petición más pequeña posible.

    Es la única forma: el listado de modelos NO devuelve esas cabeceras (medido
    contra Groq). El coste es de un token de salida, pero **es una llamada de
    pago**: no la dispares en bucles ni en tests.
    """
    from backend.services import settings_service

    proveedor_llm = str(settings_service.get("LLM_PROVIDER")).strip().lower()
    if proveedor_llm != "openai":
        return _sin_api(
            "llm",
            f"El proveedor de LLM activo es '{proveedor_llm}', que no informa de cuota por "
            "API. Esta clave solo se usa con LLM_PROVIDER=openai.",
        )
    if not config.LLM_API_KEY:
        return _error("llm", "Falta la clave del endpoint openai-compatible.")

    base_url = str(settings_service.get("LLM_BASE_URL")).strip()
    modelo = str(settings_service.get("LLM_MODEL")).strip()
    try:
        from openai import OpenAI

        cliente = OpenAI(api_key=config.LLM_API_KEY, base_url=base_url or None)
        respuesta = cliente.chat.completions.with_raw_response.create(
            model=modelo,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        cabeceras = dict(respuesta.headers)
    except Exception as exc:  # noqa: BLE001
        return _error("llm", f"No se pudo consultar la cuota del LLM: {exc}")

    medidas = _medidas_desde_cabeceras(cabeceras)
    panel = "https://console.groq.com/settings/limits" if "groq" in base_url else None
    if not medidas:
        return {
            "proveedor": "llm",
            "disponible": False,
            "ok": False,
            "mensaje": (
                f"La clave funciona, pero {base_url or 'el endpoint'} no devuelve cabeceras "
                "de cuota ('x-ratelimit-*'), así que no hay saldo que mostrar."
            ),
            "medidas": [],
            "panel_url": panel,
        }
    return {
        "proveedor": "llm",
        "disponible": True,
        "ok": True,
        "mensaje": f"{_resumen(medidas)} en la ventana actual de {modelo}.",
        "medidas": medidas,
        "panel_url": panel,
    }


def _wav_silencio() -> bytes:
    """Un WAV de 1 segundo de silencio (16 kHz, mono, 16 bits) — ~32 KB.

    Es el "coste mínimo" de una transcripción: Groq factura el audio por segundos,
    así que un segundo es lo más barato que se puede enviar y seguir recibiendo una
    respuesta 200 con sus cabeceras de cuota. Se genera con el módulo `wave` de la
    stdlib para no arrastrar un fichero binario al repositorio.
    """
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        w.writeframes(b"\x00\x00" * 16_000)
    return buffer.getvalue()


def _saldo_groq() -> dict:
    """Cuota de la clave de Groq (STT) gastando la transcripción más pequeña posible.

    Igual que con el LLM, las cabeceras `x-ratelimit-*` SOLO llegan en una llamada
    de inferencia — el `GET /models` de Groq no las trae (medido). Aquí eso implica
    transcribir de verdad, así que se manda 1 segundo de silencio.

    Medido el 2026-08-07: la respuesta de `audio/transcriptions` informa de
    PETICIONES (2000/día en el plan actual) pero **no** de segundos de audio, aunque
    Groq documente ese límite. Por eso el parseo omite las dimensiones ausentes en
    vez de pintarlas a cero.
    """
    from backend.services import settings_service

    if not config.GROQ_API_KEY:
        return _error("groq", "Falta la clave de Groq.")

    modelo = str(settings_service.get("GROQ_STT_MODEL")).strip()
    try:
        import io

        from openai import OpenAI

        cliente = OpenAI(
            api_key=config.GROQ_API_KEY,
            base_url=config.GROQ_BASE_URL,
            timeout=config.ELEVENLABS_TIMEOUT,
        )
        respuesta = cliente.audio.transcriptions.with_raw_response.create(
            model=modelo,
            file=("silencio.wav", io.BytesIO(_wav_silencio())),
        )
        cabeceras = dict(respuesta.headers)
    except Exception as exc:  # noqa: BLE001
        return _error("groq", f"No se pudo consultar la cuota de Groq: {exc}")

    medidas = _medidas_desde_cabeceras(cabeceras)
    if not medidas:
        return {
            "proveedor": "groq",
            "disponible": False,
            "ok": False,
            "mensaje": (
                "La clave funciona, pero Groq no ha devuelto cabeceras de cuota en esta "
                "transcripción, así que no hay saldo que mostrar."
            ),
            "medidas": [],
            "panel_url": _PANELES["groq"],
        }
    return {
        "proveedor": "groq",
        "disponible": True,
        "ok": True,
        "mensaje": f"{_resumen(medidas)} en la ventana actual de {modelo}.",
        "medidas": medidas,
        "panel_url": _PANELES["groq"],
    }


# Proveedores que SÍ se pueden consultar. Es la política que gobierna la interfaz:
# `secrets_service.estado()` la publica como `saldo_consultable` para que la pestaña
# APIs decida si pinta el botón, un simple enlace al panel, o nada — sin repetir la
# lista de proveedores en el frontend.
_CONSULTABLES: frozenset[str] = frozenset({"deepl", "elevenlabs", "llm", "groq"})


def consultable(proveedor: str) -> bool:
    """¿Tiene sentido ofrecer el botón "Consultar saldo" para este proveedor?"""
    return proveedor in _CONSULTABLES


def panel(proveedor: str) -> str | None:
    """Panel web donde se ve el saldo, o None si no hay uno útil (p. ej. SMTP)."""
    return _PANELES.get(proveedor)


def consultar(proveedor: str) -> dict:
    """Consulta el saldo/consumo de un proveedor. Devuelve siempre un dict, nunca lanza.

    El despacho vive aquí y no en `secrets_service` para no engordar ese módulo;
    `secrets_service.saldo` es la puerta pública que valida el nombre.
    """
    if proveedor == "deepl":
        return _saldo_deepl()
    if proveedor == "elevenlabs":
        return _saldo_elevenlabs()
    if proveedor == "llm":
        return _saldo_llm()
    if proveedor == "groq":
        return _saldo_groq()
    if proveedor == "replicate":
        return _sin_api(
            "replicate",
            "Replicate no publica el crédito por API (su cliente solo expone cuenta, "
            "modelos y predicciones). Míralo en su panel de facturación.",
        )
    if proveedor == "smtp":
        return _sin_api(
            "smtp",
            "Los créditos de correo no se consultan con la clave SMTP: Brevo los expone en "
            "su API v3, que es otra credencial distinta.",
        )
    return _sin_api(proveedor, "Este proveedor no informa de saldo por API.")
