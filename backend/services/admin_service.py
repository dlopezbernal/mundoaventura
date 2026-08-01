"""
services/admin_service.py — Acceso de administrador al área de configuración
============================================================================

El menú de configuración contiene claves de API y operaciones destructivas
(borrar personajes/documentos, importar ajustes), y la app la usan NIÑOS. Por eso
toda la zona de ajustes queda detrás de un **PIN de adulto** (Hito 7):

  1. La primera vez, el adulto CREA un PIN (setup). No se puede acceder a los
     ajustes hasta que exista uno.
  2. Para entrar, introduce el PIN (login) → el backend devuelve un TOKEN de sesión
     temporal que el frontend envía en cada petición a los endpoints protegidos.
  3. `requiere_admin` es la dependencia de FastAPI que valida ese token.

El PIN se guarda **hasheado** (PBKDF2-HMAC-SHA256 con sal), nunca en claro y nunca
se envía al frontend. Los tokens viven en memoria (se pierden al reiniciar → habrá
que volver a entrar), suficiente para una app local de un solo proceso.

Además, `backup_sqlite()` hace una copia de seguridad del fichero SQLite antes de
operaciones destructivas (p. ej. importar configuración), como pide el Hito 7.
"""

import hashlib
import hmac
import logging
import secrets
import shutil
import time
from datetime import UTC, datetime

from fastapi import Header, HTTPException

from backend import config, db
from backend.models import Setting

logger = logging.getLogger(__name__)

# Clave RESERVADA en la tabla `settings` para el hash del PIN. No está en el
# `_SPEC` de settings_service, así que ni se exporta, ni se importa, ni aparece
# en el menú de ajustes: es interna de este servicio.
_CLAVE_PIN = "admin_pin_hash"

# Parámetros del hash (PBKDF2). 200k iteraciones = buen equilibrio en 2025.
_ITERACIONES = 200_000
_LONGITUD_MIN_PIN = 4

# Vigencia de un token de sesión (segundos). 12 h: cómodo para un adulto que
# configura la app en una sesión sin tener que reintroducir el PIN a cada paso.
_TTL_TOKEN = 12 * 3600

# Tokens de sesión válidos → instante de caducidad (epoch). En memoria: un solo
# proceso (uvicorn en dev). Al reiniciar el backend se vacían (hay que reentrar).
_tokens: dict[str, float] = {}

# ---------------------------------------------------------------------------
# Anti-fuerza-bruta del login (Hito 2)
# ---------------------------------------------------------------------------
# Un PIN de 4 dígitos son ~10.000 combinaciones: sin freno, minutos de ataque. Tres
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
    """Demasiados intentos fallidos de PIN: bloqueo temporal (el router → HTTP 429)."""

    def __init__(self, segundos: int):
        self.segundos = segundos
        super().__init__(
            f"Demasiados intentos. Espera {segundos} segundos antes de volver a intentarlo."
        )


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
    logger.warning("PIN de admin incorrecto desde %s (fallo %s).", ip, int(entrada["fallos"]))
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
# Almacenamiento del PIN (hash) en la tabla settings
# ---------------------------------------------------------------------------
def _leer_hash() -> str | None:
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Setting, _CLAVE_PIN)
        return fila.valor if fila else None


def _guardar_hash(valor: str) -> None:
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Setting, _CLAVE_PIN)
        if fila is None:
            fila = Setting(clave=_CLAVE_PIN, valor=valor, tipo="str")
        else:
            fila.valor = valor
            fila.actualizado_en = datetime.now(UTC)
        sesion.add(fila)
        sesion.commit()


def _hashear(pin: str, salt_hex: str) -> str:
    """Deriva el hash del PIN con PBKDF2. Devuelve 'salt$hash' en hex."""
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt_hex), _ITERACIONES)
    return f"{salt_hex}${dk.hex()}"


def _verificar(pin: str, guardado: str) -> bool:
    """Comprueba el PIN contra el 'salt$hash' guardado (comparación en tiempo constante)."""
    try:
        salt_hex, _ = guardado.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(_hashear(pin, salt_hex), guardado)


def _validar_pin_nuevo(pin: str) -> None:
    if not pin or len(pin.strip()) < _LONGITUD_MIN_PIN:
        raise ValueError(f"El PIN debe tener al menos {_LONGITUD_MIN_PIN} caracteres.")


# ---------------------------------------------------------------------------
# API pública del servicio
# ---------------------------------------------------------------------------
def esta_configurado() -> bool:
    """¿Ya existe un PIN de adulto?"""
    return _leer_hash() is not None


def configurar(pin: str) -> str:
    """Crea el PIN por primera vez y devuelve un token de sesión (auto-login).

    Lanza ValueError (→ 400) si ya hay un PIN configurado o el PIN es demasiado corto.
    """
    if esta_configurado():
        raise ValueError("Ya hay un PIN configurado. Usa 'cambiar PIN' para modificarlo.")
    _validar_pin_nuevo(pin)
    _guardar_hash(_hashear(pin.strip(), secrets.token_hex(16)))
    return _crear_token()


def login(pin: str, ip: str = "?") -> str:
    """Valida el PIN y devuelve un token de sesión.

    Lanza BloqueoLoginError (→ 429) si la IP está bloqueada por intentos, o
    ValueError (→ 400) si no hay PIN o es incorrecto. Aplica un retardo fijo y
    cuenta los fallos por IP para frenar la fuerza bruta (ver arriba).
    """
    _comprobar_bloqueo(ip)
    time.sleep(_RETARDO_LOGIN)  # coste fijo por intento: encarece el ataque
    guardado = _leer_hash()
    if guardado is None:
        raise ValueError("Aún no hay un PIN configurado. Créalo primero.")
    if not _verificar(pin.strip(), guardado):
        _registrar_fallo(ip)
        raise ValueError("PIN incorrecto.")
    _limpiar_fallos(ip)  # login correcto: borrón y cuenta nueva
    return _crear_token()


def cambiar(pin_actual: str, pin_nuevo: str) -> None:
    """Cambia el PIN (requiere el actual). Lanza ValueError (→ 400) si no cuadra."""
    guardado = _leer_hash()
    if guardado is None:
        raise ValueError("Aún no hay un PIN configurado.")
    if not _verificar(pin_actual.strip(), guardado):
        raise ValueError("El PIN actual no es correcto.")
    _validar_pin_nuevo(pin_nuevo)
    _guardar_hash(_hashear(pin_nuevo.strip(), secrets.token_hex(16)))
    # Al cambiar el PIN invalidamos todas las sesiones abiertas.
    _tokens.clear()


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
            detail="Acceso restringido: introduce el PIN de adulto para entrar en la configuración.",
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
