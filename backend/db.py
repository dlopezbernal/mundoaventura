"""
backend/db.py — Base de datos de configuración (SQLite + SQLModel)
==================================================================

Un único fichero SQLite (config.CONFIG_DB_PATH) guarda los AJUSTES editables en
caliente y el catálogo (personajes, ubicaciones, documentos). Los SECRETOS (claves
API) NO viven aquí: siguen en el `.env`.

¿Por qué SQLite y no un servidor (MySQL/MariaDB)? El proyecto es "ligero, corre en
cualquier ordenador, sin servicios aparte". SQLite es un solo fichero, sin servidor
ni configuración, ya incluido en Python. Para un equipo con un adulto editando
ajustes de vez en cuando es la elección de manual.

Este módulo solo expone el motor, la creación de tablas y una sesión. La LÓGICA
(leer/escribir ajustes con caché) vive en services/settings_service.py.
"""

from sqlmodel import Session, SQLModel, create_engine

from backend import config

# Motor SQLModel/SQLAlchemy, creado una sola vez (singleton perezoso).
_engine = None


def get_engine():
    """Devuelve el motor SQLite, creándolo (y la carpeta destino) la 1ª vez."""
    global _engine
    if _engine is None:
        # Asegura que la carpeta del fichero existe (p. ej. backend/).
        config.CONFIG_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI atiende peticiones en un pool de hilos;
        # SQLite necesita este flag para poder usar la conexión entre hilos.
        _engine = create_engine(
            f"sqlite:///{config.CONFIG_DB_PATH}",
            connect_args={"check_same_thread": False},
        )
    return _engine


def init_db() -> None:
    """Crea las tablas si no existen (idempotente).

    Importa backend.models para que las tablas queden registradas en el metadata
    de SQLModel antes de crearlas.
    """
    from backend import models  # noqa: F401  (registra los modelos en el metadata)

    SQLModel.metadata.create_all(get_engine())


def get_session() -> Session:
    """Abre una sesión nueva contra la BBDD (usar dentro de un `with`)."""
    return Session(get_engine())
