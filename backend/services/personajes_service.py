"""
services/personajes_service.py — Catálogo de personajes (BBDD) + CRUD
=====================================================================

Desde el Hito 4, el catálogo de personajes deja de vivir en `personajes.py` y se
lee de la tabla `personajes` (SQLite). Este servicio es la ÚNICA puerta de acceso:

  - Lo consumen el backend (generación de imagen y chat RAG) y el frontend (por
    API: la pantalla del niño y la pestaña de configuración).
  - Con **caché en memoria** e invalidación al escribir, igual que settings_service.
  - Mantiene el invariante `personaje_id`: al CREAR un personaje se generan de golpe
    todas sus piezas (fila en BBDD con nombre/categoría/emoji/prompt/voz + carpeta
    `backend/documentos/<id>/` para sus documentos del RAG).

Los valores por defecto (los personajes de siempre) se vuelcan a la BBDD en el
"seeding" del arranque (ver seed.py); aquí solo se lee y edita esa tabla.
"""

import logging
import re
import shutil
import time
from typing import Any

from sqlmodel import select

from backend import config, db
from backend.models import Personaje

logger = logging.getLogger(__name__)

# Categorías válidas de la carta (agrupan el catálogo en la UI del niño).
CATEGORIAS_VALIDAS = ("prehistorico", "historico", "ficticio")

# Formato admitido para el id (el invariante personaje_id): minúsculas, números,
# guion y guion bajo. Es lo que además sirve como nombre de carpeta de documentos.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# ---------------------------------------------------------------------------
# Caché en memoria (id → dict). Se carga de la BBDD la 1ª vez.
# ---------------------------------------------------------------------------
_cache: dict[str, dict[str, Any]] | None = None


def _a_dict(fila: Personaje) -> dict[str, Any]:
    """Convierte una fila Personaje a un dict serializable (para API y consumidores)."""
    return {
        "id": fila.id,
        "nombre": fila.nombre,
        "categoria": fila.categoria,
        "emoji": fila.emoji,
        "prompt_imagen": fila.prompt_imagen,
        "voz_id": fila.voz_id,
        "activo": fila.activo,
        "prompt_sistema_override": fila.prompt_sistema_override,
        # URL relativa del avatar del carrusel si existe (con token de versión para
        # invalidar la caché del navegador al regenerar); None si aún no se ha generado.
        "avatar_url": (
            f"/api/personajes/{fila.id}/avatar?v={fila.avatar}" if fila.avatar else None
        ),
    }


def _ensure_cache() -> dict[str, dict[str, Any]]:
    """Carga (la 1ª vez) el catálogo de la BBDD a la caché en memoria."""
    global _cache
    if _cache is None:
        db.init_db()
        catalogo: dict[str, dict[str, Any]] = {}
        with db.get_session() as sesion:
            for fila in sesion.exec(select(Personaje)).all():
                catalogo[fila.id] = _a_dict(fila)
        _cache = catalogo
    return _cache


def _invalidar() -> None:
    """Fuerza la recarga del catálogo en la siguiente lectura."""
    global _cache
    _cache = None


def listar(incluir_inactivos: bool = False) -> list[dict[str, Any]]:
    """Devuelve el catálogo (por defecto solo los personajes ACTIVOS).

    El orden es estable (por id) para que los carruseles del frontend no bailen.
    """
    cache = _ensure_cache()
    filas = [p for p in cache.values() if incluir_inactivos or p["activo"]]
    return sorted(filas, key=lambda p: p["id"])


def obtener(personaje_id: str) -> dict[str, Any] | None:
    """Devuelve un personaje por su id, o None si no existe."""
    return _ensure_cache().get(personaje_id)


def existe(personaje_id: str) -> bool:
    """¿Existe ese personaje en el catálogo?"""
    return personaje_id in _ensure_cache()


def _validar_id(personaje_id: str) -> None:
    if not personaje_id or not _ID_RE.match(personaje_id):
        raise ValueError(
            "El id del personaje debe empezar por una letra o número y usar solo "
            "minúsculas, números, guion (-) o guion bajo (_). Ej.: 'marie_curie'."
        )


def _carpeta_documentos(personaje_id: str):
    """Ruta de la carpeta de documentos del RAG para este personaje."""
    return config.DOCUMENTOS_DIR / personaje_id


def crear(datos: dict[str, Any]) -> dict[str, Any]:
    """Crea un personaje NUEVO y todas sus piezas del invariante.

    `datos` admite: id (obligatorio), nombre (obligatorio), prompt_imagen
    (obligatorio), categoria, emoji, voz_id, prompt_sistema_override, activo.

    Además de la fila en BBDD, crea la carpeta `backend/documentos/<id>/` para
    que el adulto pueda subir ahí los documentos del RAG (Hito 5). Lanza
    ValueError (→ 400) si el id es inválido, ya existe, o faltan campos.
    """
    personaje_id = str(datos.get("id", "")).strip()
    _validar_id(personaje_id)
    if existe(personaje_id):
        raise ValueError(f"Ya existe un personaje con el id '{personaje_id}'.")
    if len(_ensure_cache()) >= config.MAX_PERSONAJES:
        raise ValueError(
            f"Se alcanzó el máximo de {config.MAX_PERSONAJES} personajes. "
            "Borra alguno antes de crear uno nuevo."
        )

    nombre = str(datos.get("nombre", "")).strip()
    prompt_imagen = str(datos.get("prompt_imagen", "")).strip()
    if not nombre:
        raise ValueError("El personaje necesita un nombre.")
    if not prompt_imagen:
        raise ValueError(
            "El personaje necesita una descripción para generar su imagen "
            "(prompt_imagen), en inglés y sin datos personales."
        )
    categoria = _validar_categoria(datos.get("categoria"))
    voz_id = (str(datos["voz_id"]).strip() or None) if datos.get("voz_id") else None
    override = datos.get("prompt_sistema_override") or None

    db.init_db()
    with db.get_session() as sesion:
        sesion.add(
            Personaje(
                id=personaje_id,
                nombre=nombre,
                categoria=categoria,
                emoji=(str(datos["emoji"]).strip() or None) if datos.get("emoji") else None,
                prompt_imagen=prompt_imagen,
                voz_id=voz_id,
                activo=bool(datos.get("activo", True)),
                prompt_sistema_override=override,
            )
        )
        sesion.commit()

    # Carpeta de documentos del RAG (5º sitio del invariante). exist_ok por si
    # se recrea un id que tuvo documentos antes.
    _carpeta_documentos(personaje_id).mkdir(parents=True, exist_ok=True)

    _invalidar()
    return obtener(personaje_id)  # type: ignore[return-value]


def actualizar(personaje_id: str, cambios: dict[str, Any]) -> dict[str, Any]:
    """Actualiza campos de un personaje existente y aplica en caliente.

    Solo toca los campos presentes en `cambios` (el id NO se cambia: es la clave
    del invariante). Lanza ValueError (→ 400) si el personaje no existe o un valor
    es inválido.
    """
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Personaje, personaje_id)
        if fila is None:
            raise ValueError(f"No existe el personaje '{personaje_id}'.")

        if "nombre" in cambios:
            nombre = str(cambios["nombre"]).strip()
            if not nombre:
                raise ValueError("El nombre no puede quedar vacío.")
            fila.nombre = nombre
        if "prompt_imagen" in cambios:
            prompt_imagen = str(cambios["prompt_imagen"]).strip()
            if not prompt_imagen:
                raise ValueError("La descripción de imagen (prompt_imagen) no puede quedar vacía.")
            fila.prompt_imagen = prompt_imagen
        if "categoria" in cambios:
            fila.categoria = _validar_categoria(cambios["categoria"])
        if "emoji" in cambios:
            fila.emoji = (str(cambios["emoji"]).strip() or None) if cambios["emoji"] else None
        if "voz_id" in cambios:
            fila.voz_id = (str(cambios["voz_id"]).strip() or None) if cambios["voz_id"] else None
        if "prompt_sistema_override" in cambios:
            fila.prompt_sistema_override = cambios["prompt_sistema_override"] or None
        if "activo" in cambios:
            fila.activo = bool(cambios["activo"])

        sesion.add(fila)
        sesion.commit()

    _invalidar()
    return obtener(personaje_id)  # type: ignore[return-value]


def eliminar(personaje_id: str) -> None:
    """Elimina un personaje del catálogo.

    Borra la fila de la BBDD. La carpeta de documentos solo se borra si está
    VACÍA (nunca destruimos conocimiento que el adulto haya subido: el borrado de
    contenido con copia de seguridad se aborda en el Hito 7). Lanza ValueError
    (→ 400) si el personaje no existe.
    """
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Personaje, personaje_id)
        if fila is None:
            raise ValueError(f"No existe el personaje '{personaje_id}'.")
        sesion.delete(fila)
        sesion.commit()

    # Borrar la carpeta solo si está vacía (sin documentos que perder).
    carpeta = _carpeta_documentos(personaje_id)
    try:
        if carpeta.is_dir() and not any(carpeta.iterdir()):
            shutil.rmtree(carpeta)
    except OSError:
        # Best-effort: si no se puede borrar, no es crítico, pero se registra con la
        # traza para no perder el fallo sin rastro (podría quedar una carpeta vacía).
        logger.warning(
            "No se pudo borrar la carpeta de documentos de '%s'.",
            personaje_id,
            exc_info=True,
        )

    # El avatar SÍ se borra (se regenera desde la ficha; no es conocimiento del adulto).
    _ruta_avatar(personaje_id).unlink(missing_ok=True)

    _invalidar()


# ---------------------------------------------------------------------------
# Avatar del carrusel (Hito 10): PNG transparente en disco, generado bajo demanda.
# ---------------------------------------------------------------------------
def _ruta_avatar(personaje_id: str):
    """Ruta del PNG del avatar de este personaje (exista o no)."""
    return config.AVATARES_DIR / f"{personaje_id}.png"


def ruta_avatar(personaje_id: str):
    """Ruta del PNG del avatar si existe en disco (para servirlo), o None."""
    ruta = _ruta_avatar(personaje_id)
    return ruta if ruta.is_file() else None


def guardar_avatar(personaje_id: str, png_bytes: bytes) -> dict[str, Any]:
    """Guarda el PNG del avatar en disco y marca su versión en la fila.

    El token de versión (epoch) hace que la URL cambie al regenerar, forzando al
    navegador a recargar la imagen. Lanza ValueError (→ 400) si el personaje no existe.
    """
    if not existe(personaje_id):
        raise ValueError(f"No existe el personaje '{personaje_id}'.")
    config.AVATARES_DIR.mkdir(parents=True, exist_ok=True)
    _ruta_avatar(personaje_id).write_bytes(png_bytes)

    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Personaje, personaje_id)
        fila.avatar = str(int(time.time()))
        sesion.add(fila)
        sesion.commit()

    _invalidar()
    return obtener(personaje_id)  # type: ignore[return-value]


def borrar_avatar(personaje_id: str) -> dict[str, Any]:
    """Elimina el avatar (fichero + marca), volviendo al emoji. 400 si no existe."""
    if not existe(personaje_id):
        raise ValueError(f"No existe el personaje '{personaje_id}'.")
    _ruta_avatar(personaje_id).unlink(missing_ok=True)

    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Personaje, personaje_id)
        fila.avatar = None
        sesion.add(fila)
        sesion.commit()

    _invalidar()
    return obtener(personaje_id)  # type: ignore[return-value]


def _validar_categoria(valor: Any) -> str | None:
    """Normaliza/valida la categoría (o None si no se indica)."""
    if not valor:
        return None
    categoria = str(valor).strip().lower()
    if categoria not in CATEGORIAS_VALIDAS:
        raise ValueError(
            f"Categoría '{categoria}' no válida. Usa una de: {', '.join(CATEGORIAS_VALIDAS)}."
        )
    return categoria
