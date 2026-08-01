"""
backend/models.py — Modelos de datos (tablas SQLModel)
=======================================================

Define las tablas de la BBDD de configuración (SQLite, ver db.py):

  - Setting     → ajustes editables en caliente (clave/valor tipado).
  - Personaje   → catálogo de personajes (se consume desde la UI en el Hito 4).
  - Ubicacion   → catálogo de lugares (Hito 6).
  - Documento   → metadatos de los documentos del RAG por personaje (Hito 5).

En el Hito 1 se crean todas las tablas y se hace el "seeding" (volcar los valores
actuales del código a la BBDD), pero la app sigue leyendo el catálogo desde el
código; el cambio a leerlo de la BBDD llega en sus hitos respectivos. Los SECRETOS
(claves API) NO se modelan aquí: viven en el `.env`.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _ahora_utc() -> datetime:
    """Marca de tiempo actual en UTC (aware). Sustituye a la variante naíf deprecada."""
    return datetime.now(UTC)


class Setting(SQLModel, table=True):
    """Un ajuste editable (clave/valor tipado). Ver settings_service.py."""

    __tablename__ = "settings"

    clave: str = Field(primary_key=True)
    valor: str  # siempre texto; el tipo real se guarda aparte
    tipo: str  # "str" | "int" | "float" | "bool"
    actualizado_en: datetime = Field(default_factory=_ahora_utc)


class Personaje(SQLModel, table=True):
    """Catálogo de personajes. `id` es el invariante `personaje_id` del proyecto."""

    __tablename__ = "personajes"

    id: str = Field(primary_key=True)
    nombre: str
    categoria: str | None = None
    emoji: str | None = None
    prompt_imagen: str = ""
    voz_id: str | None = None  # voz de ElevenLabs; None = solo texto
    activo: bool = True
    prompt_sistema_override: str | None = None
    creado_en: datetime = Field(default_factory=_ahora_utc)


class Ubicacion(SQLModel, table=True):
    """Catálogo de ubicaciones (lugares donde aparece el personaje)."""

    __tablename__ = "ubicaciones"

    id: str = Field(primary_key=True)
    nombre: str | None = None
    emoji: str | None = None
    prompt: str = ""
    activo: bool = True
    creado_en: datetime = Field(default_factory=_ahora_utc)


class UsoDiario(SQLModel, table=True):
    """Contador de generaciones de imagen por día natural (tope de coste, Hito 2).

    `fecha` es la clave (formato ISO 'YYYY-MM-DD'); `imagenes` cuenta las escenas
    generadas ese día. Lo usa cuota_service para frenar el gasto en el túnel público.
    """

    __tablename__ = "uso_diario"

    fecha: str = Field(primary_key=True)  # 'YYYY-MM-DD'
    imagenes: int = 0


class Documento(SQLModel, table=True):
    """Metadato de un documento del RAG (el fichero vive en documentos/<id>/)."""

    __tablename__ = "documentos"

    id: int | None = Field(default=None, primary_key=True)
    personaje_id: str = Field(index=True)
    nombre_archivo: str
    origen: str = "subido"  # "subido" | "url"
    url_origen: str | None = None
    idioma_original: str | None = None
    traducido: bool = False
    creado_en: datetime = Field(default_factory=_ahora_utc)
    actualizado_en: datetime = Field(default_factory=_ahora_utc)
    copiado_de_id: int | None = (
        None  # id del documento origen si se creó con "copiar a"; solo informativo
    )
