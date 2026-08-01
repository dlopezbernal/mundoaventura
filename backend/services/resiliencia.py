"""
services/resiliencia.py — Reintentos con backoff exponencial + jitter (Hito 2)
==============================================================================

Los free tiers de los proveedores devuelven 429 (demasiadas peticiones) y 5xx
puntuales con frecuencia. Sin reintentos, un pico transitorio tumba la petición
del niño. `reintentar()` envuelve una llamada de red y la repite ante errores
TRANSITORIOS (429, 5xx, timeouts y errores de conexión), con espera creciente
(backoff exponencial) y un poco de aleatoriedad (jitter) para no sincronizar los
reintentos de varios clientes a la vez.

NO se reintentan los errores del cliente (4xx salvo 429): un 400/401/404 no mejora
por reintentar, así que se propaga de inmediato. Cada reintento se registra con
`logger.warning` (el fallo NO se traga: si se agotan los intentos, la excepción
original se relanza para que el llamante la gestione).

DeepL queda FUERA de este helper a propósito: su SDK ya implementa timeout +
backoff con jitter (deepl.http_client), y envolverlo aquí duplicaría los reintentos.
"""

import logging
import random
import time
from collections.abc import Callable

import httpx

from backend import config

logger = logging.getLogger(__name__)


def _codigo_estado(exc: Exception) -> int | None:
    """Extrae el código HTTP de la excepción de cualquiera de los SDKs, o None.

    Cubre `status_code` (ElevenLabs ApiError, httpx), `status` (Replicate
    ReplicateError) y `response.status_code` (httpx.HTTPStatusError).
    """
    for attr in ("status_code", "status"):
        valor = getattr(exc, attr, None)
        if isinstance(valor, int):
            return valor
    respuesta = getattr(exc, "response", None)
    codigo = getattr(respuesta, "status_code", None)
    return codigo if isinstance(codigo, int) else None


def es_reintentable(exc: Exception) -> bool:
    """True si el error es TRANSITORIO: timeout/conexión, o HTTP 429 / 5xx."""
    # Timeouts y errores de transporte de httpx (lo que usan por debajo los 3 SDKs).
    if isinstance(exc, httpx.TransportError):
        return True
    codigo = _codigo_estado(exc)
    return codigo is not None and (codigo == 429 or 500 <= codigo <= 599)


def _espera_backoff(intento: int) -> float:
    """Segundos a esperar ANTES del próximo intento (1-indexado): base·2^(n-1) + jitter."""
    base = config.HTTP_BACKOFF_BASE * (2 ** (intento - 1))
    base = min(base, config.HTTP_BACKOFF_MAX)
    # Jitter: hasta un 25% extra, para desincronizar reintentos concurrentes.
    return base + random.uniform(0, base * 0.25)


def reintentar[T](func: Callable[[], T], *, etiqueta: str = "llamada externa") -> T:
    """Ejecuta `func()` reintentando ante errores transitorios (429/5xx/timeout).

    Hace hasta `config.HTTP_MAX_INTENTOS` intentos en total. Relanza la última
    excepción si se agotan o si el error NO es transitorio. `etiqueta` identifica
    la llamada en los logs de reintento.
    """
    intentos = max(1, config.HTTP_MAX_INTENTOS)
    for intento in range(1, intentos + 1):
        try:
            return func()
        except Exception as exc:
            # Último intento o error no transitorio → propagar (no se traga nada).
            if intento >= intentos or not es_reintentable(exc):
                raise
            espera = _espera_backoff(intento)
            logger.warning(
                "%s falló (%s: %s); reintento %s/%s en %.2fs",
                etiqueta,
                type(exc).__name__,
                exc,
                intento + 1,
                intentos,
                espera,
            )
            time.sleep(espera)
    # Inalcanzable (el bucle siempre retorna o relanza), pero deja el tipo cerrado.
    raise RuntimeError("reintentar: estado inesperado")
