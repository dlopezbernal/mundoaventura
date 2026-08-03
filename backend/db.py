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
    """Crea las tablas si no existen (idempotente) y migra columnas nuevas.

    Importa backend.models para que las tablas queden registradas en el metadata
    de SQLModel antes de crearlas.
    """
    from backend import models  # noqa: F401  (registra los modelos en el metadata)

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _migrar_columnas_faltantes(engine)


# Columnas añadidas a tablas YA EXISTENTES después de su creación inicial.
# `create_all` solo crea tablas que faltan; no altera las que ya existen, así que
# un cambio de modelo que añade una columna necesita entrar aquí también, o las
# instalaciones con una BBDD previa se quedarán con el esquema viejo.
_COLUMNAS_NUEVAS: dict[str, list[tuple[str, str]]] = {
    "documentos": [("actualizado_en", "TEXT"), ("copiado_de_id", "INTEGER")],
    # Verificación de correo (H9.2): añadida a `familias` tras su creación inicial.
    "familias": [
        ("verificada", "INTEGER"),
        ("codigo_hash", "TEXT"),
        ("codigo_expira", "TEXT"),
        ("codigo_intentos", "INTEGER"),
        ("ninos", "TEXT"),
        ("pin_familia_hash", "TEXT"),
    ],
}


def _migrar_columnas_faltantes(engine) -> None:
    """Añade a tablas existentes las columnas de `_COLUMNAS_NUEVAS` que falten.

    Idempotente vía `PRAGMA table_info`: no falla al re-ejecutarse ni en
    instalaciones nuevas (donde `create_all` ya trajo la columna de fábrica).
    """
    with engine.connect() as con:
        for tabla, columnas in _COLUMNAS_NUEVAS.items():
            existentes = {fila[1] for fila in con.exec_driver_sql(f"PRAGMA table_info({tabla})")}
            for nombre, tipo_sql in columnas:
                if nombre in existentes:
                    continue
                con.exec_driver_sql(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {tipo_sql}")
                if nombre == "actualizado_en":
                    # Backfill: filas de antes de esta columna toman la fecha de alta.
                    con.exec_driver_sql(
                        f"UPDATE {tabla} SET actualizado_en = creado_en WHERE actualizado_en IS NULL"
                    )
                elif nombre == "verificada":
                    # Backfill: las familias creadas ANTES de la verificación se dan por
                    # verificadas (si no, quedarían bloqueadas al no poder teclear código).
                    con.exec_driver_sql(
                        f"UPDATE {tabla} SET verificada = 1 WHERE verificada IS NULL"
                    )
                elif nombre == "ninos":
                    # Backfill: lista de niños vacía (JSON) para las filas previas.
                    con.exec_driver_sql(f"UPDATE {tabla} SET ninos = '[]' WHERE ninos IS NULL")
                con.commit()


def get_session() -> Session:
    """Abre una sesión nueva contra la BBDD (usar dentro de un `with`)."""
    return Session(get_engine())
