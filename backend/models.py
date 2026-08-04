"""
backend/models.py — Modelos de datos (tablas SQLModel)
=======================================================

Define las tablas de la BBDD de configuración (SQLite, ver db.py):

  - Setting     → ajustes editables en caliente (clave/valor tipado).
  - Personaje   → catálogo de personajes (se consume desde la UI en el Hito 4).
  - Ubicacion   → catálogo de lugares (Hito 6).
  - Documento   → metadatos de los documentos del RAG por personaje (Hito 5).

Todas las tablas se crean al arrancar y se hace el "seeding" (volcar los valores por
defecto del código a la BBDD, idempotente). La app lee los catálogos de personajes y
ubicaciones **desde la BBDD** (`personajes_service`/`ubicaciones_service`); los ficheros
`personajes.py`/`ubicaciones.py` quedaron como fuente de seeding. Los SECRETOS (claves
API) NO se modelan aquí: viven en el `.env`.
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
    # Avatar del carrusel (Hito 10): token de versión (None = sin avatar). El PNG
    # transparente vive en disco en backend/avatares/<id>.png; el token cambia al
    # regenerar para invalidar la caché del navegador (?v=<token> en la URL).
    avatar: str | None = None
    creado_en: datetime = Field(default_factory=_ahora_utc)


class Ubicacion(SQLModel, table=True):
    """Catálogo de ubicaciones (lugares donde aparece el personaje)."""

    __tablename__ = "ubicaciones"

    id: str = Field(primary_key=True)
    nombre: str | None = None
    emoji: str | None = None
    prompt: str = ""
    activo: bool = True
    # Imagen del carrusel (Hito 10): token de versión (None = sin imagen). El PNG
    # transparente vive en backend/avatares/ubicaciones/<id>.png. Igual que en Personaje.
    avatar: str | None = None
    creado_en: datetime = Field(default_factory=_ahora_utc)


class UsoDiario(SQLModel, table=True):
    """Contador de generaciones de imagen por día natural (tope de coste, Hito 2).

    `fecha` es la clave (formato ISO 'YYYY-MM-DD'); `imagenes` cuenta las escenas
    generadas ese día. Lo usa cuota_service para frenar el gasto en el túnel público.
    """

    __tablename__ = "uso_diario"

    fecha: str = Field(primary_key=True)  # 'YYYY-MM-DD'
    imagenes: int = 0


class Auditoria(SQLModel, table=True):
    """Registro de auditoría de uso por familia/niño (informe para el adulto).

    Dos niveles (ver `auditoria_service` / ajuste AUDITORIA_CONTENIDO): METADATOS
    (evento + quién/cuándo + ids de personaje/ubicación, siempre) y CONTENIDO (el
    texto de preguntas/respuestas, opcional). Dato personal de un menor: se purga por
    retención (AUDITORIA_RETENCION_DIAS) y con la supresión RGPD de la cuenta (ver
    familias_service.eliminar). `familia_id` permite borrar solo lo de una familia.
    """

    __tablename__ = "auditoria"

    id: int | None = Field(default=None, primary_key=True)
    creado_en: datetime = Field(default_factory=_ahora_utc, index=True)
    tipo: str = Field(index=True)  # login/logout/signup/perfil/escena/pregunta…
    familia_id: str | None = Field(default=None, index=True)
    familia_nombre: str | None = None  # denormalizado para el informe (legible)
    nino: str | None = None  # nombre del niño activo (metadato: "con quién juega")
    detalle: str | None = None  # metadatos en JSON (ids, origen, longitud…)
    contenido: str | None = None  # texto pregunta/respuesta (solo nivel CONTENIDO)
    ip: str | None = None


class Familia(SQLModel, table=True):
    """Cuenta de una familia (Hito 9.2): la credencial de acceso a la aplicación.

    La familia se da de alta ella misma (self-signup). El **email del adulto** es la
    credencial de login (única, normalizada en minúsculas) y sirve de contacto para el
    consentimiento parental; la **contraseña** se guarda hasheada (PBKDF2, ver
    `seguridad.py`), nunca en claro. El **nombre de familia** personaliza la interfaz.
    Los **nombres de los niños** (multi-perfil) y el **PIN de familia** viven también en
    esta fila (`ninos`, `pin_familia_hash`, ver abajo); no confundir el PIN de familia
    (4 dígitos, protege foto/perfil) con la credencial de **Admin** (contraseña + 2FA).
    """

    __tablename__ = "familias"

    id: str = Field(primary_key=True)
    email: str = Field(index=True, unique=True)  # credencial de login (normalizada)
    password_hash: str  # 'salt$hash' (PBKDF2); nunca la contraseña en claro
    nombre_familia: str
    activo: bool = True
    # Verificación del correo (Hito 9.2). Si EMAIL_VERIFICACION está activo, el alta
    # nace con verificada=False y se activa al teclear el código (OTP) que se envía por
    # email. Con la verificación desactivada (por defecto), nace ya verificada=True.
    # Los campos de código son transitorios (se limpian al verificar o al caducar).
    verificada: bool = True
    codigo_hash: str | None = None  # 'salt$hash' del OTP; None si no hay código vivo
    codigo_expira: datetime | None = None
    codigo_intentos: int = 0  # intentos fallidos del código actual (anti-fuerza-bruta)
    # Multi-perfil (Hito 9.2c). `ninos` guarda la lista de nombres (hermanos) como JSON
    # (p. ej. '["Marco","Lucía"]'). `pin_familia_hash` es el PIN de adulto DE LA FAMILIA
    # (4 dígitos, hasheado): protege el consentimiento de la foto y la edición del perfil,
    # y NO da acceso a Admin. None = aún sin PIN configurado.
    ninos: str = "[]"
    pin_familia_hash: str | None = None
    creado_en: datetime = Field(default_factory=_ahora_utc)


class SesionFamilia(SQLModel, table=True):
    """Sesión PERSISTENTE de una familia (token de vida larga en el dispositivo).

    A diferencia del token de admin (en memoria, se pierde al reiniciar el backend), la
    sesión de familia sobrevive a reinicios para NO volver a pedir login en ese equipo.
    Se guarda solo el **hash** del token (SHA-256), nunca el token en claro, junto con su
    caducidad; el token real vive en el `localStorage` del navegador.
    """

    __tablename__ = "sesiones_familia"

    token_hash: str = Field(primary_key=True)
    familia_id: str = Field(index=True)
    creado_en: datetime = Field(default_factory=_ahora_utc)
    expira_en: datetime


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
