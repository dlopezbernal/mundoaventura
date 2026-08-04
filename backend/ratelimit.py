"""
backend/ratelimit.py — Rate limit por IP con degradación amable (Hito 2)
========================================================================

Límite de peticiones por IP (slowapi) para que un bot que descubra la URL del túnel
no pueda machacar las APIs. Los límites son configurables y distintos por endpoint:
generoso para el chat, restrictivo para la generación de imagen (lo caro).

Clave: cuando se supera el límite NO se devuelve un 429 crudo al niño. En el chat
(`/api/ask`) el personaje responde "en personaje" (200 con MENSAJE_LIMITE); en el
resto se devuelve un aviso amable. Un 429 pelado en la cara de un niño de 9 años es
un fallo de producto.

Nota de despliegue: la clave es la IP (`get_remote_address`). Tras un proxy/túnel,
puede que todas las peticiones compartan la IP del proxy (un único cubo); para el
objetivo (frenar el escaneo automático) sigue sirviendo como techo global.
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend import config

logger = logging.getLogger(__name__)

# Limiter compartido: lo usan los decoradores de los routers y lo registra main.py.
limiter = Limiter(key_func=get_remote_address)


def _respuesta_en_personaje() -> dict:
    """AskResponse mínima con el mensaje de 'descanso', para responder en personaje."""
    return {
        "success": True,
        "personaje_id": "",
        "pregunta": "",
        "respuesta": config.MENSAJE_LIMITE,
        "origen": "LIMITE",
        "metodo": "",
        "pregunta_traducida": "",
        "distancia": None,
        "fuentes": [],
        "audio_base64": None,
    }


def manejar_rate_limit(request: Request, exc: Exception) -> JSONResponse:
    """Handler de RateLimitExceeded: responde en personaje (chat) o con aviso amable."""
    logger.warning(
        "Rate limit alcanzado en %s desde %s", request.url.path, get_remote_address(request)
    )
    if request.url.path == "/api/ask":
        # El personaje contesta en personaje (200), no un 429 crudo.
        return JSONResponse(status_code=200, content=_respuesta_en_personaje())
    # Generación / voz: aviso amable con 429 (el frontend lo muestra tal cual).
    return JSONResponse(status_code=429, content={"detail": config.MENSAJE_LIMITE})
