"""
services/cuota_service.py — Tope diario de generaciones de imagen (Hito 2)
==========================================================================

El túnel público podría vaciar el crédito de Replicate a base de generar imágenes.
Además del rate limit por minuto (slowapi), fijamos un TECHO DURO por día natural,
contado en SQLite (tabla `uso_diario`). Es dinero: preferimos un tope claro.

Flujo: el endpoint de generación llama a `hay_cupo()` ANTES de gastar en Replicate;
si no queda, responde con un aviso amable sin llamar a la API. Tras una generación
correcta llama a `registrar()`. La ventana de carrera (dos peticiones que pasan el
chequeo a la vez) es despreciable con SQLite y el tráfico de la app, y el rate limit
por minuto ya acota las ráfagas.
"""

from datetime import date

from backend import config, db
from backend.models import UsoDiario


def _hoy() -> str:
    return date.today().isoformat()


def _generadas_hoy(sesion) -> int:
    fila = sesion.get(UsoDiario, _hoy())
    return fila.imagenes if fila else 0


def hay_cupo() -> bool:
    """True si aún se pueden generar imágenes hoy (o si el tope está desactivado)."""
    limite = config.MAX_IMAGENES_DIA
    if limite <= 0:
        return True  # tope desactivado
    db.init_db()
    with db.get_session() as sesion:
        return _generadas_hoy(sesion) < limite


def registrar() -> None:
    """Suma 1 a la cuenta de imágenes generadas hoy (tras una generación correcta)."""
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(UsoDiario, _hoy())
        if fila is None:
            fila = UsoDiario(fecha=_hoy(), imagenes=1)
        else:
            fila.imagenes += 1
        sesion.add(fila)
        sesion.commit()


def estado() -> dict:
    """Uso de hoy y tope, para diagnóstico (no expuesto al niño)."""
    db.init_db()
    with db.get_session() as sesion:
        return {
            "fecha": _hoy(),
            "imagenes_hoy": _generadas_hoy(sesion),
            "limite": config.MAX_IMAGENES_DIA,
        }
