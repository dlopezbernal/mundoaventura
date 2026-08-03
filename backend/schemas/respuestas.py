"""
schemas/respuestas.py — Modelos de RESPUESTA de la API (contrato de salida)
===========================================================================

Modelos Pydantic de lo que DEVUELVE cada endpoint. Antes las respuestas eran `dict`
sueltos y el frontend replicaba su forma a mano en `src/api/types.ts`; desde aquí, el
backend es la ÚNICA fuente de verdad del contrato y `types.ts` se **autogenera** del
esquema OpenAPI (ver `scripts/gen_types.py`). Añadir `response_model=` a un endpoint:
(1) documenta el contrato en `/docs`, (2) valida/filtra la salida en cada respuesta
—los tests lo comprueban—, y (3) alimenta la generación de tipos del frontend.

Los DTOs "planos" (PersonajeDTO, UbicacionDTO, DocumentoDTO…) se definen una vez y las
respuestas envoltorio (`{ok, personaje}`, etc.) los COMPONEN, así el tipo interno que
consume el frontend no cambia aunque el endpoint lo envuelva.
"""

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# DTOs planos (entidades del dominio)
# ---------------------------------------------------------------------------


class PersonajeDTO(BaseModel):
    """Un personaje del catálogo (lo que devuelve personajes_service)."""

    id: str
    nombre: str
    categoria: str | None = None
    emoji: str | None = None
    prompt_imagen: str
    voz_id: str | None = None
    activo: bool
    prompt_sistema_override: str | None = None


class UbicacionDTO(BaseModel):
    """Una ubicación del catálogo (lo que devuelve ubicaciones_service)."""

    id: str
    nombre: str
    emoji: str | None = None
    prompt_imagen: str
    activo: bool


class VozDTO(BaseModel):
    """Una voz de ElevenLabs (para elegir voz_id)."""

    voz_id: str
    nombre: str
    categoria: str | None = None
    espanol: bool


class DocumentoDTO(BaseModel):
    """Metadatos de un documento del RAG (el fichero vive en disco)."""

    id: int
    personaje_id: str
    nombre_archivo: str
    origen: str
    url_origen: str | None = None
    idioma_original: str | None = None
    traducido: bool
    creado_en: str
    actualizado_en: str
    copiado_de_id: int | None = None


class SettingMeta(BaseModel):
    """Metadatos + valor vigente de UN ajuste editable (settings_service.exportar())."""

    clave: str
    # bool antes que int (bool es subclase de int) y float incluido: hay ajustes
    # decimales (umbrales del Evaluator, temperatura del LLM…). Equivale al
    # `number | string | boolean` del frontend.
    valor: bool | int | float | str
    tipo: str
    categoria: str
    requiere_reindex: bool
    ayuda: str
    min: float | None = None
    max: float | None = None
    paso: float | None = None
    opciones: list[str] | None = None
    multilinea: bool | None = None


class ApiProviderStatus(BaseModel):
    """Estado de un proveedor de API (GET /api/apis), con nombre y enlace de alta."""

    proveedor: str
    variable: str
    nombre: str
    ayuda_url: str
    configurado: bool
    enmascarado: str | None = None


class SecretoEstado(BaseModel):
    """Estado de un secreto tal y como lo expone GET /api/config (forma reducida).

    OJO: es más corto que ApiProviderStatus (sin `nombre`/`ayuda_url`) porque el router
    de config solo necesita pintar "configurado / falta". El estado completo con nombre y
    enlace de alta es el de GET /api/apis (ApiProviderStatus).
    """

    proveedor: str
    variable: str
    configurado: bool
    enmascarado: str | None = None


class ErrorNombre(BaseModel):
    """Un fallo por fichero en la subida múltiple (mejor esfuerzo)."""

    nombre: str
    detalle: str


class ErrorDestino(BaseModel):
    """Un fallo por destino al copiar un documento (mejor esfuerzo)."""

    personaje_id: str
    detalle: str


class ReindexResult(BaseModel):
    """Resultado de un reindexado (por personaje o global)."""

    personaje_id: str | None = None
    personajes: int | None = None
    archivos: int
    chunks: int


class ReindexEstado(BaseModel):
    """Progreso del reindexado GLOBAL en curso (sondeo del frontend)."""

    en_curso: bool
    total: int
    hecho: int
    personaje_actual: str | None = None
    porcentaje: float


class ResumenImport(BaseModel):
    """Cuántas entidades se aplicaron al importar configuración."""

    ajustes: int
    personajes: int
    ubicaciones: int


# ---------------------------------------------------------------------------
# Respuestas envoltorio (componen los DTOs de arriba)
# ---------------------------------------------------------------------------


class OkResponse(BaseModel):
    """Respuesta mínima de una acción sin datos: {ok: true}."""

    ok: bool


class AudioResponse(BaseModel):
    """Audio sintetizado en base64 (mp3), p. ej. al probar una voz."""

    audio_base64: str


# --- Personajes ---
class PersonajesInfo(BaseModel):
    """Catálogo de personajes + tope MAX_PERSONAJES (fijo, no editable desde la UI)."""

    personajes: list[PersonajeDTO]
    limite: int


class PersonajeMutacion(BaseModel):
    """Respuesta de crear/editar un personaje."""

    ok: bool
    personaje: PersonajeDTO


class VocesResponse(BaseModel):
    """Lista de voces de ElevenLabs + aviso si no está disponible."""

    disponible: bool
    voces: list[VozDTO]
    mensaje: str


# --- Ubicaciones ---
class UbicacionesResponse(BaseModel):
    """Catálogo de ubicaciones."""

    ubicaciones: list[UbicacionDTO]


class UbicacionMutacion(BaseModel):
    """Respuesta de crear/editar una ubicación."""

    ok: bool
    ubicacion: UbicacionDTO


# --- Documentos ---
class DocumentosResponse(BaseModel):
    """Lista de documentos de un personaje."""

    documentos: list[DocumentoDTO]


class DocumentoMutacion(BaseModel):
    """Respuesta de ingerir/editar UN documento."""

    ok: bool
    documento: DocumentoDTO


class SubidaDocumentoResponse(BaseModel):
    """Respuesta de subir documentos: uno (`documento`) o varios (`documentos`+`errores`).

    Campos opcionales según el caso; el endpoint usa `response_model_exclude_none=True`
    para no emitir los que no apliquen (así un fichero único responde solo `documento`).
    """

    ok: bool
    documento: DocumentoDTO | None = None
    documentos: list[DocumentoDTO] | None = None
    errores: list[ErrorNombre] | None = None


class DocumentoContenido(BaseModel):
    """Texto actual de un documento (para el visor)."""

    contenido: str
    editable: bool


class CopiaResponse(BaseModel):
    """Resultado de copiar un documento a uno o varios personajes (mejor esfuerzo)."""

    ok: bool
    copiados: list[DocumentoDTO]
    errores: list[ErrorDestino]


class ReindexResponse(BaseModel):
    """Respuesta de un reindexado (por personaje o global)."""

    ok: bool
    resultado: ReindexResult


# --- Config ---
class ConfigResponse(BaseModel):
    """Ajustes vigentes (con metadatos) + estado de los secretos (enmascarados)."""

    ajustes: list[SettingMeta]
    secretos: list[SecretoEstado]


class ConfigSaveResult(BaseModel):
    """Respuesta de guardar ajustes: qué cambios exigen reindexar ChromaDB."""

    ok: bool
    reindex_necesario: list[str]


# --- APIs (secretos) ---
class ApisResponse(BaseModel):
    """Estado de los proveedores de API (enmascarado)."""

    proveedores: list[ApiProviderStatus]


class ApisGuardarResponse(BaseModel):
    """Respuesta de guardar claves de API."""

    ok: bool
    proveedores: list[ApiProviderStatus]


class ApiTestResult(BaseModel):
    """Resultado de probar la conexión de un proveedor."""

    ok: bool
    mensaje: str


class ApiRevealResponse(BaseModel):
    """Clave COMPLETA de un proveedor (icono del ojo)."""

    proveedor: str
    clave: str


# --- Admin ---
class AdminStatus(BaseModel):
    """¿Hay contraseña configurada? ¿La sesión es válida? ¿Está el 2FA activo?"""

    configurado: bool
    sesion_activa: bool
    dos_factor_activo: bool = False


class TokenResponse(BaseModel):
    """Token de sesión de adulto (setup)."""

    ok: bool
    token: str


class AdminLoginResponse(BaseModel):
    """Resultado del login de admin: token, o 'requiere_2fa' si falta el segundo factor."""

    ok: bool
    requiere_2fa: bool = False
    token: str = ""  # vacío mientras falte el 2FA


class Admin2FAEnrol(BaseModel):
    """Datos del enrolamiento 2FA: QR (data URI), URI otpauth y la clave en texto."""

    secret: str
    otpauth_uri: str
    qr_svg: str


class Admin2FARecovery(BaseModel):
    """Códigos de recuperación (en claro, se muestran una sola vez tras activar el 2FA)."""

    ok: bool
    recovery_codes: list[str]


class ConfigExport(BaseModel):
    """Configuración exportada (sin secretos)."""

    version: int
    exportado_en: str
    ajustes: dict[str, bool | int | float | str]
    personajes: list[PersonajeDTO]
    ubicaciones: list[UbicacionDTO]


class ImportResult(BaseModel):
    """Resultado de importar configuración (con copia de seguridad previa)."""

    ok: bool
    resumen: ResumenImport
    backup: str | None = None


# --- Familias (cuentas + sesión, Hito 9.2) ---
class NinoDTO(BaseModel):
    """Un niño del perfil de familia: nombre + sexo (para avatar y género gramatical)."""

    nombre: str
    sexo: str = ""  # "chico" | "chica" | "" (sin especificar)


class FamiliaDTO(BaseModel):
    """Datos públicos de una familia (NUNCA el hash de la contraseña ni del PIN)."""

    id: str
    email: str
    nombre_familia: str
    ninos: list[NinoDTO] = []  # niños (hermanos) del multi-perfil, con nombre y sexo
    tiene_pin: bool = False  # ¿tiene PIN de familia configurado?


class FamiliaSesion(BaseModel):
    """Estado de la sesión de familia (GET /api/familias/me)."""

    autenticada: bool
    familia: FamiliaDTO | None = None


class FamiliaAuthResponse(BaseModel):
    """Respuesta de inicio de sesión o verificación: token de sesión + datos de la familia."""

    ok: bool
    token: str
    familia: FamiliaDTO


class FamiliaSignupResponse(BaseModel):
    """Respuesta del alta de familia.

    Si la verificación de correo está desactivada, viene con sesión iniciada
    (`token` + `familia`). Si está activada, `verificacion_requerida=True` y NO hay
    token: hay que verificar el código (`canal` dice si se envió por email o quedó en
    la consola del backend, en modo desarrollo).
    """

    ok: bool
    verificacion_requerida: bool
    canal: str | None = None  # "email" | "consola" | None
    familia: FamiliaDTO | None = None
    token: str | None = None


class FamiliaReenviarResponse(BaseModel):
    """Respuesta de reenviar el código de verificación."""

    ok: bool
    canal: str  # "email" | "consola"


class FamiliasEstado(BaseModel):
    """¿Hay ya alguna familia registrada? (para adaptar el primer arranque)."""

    hay_familias: bool


# --- Transcripción ---
class TranscribeResponse(BaseModel):
    """Texto transcrito del audio del niño."""

    texto: str


# --- Salud ---
class HealthResponse(BaseModel):
    """Estado del backend. Campos dinámicos (config + proveedores), por eso `extra=allow`.

    Se declaran los que el frontend consulta explícitamente; el resto (describe(),
    estado() de traducción/voz) se preservan como propiedades extra.
    """

    model_config = ConfigDict(extra="allow")

    status: str
    token_configurado: bool | None = None
    deepl_ok: bool | None = None
    elevenlabs_ok: bool | None = None


class RootResponse(BaseModel):
    """Mensaje de bienvenida del endpoint raíz (GET /)."""

    proyecto: str
    fases_activas: list[str]
    documentacion: str
