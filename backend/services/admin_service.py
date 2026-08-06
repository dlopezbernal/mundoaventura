"""
services/admin_service.py — Acceso de administrador al área de configuración
============================================================================

La zona de Administración contiene claves de API y operaciones destructivas (borrar
personajes/documentos, importar ajustes), y la app la usan NIÑOS. Por eso va detrás de
una **contraseña de administración** (introducida como PIN en el Hito 7 y robustecida en
el Hito 9.2d a contraseña ≥ 8 + 2FA TOTP opcional):

  1. La primera vez, el adulto CREA la contraseña (setup). No se puede entrar hasta que
     exista una.
  2. Para entrar, introduce la contraseña (login); si el 2FA está activo, además un
     código TOTP → el backend devuelve un TOKEN de sesión temporal que el frontend envía
     en cada petición a los endpoints protegidos.
  3. `requiere_admin` es la dependencia de FastAPI que valida ese token.

La contraseña se guarda **hasheada** (PBKDF2-HMAC-SHA256 con sal), nunca en claro y nunca
se envía al frontend. Los tokens viven en memoria (se pierden al reiniciar → habrá que
volver a entrar), suficiente para una app local de un solo proceso. El 2FA (secreto TOTP
+ códigos de recuperación) vive más abajo, en su propia sección.

Además, `backup_sqlite()` hace una copia de seguridad del fichero SQLite antes de
operaciones destructivas (p. ej. importar configuración), como pide el Hito 7.
"""

import hashlib
import hmac
import json
import logging
import secrets
import shutil
import time
from datetime import UTC, datetime

import pyotp
import segno
from fastapi import Header, HTTPException

from backend import config, db
from backend.models import Setting

logger = logging.getLogger(__name__)

# Claves RESERVADAS en la tabla `settings`. Ninguna está en el `_SPEC` de
# settings_service, así que ni se exportan, ni se importan, ni aparecen en el menú de
# ajustes: son internas de este servicio.
# OJO: el STRING conserva el nombre viejo ("admin_pin_hash") a propósito. Es la clave
# primaria de una fila que ya existe en el SQLite de las instalaciones desplegadas
# (producción incluida); renombrarla dejaría a esos adultos sin contraseña de admin.
# El identificador de Python sí se renombró a la nomenclatura actual (contraseña).
_CLAVE_PASSWORD = "admin_pin_hash"
# 2FA (Hito 9.2d): el secreto TOTP activo, el secreto "pendiente" durante el
# enrolamiento (antes de confirmar), y los códigos de recuperación (hasheados).
_CLAVE_2FA_SECRET = "admin_2fa_secret"
_CLAVE_2FA_PENDIENTE = "admin_2fa_pendiente"
_CLAVE_2FA_RECOVERY = "admin_2fa_recovery"

# Parámetros del hash (PBKDF2). 200k iteraciones = buen equilibrio en 2025.
_ITERACIONES = 200_000
# Longitud mínima de la CONTRASEÑA de administración (Hito 9.2d): se sube de 4 a 8 al
# robustecer el acceso pensando en internet. Solo se comprueba al crear/cambiar, así
# que una credencial más corta ya existente sigue sirviendo para entrar.
_LONGITUD_MIN_PASSWORD = 8
# Nº de códigos de recuperación de un solo uso que se generan al activar el 2FA.
_NUM_RECOVERY = 8
# Ventana de validación TOTP: ±1 intervalo (30 s) para tolerar desfases de reloj.
_TOTP_WINDOW = 1

# Vigencia de un token de sesión (segundos). 12 h: cómodo para un adulto que
# configura la app en una sesión sin tener que reintroducir la contraseña a cada paso.
_TTL_TOKEN = 12 * 3600

# Tokens de sesión válidos → instante de caducidad (epoch). En memoria: un solo
# proceso (uvicorn en dev). Al reiniciar el backend se vacían (hay que reentrar).
_tokens: dict[str, float] = {}

# ---------------------------------------------------------------------------
# Anti-fuerza-bruta del login (Hito 2)
# ---------------------------------------------------------------------------
# Una contraseña débil se rompe por fuerza bruta si no hay freno. Tres
# barreras baratas: (1) un retardo fijo en CADA intento (encarece mucho el ataque,
# imperceptible para el adulto); (2) tras varios fallos por IP, bloqueo temporal con
# espera CRECIENTE; (3) log de los intentos fallidos.
_RETARDO_LOGIN = 0.5  # s de espera fija en cada login (los tests lo ponen a 0)
_MAX_FALLOS = 5  # fallos consecutivos por IP antes de bloquear
_BLOQUEO_BASE = 30  # s del primer bloqueo; se duplica en bloqueos consecutivos
_MAX_BLOQUEO = 3600  # tope del bloqueo (1 h)

# Estado por IP: {"fallos": int, "bloqueos": int, "hasta": epoch de fin de bloqueo}.
_fallos_login: dict[str, dict[str, float]] = {}


class BloqueoLoginError(Exception):
    """Demasiados intentos fallidos de contraseña: bloqueo temporal (el router → HTTP 429)."""

    def __init__(self, segundos: int):
        self.segundos = segundos
        super().__init__(
            f"Demasiados intentos. Espera {segundos} segundos antes de volver a intentarlo."
        )


class Requiere2FAError(Exception):
    """La contraseña es correcta pero falta el código 2FA (el router lo señaliza al frontend)."""


def _comprobar_bloqueo(ip: str) -> None:
    """Lanza BloqueoLoginError si la IP está bloqueada ahora mismo."""
    entrada = _fallos_login.get(ip)
    if entrada and entrada["hasta"] > time.time():
        restante = int(entrada["hasta"] - time.time()) + 1
        raise BloqueoLoginError(restante)


def _registrar_fallo(ip: str) -> None:
    """Suma un fallo a la IP; al llegar a _MAX_FALLOS, la bloquea con espera creciente."""
    entrada = _fallos_login.setdefault(ip, {"fallos": 0, "bloqueos": 0, "hasta": 0.0})
    entrada["fallos"] += 1
    logger.warning(
        "Contraseña de admin incorrecta desde %s (fallo %s).", ip, int(entrada["fallos"])
    )
    if entrada["fallos"] >= _MAX_FALLOS:
        entrada["bloqueos"] += 1
        espera = min(_BLOQUEO_BASE * (2 ** (entrada["bloqueos"] - 1)), _MAX_BLOQUEO)
        entrada["hasta"] = time.time() + espera
        entrada["fallos"] = 0  # reinicia el contador; el siguiente ciclo bloquea más
        logger.warning("Login de admin BLOQUEADO para %s durante %ss.", ip, int(espera))


def _limpiar_fallos(ip: str) -> None:
    """Olvida los fallos de una IP (tras un login correcto)."""
    _fallos_login.pop(ip, None)


# ---------------------------------------------------------------------------
# Almacenamiento de la contraseña (hash) en la tabla settings
# ---------------------------------------------------------------------------
def _leer_clave(clave: str) -> str | None:
    """Lee el valor de una clave reservada de la tabla settings (o None)."""
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Setting, clave)
        return fila.valor if fila else None


def _guardar_clave(clave: str, valor: str) -> None:
    """Crea o actualiza una clave reservada de la tabla settings."""
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Setting, clave)
        if fila is None:
            fila = Setting(clave=clave, valor=valor, tipo="str")
        else:
            fila.valor = valor
            fila.actualizado_en = datetime.now(UTC)
        sesion.add(fila)
        sesion.commit()


def _borrar_clave(clave: str) -> None:
    """Elimina una clave reservada de la tabla settings (si existe)."""
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Setting, clave)
        if fila is not None:
            sesion.delete(fila)
            sesion.commit()


def _leer_hash() -> str | None:
    return _leer_clave(_CLAVE_PASSWORD)


def _guardar_hash(valor: str) -> None:
    _guardar_clave(_CLAVE_PASSWORD, valor)


def _hashear(secreto: str, salt_hex: str) -> str:
    """Deriva el hash de un secreto con PBKDF2. Devuelve 'salt$hash' en hex.

    Se usa tanto para la contraseña de admin como para los códigos de recuperación 2FA.
    """
    dk = hashlib.pbkdf2_hmac(
        "sha256", secreto.encode("utf-8"), bytes.fromhex(salt_hex), _ITERACIONES
    )
    return f"{salt_hex}${dk.hex()}"


def _verificar(secreto: str, guardado: str) -> bool:
    """Comprueba un secreto contra el 'salt$hash' guardado (comparación en tiempo constante)."""
    try:
        salt_hex, _ = guardado.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(_hashear(secreto, salt_hex), guardado)


def _validar_password_nueva(password: str) -> None:
    if not password or len(password.strip()) < _LONGITUD_MIN_PASSWORD:
        raise ValueError(
            "La contraseña de administración debe tener al menos "
            f"{_LONGITUD_MIN_PASSWORD} caracteres."
        )


# ---------------------------------------------------------------------------
# API pública del servicio
# ---------------------------------------------------------------------------
def esta_configurado() -> bool:
    """¿Ya existe una contraseña de administración?"""
    return _leer_hash() is not None


def configurar(password: str) -> str:
    """Crea la contraseña por primera vez y devuelve un token de sesión (auto-login).

    Lanza ValueError (→ 400) si ya hay una contraseña configurada o es demasiado corta.
    """
    if esta_configurado():
        raise ValueError(
            "Ya hay una contraseña configurada. Usa 'cambiar contraseña' para modificarla."
        )
    _validar_password_nueva(password)
    _guardar_hash(_hashear(password.strip(), secrets.token_hex(16)))
    return _crear_token()


def login(password: str, ip: str = "?", codigo: str | None = None) -> str:
    """Valida la contraseña (y el 2FA si está activo) y devuelve un token de sesión.

    Lanza BloqueoLoginError (→ 429) si la IP está bloqueada; ValueError (→ 400) si no
    hay contraseña o es incorrecta, o si el código 2FA no es válido; y Requiere2FAError
    si la contraseña es correcta pero el 2FA está activo y no se ha aportado código
    (el router lo traduce a "pide el código" sin dar todavía la sesión).
    """
    _comprobar_bloqueo(ip)
    time.sleep(_RETARDO_LOGIN)  # coste fijo por intento: encarece el ataque
    guardado = _leer_hash()
    if guardado is None:
        raise ValueError("Aún no hay una contraseña configurada. Créala primero.")
    if not _verificar(password.strip(), guardado):
        _registrar_fallo(ip)
        raise ValueError("Contraseña incorrecta.")
    # Contraseña correcta. Si el 2FA está activo, exigimos el segundo factor.
    if dos_factor_activo():
        if not codigo or not codigo.strip():
            raise Requiere2FAError()
        if not _verificar_2fa(codigo.strip()):
            _registrar_fallo(ip)
            raise ValueError("Código de verificación incorrecto.")
    _limpiar_fallos(ip)  # login correcto: borrón y cuenta nueva
    return _crear_token()


def cambiar(password_actual: str, password_nueva: str) -> None:
    """Cambia la contraseña (requiere la actual). Lanza ValueError (→ 400) si no cuadra."""
    guardado = _leer_hash()
    if guardado is None:
        raise ValueError("Aún no hay una contraseña configurada.")
    if not _verificar(password_actual.strip(), guardado):
        raise ValueError("La contraseña actual no es correcta.")
    _validar_password_nueva(password_nueva)
    _guardar_hash(_hashear(password_nueva.strip(), secrets.token_hex(16)))
    # Al cambiar la contraseña invalidamos todas las sesiones abiertas.
    _tokens.clear()


# ---------------------------------------------------------------------------
# Doble factor (2FA TOTP) — Hito 9.2d
# ---------------------------------------------------------------------------
# El área de Admin gestiona la configuración GLOBAL (claves API, catálogo…) y se
# planea exponer por internet, así que además de la contraseña ofrece un segundo
# factor TOTP (Google Authenticator, Aegis, etc.). Es un TOGGLE: por defecto está
# DESACTIVADO —un clon nuevo y el tribunal entran solo con la contraseña—, y se activa
# con un clic (enrolamiento por QR + confirmar código + códigos de recuperación).
def dos_factor_activo() -> bool:
    """¿Está el 2FA activo? (hay un secreto TOTP confirmado)."""
    return _leer_clave(_CLAVE_2FA_SECRET) is not None


def _verificar_totp(secreto: str, codigo: str) -> bool:
    """Comprueba un código TOTP contra el secreto (con ventana de ±1 intervalo)."""
    return pyotp.TOTP(secreto).verify(codigo, valid_window=_TOTP_WINDOW)


def _verificar_y_consumir_recovery(codigo: str) -> bool:
    """¿`codigo` es un código de recuperación válido? Si lo es, lo CONSUME (un solo uso)."""
    guardado = _leer_clave(_CLAVE_2FA_RECOVERY)
    if not guardado:
        return False
    hashes: list[str] = json.loads(guardado)
    for h in hashes:
        if _verificar(codigo, h):
            hashes.remove(h)  # un solo uso: se retira tras acertar
            _guardar_clave(_CLAVE_2FA_RECOVERY, json.dumps(hashes))
            logger.warning(
                "2FA de admin: se usó un código de recuperación (quedan %s).", len(hashes)
            )
            return True
    return False


def _verificar_2fa(codigo: str) -> bool:
    """Valida el segundo factor: primero como TOTP y, si no, como código de recuperación."""
    secreto = _leer_clave(_CLAVE_2FA_SECRET)
    if secreto and _verificar_totp(secreto, codigo):
        return True
    return _verificar_y_consumir_recovery(codigo)


def iniciar_enrolamiento_2fa() -> dict:
    """Arranca el enrolamiento: genera un secreto PENDIENTE y devuelve QR + URI + clave.

    No activa el 2FA todavía: hace falta confirmar con un código válido
    (`confirmar_enrolamiento_2fa`). Si ya estaba activo, lanza ValueError.
    """
    if dos_factor_activo():
        raise ValueError("El 2FA ya está activado.")
    secreto = pyotp.random_base32()
    _guardar_clave(_CLAVE_2FA_PENDIENTE, secreto)
    uri = pyotp.TOTP(secreto).provisioning_uri(name="administración", issuer_name="MundoAventura")
    # QR como data URI (SVG, generado por segno sin dependencias de imagen): el frontend
    # solo lo pinta en un <img>. Además devolvemos el secreto en claro para entrada manual.
    qr_svg = segno.make(uri).svg_data_uri(scale=5)
    return {"secret": secreto, "otpauth_uri": uri, "qr_svg": qr_svg}


def confirmar_enrolamiento_2fa(codigo: str) -> list[str]:
    """Confirma el enrolamiento con un código del autenticador y activa el 2FA.

    Devuelve los códigos de recuperación (en claro, SOLO esta vez). Lanza ValueError si
    no hay enrolamiento en curso o el código no es válido.
    """
    pendiente = _leer_clave(_CLAVE_2FA_PENDIENTE)
    if not pendiente:
        raise ValueError("No hay un enrolamiento de 2FA en curso. Empieza de nuevo.")
    if not _verificar_totp(pendiente, (codigo or "").strip()):
        raise ValueError("El código no es válido. Revisa la hora del móvil e inténtalo otra vez.")
    # Promovemos el secreto pendiente a activo y generamos los códigos de recuperación.
    _guardar_clave(_CLAVE_2FA_SECRET, pendiente)
    _borrar_clave(_CLAVE_2FA_PENDIENTE)
    codigos = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(_NUM_RECOVERY)]
    _guardar_clave(
        _CLAVE_2FA_RECOVERY,
        json.dumps([_hashear(c, secrets.token_hex(16)) for c in codigos]),
    )
    logger.warning("2FA de admin ACTIVADO (con %s códigos de recuperación).", len(codigos))
    return codigos


def desactivar_2fa(password: str) -> None:
    """Desactiva el 2FA. Exige la CONTRASEÑA actual (re-autenticación). Lanza ValueError si falla."""
    guardado = _leer_hash()
    if guardado is None or not _verificar((password or "").strip(), guardado):
        raise ValueError("La contraseña no es correcta.")
    _borrar_clave(_CLAVE_2FA_SECRET)
    _borrar_clave(_CLAVE_2FA_PENDIENTE)
    _borrar_clave(_CLAVE_2FA_RECOVERY)
    logger.warning("2FA de admin DESACTIVADO.")


# ---------------------------------------------------------------------------
# Tokens de sesión
# ---------------------------------------------------------------------------
def _crear_token() -> str:
    token = secrets.token_urlsafe(32)
    _tokens[token] = time.time() + _TTL_TOKEN
    return token


def validar_token(token: str | None) -> bool:
    """True si el token existe y no ha caducado (limpia los caducados de paso)."""
    if not token:
        return False
    caducidad = _tokens.get(token)
    if caducidad is None:
        return False
    if caducidad < time.time():
        _tokens.pop(token, None)
        return False
    return True


def cerrar_sesion(token: str | None) -> None:
    """Invalida un token (cerrar sesión)."""
    if token:
        _tokens.pop(token, None)


# ---------------------------------------------------------------------------
# Dependencia de FastAPI para proteger endpoints
# ---------------------------------------------------------------------------
def requiere_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Deja pasar solo si la cabecera X-Admin-Token es un token de sesión válido.

    Se aplica a los endpoints sensibles (claves, escrituras del catálogo, docs,
    import/export). Los endpoints que usa el niño (leer catálogos, generar, chatear)
    NO la llevan y siguen siendo públicos.
    """
    if not validar_token(x_admin_token):
        raise HTTPException(
            status_code=401,
            detail="Acceso restringido: introduce la contraseña de administración para entrar.",
        )


# ---------------------------------------------------------------------------
# Copia de seguridad del SQLite (antes de operaciones destructivas)
# ---------------------------------------------------------------------------
def backup_sqlite() -> str | None:
    """Copia el fichero SQLite a `<nombre>.<timestamp>.bak`. Devuelve la ruta o None.

    Se llama antes de importar configuración (que sobrescribe ajustes y catálogo).
    Best-effort: si no existe el fichero todavía, no hay nada que respaldar.
    """
    origen = config.CONFIG_DB_PATH
    if not origen.exists():
        return None
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = origen.with_suffix(origen.suffix + f".{marca}.bak")
    shutil.copy2(origen, destino)
    return str(destino)
