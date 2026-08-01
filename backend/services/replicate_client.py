"""
services/replicate_client.py — Cliente de Replicate con timeout y reintentos (Hito 2)
=====================================================================================

El SDK de Replicate ofrece un `replicate.run(...)` de módulo que usa un cliente por
defecto SIN timeout explícito y SIN reintentos. Este módulo centraliza un cliente
único (singleton perezoso) con `timeout` configurable, y expone `run(...)` envuelto
en `resiliencia.reintentar` para tolerar los 429/5xx transitorios del free tier.

Tanto generation_service (imagen) como rag_service (LLM) llaman aquí, en vez de a
`replicate.run` directamente, para que timeout + reintentos apliquen por igual.
"""

import logging

import replicate

from backend import config
from backend.services import resiliencia

logger = logging.getLogger(__name__)

# Cliente único con timeout (singleton perezoso). Se recrea con reiniciar() cuando
# se cambia la clave desde la pantalla de APIs.
_client: replicate.Client | None = None


def _get_client() -> replicate.Client:
    global _client
    if _client is None:
        _client = replicate.Client(
            api_token=config.REPLICATE_API_TOKEN,
            timeout=config.REPLICATE_TIMEOUT,
        )
    return _client


def reiniciar() -> None:
    """Olvida el cliente cacheado para que se recree con la clave/timeout nuevos."""
    global _client
    _client = None


def run(modelo: str, *, input: dict, etiqueta: str = "Replicate"):  # noqa: A002
    """Llama a `client.run(modelo, input=...)` con timeout y reintentos (429/5xx)."""
    return resiliencia.reintentar(
        lambda: _get_client().run(modelo, input=input),
        etiqueta=etiqueta,
    )
