"""
services/ubicaciones_service.py — Catálogo de ubicaciones (BBDD) + CRUD
======================================================================

Gemelo de personajes_service pero para el LUGAR donde aparece el personaje. Desde
el Hito 6 el catálogo de ubicaciones deja de vivir en `ubicaciones.py` y se lee de
la tabla `ubicaciones` (SQLite). Este servicio es la ÚNICA puerta de acceso:

  - Lo consumen el backend (generación de imagen) y el frontend (por API: la
    pantalla del niño y la pestaña de configuración).
  - Con **caché en memoria** e invalidación al escribir.

Una ubicación es más simple que un personaje: id, nombre visible, emoji, prompt de
imagen (en inglés) y `activo`. No tiene voz ni documentos del RAG. Los valores por
defecto se vuelcan a la BBDD en el "seeding" del arranque (ver seed.py).
"""

import re
from typing import Any

from sqlmodel import select

from backend import db
from backend.models import Ubicacion

# Formato admitido para el id (minúsculas, números, guion y guion bajo).
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# ---------------------------------------------------------------------------
# Caché en memoria (id → dict). Se carga de la BBDD la 1ª vez.
# ---------------------------------------------------------------------------
_cache: dict[str, dict[str, Any]] | None = None


def _a_dict(fila: Ubicacion) -> dict[str, Any]:
    return {
        "id": fila.id,
        "nombre": fila.nombre,
        "emoji": fila.emoji,
        "prompt_imagen": fila.prompt,
        "activo": fila.activo,
    }


def _ensure_cache() -> dict[str, dict[str, Any]]:
    global _cache
    if _cache is None:
        db.init_db()
        catalogo: dict[str, dict[str, Any]] = {}
        with db.get_session() as sesion:
            for fila in sesion.exec(select(Ubicacion)).all():
                catalogo[fila.id] = _a_dict(fila)
        _cache = catalogo
    return _cache


def _invalidar() -> None:
    global _cache
    _cache = None


def listar(incluir_inactivos: bool = False) -> list[dict[str, Any]]:
    """Catálogo de ubicaciones (por defecto solo las ACTIVAS), ordenado por id."""
    cache = _ensure_cache()
    filas = [u for u in cache.values() if incluir_inactivos or u["activo"]]
    return sorted(filas, key=lambda u: u["id"])


def obtener(ubicacion_id: str) -> dict[str, Any] | None:
    """Devuelve una ubicación por su id, o None si no existe."""
    return _ensure_cache().get(ubicacion_id)


def existe(ubicacion_id: str) -> bool:
    return ubicacion_id in _ensure_cache()


def _validar_id(ubicacion_id: str) -> None:
    if not ubicacion_id or not _ID_RE.match(ubicacion_id):
        raise ValueError(
            "El id de la ubicación debe empezar por una letra o número y usar solo "
            "minúsculas, números, guion (-) o guion bajo (_). Ej.: 'antiguo_egipto'."
        )


def crear(datos: dict[str, Any]) -> dict[str, Any]:
    """Crea una ubicación NUEVA.

    `datos` admite: id (obligatorio), nombre (obligatorio), prompt_imagen
    (obligatorio), emoji, activo. Lanza ValueError (→ 400) si el id es inválido/
    duplicado o faltan campos.
    """
    ubicacion_id = str(datos.get("id", "")).strip()
    _validar_id(ubicacion_id)
    if existe(ubicacion_id):
        raise ValueError(f"Ya existe una ubicación con el id '{ubicacion_id}'.")

    nombre = str(datos.get("nombre", "")).strip()
    prompt = str(datos.get("prompt_imagen", "")).strip()
    if not nombre:
        raise ValueError("La ubicación necesita un nombre.")
    if not prompt:
        raise ValueError(
            "La ubicación necesita una descripción para generar su imagen "
            "(prompt_imagen), en inglés."
        )

    db.init_db()
    with db.get_session() as sesion:
        sesion.add(
            Ubicacion(
                id=ubicacion_id,
                nombre=nombre,
                emoji=(str(datos["emoji"]).strip() or None) if datos.get("emoji") else None,
                prompt=prompt,
                activo=bool(datos.get("activo", True)),
            )
        )
        sesion.commit()

    _invalidar()
    return obtener(ubicacion_id)  # type: ignore[return-value]


def actualizar(ubicacion_id: str, cambios: dict[str, Any]) -> dict[str, Any]:
    """Actualiza los campos indicados de una ubicación (el id no cambia)."""
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Ubicacion, ubicacion_id)
        if fila is None:
            raise ValueError(f"No existe la ubicación '{ubicacion_id}'.")

        if "nombre" in cambios:
            nombre = str(cambios["nombre"]).strip()
            if not nombre:
                raise ValueError("El nombre no puede quedar vacío.")
            fila.nombre = nombre
        if "prompt_imagen" in cambios:
            prompt = str(cambios["prompt_imagen"]).strip()
            if not prompt:
                raise ValueError("La descripción de imagen (prompt_imagen) no puede quedar vacía.")
            fila.prompt = prompt
        if "emoji" in cambios:
            fila.emoji = (str(cambios["emoji"]).strip() or None) if cambios["emoji"] else None
        if "activo" in cambios:
            fila.activo = bool(cambios["activo"])

        sesion.add(fila)
        sesion.commit()

    _invalidar()
    return obtener(ubicacion_id)  # type: ignore[return-value]


def eliminar(ubicacion_id: str) -> None:
    """Elimina una ubicación del catálogo. Lanza ValueError (→ 400) si no existe."""
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Ubicacion, ubicacion_id)
        if fila is None:
            raise ValueError(f"No existe la ubicación '{ubicacion_id}'.")
        sesion.delete(fila)
        sesion.commit()
    _invalidar()
