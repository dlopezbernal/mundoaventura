"""
routers/errores.py — Saneado de errores internos (Hito 2)
=========================================================

`HTTPException(500, detail=f"...: {exc}")` mandaba al cliente el mensaje interno del
SDK, que puede incluir URLs, claves parciales o detalles de configuración. Aquí se
corta esa fuga: el detalle COMPLETO se registra en el servidor con un `error_id`
único (uuid4), y al cliente solo le llega un mensaje GENÉRICO con ese identificador,
para que un adulto pueda cruzarlo con el log si hace falta.

Dos usos:
  - `error_500(exc, contexto)`: para los `except Exception` explícitos de los routers.
  - `manejar_excepcion(request, exc)`: handler GLOBAL (red de seguridad) para
    cualquier excepción no controlada en cualquier router.
"""

import logging
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("backend.errores")

_MENSAJE_GENERICO = (
    "¡Vaya! Algo no ha salido bien por dentro. Si necesitas ayuda, "
    "dale este código a un adulto: {id}."
)


def _registrar(exc: Exception, contexto: str) -> str:
    """Registra la excepción COMPLETA (con traza) bajo un error_id nuevo y lo devuelve."""
    error_id = uuid.uuid4().hex[:12]
    # exc_info=exc → traza completa en el log del servidor (NO se traga el error).
    logger.error("error_id=%s · %s", error_id, contexto, exc_info=exc)
    return error_id


def error_500(exc: Exception, contexto: str) -> HTTPException:
    """Devuelve un HTTPException 500 con mensaje genérico + error_id (y loguea el detalle)."""
    error_id = _registrar(exc, contexto)
    return HTTPException(status_code=500, detail=_MENSAJE_GENERICO.format(id=error_id))


def mensaje_generico(exc: Exception, contexto: str) -> str:
    """Como error_500 pero devuelve solo el TEXTO (para streams SSE, donde ya no se
    puede lanzar un HTTPException a mitad de respuesta). Loguea el detalle + error_id."""
    error_id = _registrar(exc, contexto)
    return _MENSAJE_GENERICO.format(id=error_id)


def manejar_excepcion(request: Request, exc: Exception) -> JSONResponse:
    """Handler global de excepciones NO controladas: 500 genérico + error_id."""
    error_id = _registrar(exc, f"{request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": _MENSAJE_GENERICO.format(id=error_id)},
    )
