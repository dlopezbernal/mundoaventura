"""
services/familias_service.py — Cuentas de familia + sesión persistente (Hito 9.2)
=================================================================================

Antes de este hito la app no tenía identidad: cualquiera que la abría jugaba. Con el
multi-perfil, cada **familia** es una CUENTA con:

  - **email del adulto** — credencial de login única (normalizada en minúsculas) y
    contacto para el consentimiento parental (app de menores, ver PRIVACIDAD.md).
  - **contraseña** — hasheada con PBKDF2 (`seguridad.py`), nunca en claro.
  - **nombre de familia** — personaliza la interfaz ("Hola, familia …").

La familia se da de alta ella misma (self-signup) y su **sesión es PERSISTENTE**: un
token de vida larga que se guarda en el dispositivo (localStorage) para no re-pedir
login. A diferencia del token de admin (en memoria, se pierde al reiniciar), la sesión
de familia vive en SQLite —solo su HASH— para sobrevivir a reinicios del backend.

La estructura es un primo de `admin_service` (mismo anti-fuerza-bruta por IP), pero la
credencial es email+contraseña y la sesión es duradera.
"""

import hashlib
import json
import logging
import re
import secrets
import time
from datetime import UTC, datetime, timedelta

from fastapi import Header, HTTPException
from sqlmodel import select

from backend import db
from backend.models import Familia, SesionFamilia
from backend.services import email_service, seguridad, settings_service

logger = logging.getLogger(__name__)

# Multi-perfil (Hito 9.2c): límites de la lista de niños y forma del PIN de familia.
_MAX_NINOS = 8
_MAX_LARGO_NOMBRE = 30
_SEXOS_VALIDOS = {"chico", "chica"}  # además de '' (sin especificar)
_RE_PIN_FAMILIA = re.compile(r"^\d{4}$")  # exactamente 4 dígitos

# Vida de una sesión de familia (días). Larga a propósito: el sentido es no volver a
# pedir login en el equipo de casa. Se renueva al iniciar sesión.
_SESION_DIAS = 90

# Verificación del correo (OTP, Hito 9.2): vida y tope de intentos del código.
_CODIGO_TTL_MIN = 15
_CODIGO_MAX_INTENTOS = 5

_LONGITUD_MIN_PASSWORD = 8
# Regex de email deliberadamente laxa (algo@algo.algo): solo evita erratas obvias,
# no valida que el buzón exista. No usamos pydantic EmailStr para no arrastrar la
# dependencia `email-validator`.
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ---------------------------------------------------------------------------
# Anti-fuerza-bruta del login (mismo patrón que admin_service, por IP)
# ---------------------------------------------------------------------------
_RETARDO_LOGIN = 0.5  # s de espera fija en cada login (los tests lo ponen a 0)
_MAX_FALLOS = 5
_BLOQUEO_BASE = 30
_MAX_BLOQUEO = 3600
_fallos_login: dict[str, dict[str, float]] = {}


class BloqueoLoginError(Exception):
    """Demasiados intentos fallidos de login: bloqueo temporal (el router → HTTP 429)."""

    def __init__(self, segundos: int):
        self.segundos = segundos
        super().__init__(
            f"Demasiados intentos. Espera {segundos} segundos antes de volver a intentarlo."
        )


def _comprobar_bloqueo(ip: str) -> None:
    entrada = _fallos_login.get(ip)
    if entrada and entrada["hasta"] > time.time():
        raise BloqueoLoginError(int(entrada["hasta"] - time.time()) + 1)


def _registrar_fallo(ip: str) -> None:
    entrada = _fallos_login.setdefault(ip, {"fallos": 0, "bloqueos": 0, "hasta": 0.0})
    entrada["fallos"] += 1
    logger.warning("Login de familia incorrecto desde %s (fallo %s).", ip, int(entrada["fallos"]))
    if entrada["fallos"] >= _MAX_FALLOS:
        entrada["bloqueos"] += 1
        espera = min(_BLOQUEO_BASE * (2 ** (entrada["bloqueos"] - 1)), _MAX_BLOQUEO)
        entrada["hasta"] = time.time() + espera
        entrada["fallos"] = 0
        logger.warning("Login de familia BLOQUEADO para %s durante %ss.", ip, int(espera))


def _limpiar_fallos(ip: str) -> None:
    _fallos_login.pop(ip, None)


# ---------------------------------------------------------------------------
# Validación y normalización de la entrada
# ---------------------------------------------------------------------------
def _normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


def _validar_signup(email: str, password: str, nombre_familia: str) -> None:
    if not _RE_EMAIL.match(email):
        raise ValueError("Escribe un correo electrónico válido (por ejemplo, familia@ejemplo.com).")
    if len(password or "") < _LONGITUD_MIN_PASSWORD:
        raise ValueError(f"La contraseña debe tener al menos {_LONGITUD_MIN_PASSWORD} caracteres.")
    if not (nombre_familia or "").strip():
        raise ValueError("Escribe un nombre de familia.")


def _sanear_nombre_nino(nombre: str) -> str:
    """Normaliza un nombre de niño: recorta, colapsa espacios y limita la longitud.

    Solo se usa como texto de presentación ("Hola, …") y, en 2c-2, para personalizar
    el prompt del chat; aquí se deja legible y acotado (el saneado anti-inyección para
    el prompt vive en el servicio del chat)."""
    limpio = " ".join((nombre or "").split())
    return limpio[:_MAX_LARGO_NOMBRE]


def _sanear_nino(entry: object) -> dict | None:
    """Normaliza un niño a ``{"nombre", "sexo"}`` seguro, o None si el nombre queda vacío.

    Acepta tanto el formato NUEVO (dict con nombre+sexo) como el ANTIGUO (una cadena
    con solo el nombre, de las familias creadas antes de añadir el sexo): así no hace
    falta migrar la BBDD, la lectura normaliza al vuelo. `sexo` se limita a los valores
    conocidos ('chico'/'chica'); cualquier otra cosa queda como '' (sin especificar).
    """
    if isinstance(entry, str):
        nombre, sexo = entry, ""
    elif isinstance(entry, dict):
        nombre = str(entry.get("nombre", ""))
        sexo = str(entry.get("sexo", ""))
    else:
        return None
    nombre = _sanear_nombre_nino(nombre)
    if not nombre:
        return None
    return {"nombre": nombre, "sexo": sexo if sexo in _SEXOS_VALIDOS else ""}


def _ninos_lista(fam: Familia) -> list[dict]:
    """Decodifica la lista de niños (JSON) de la fila como dicts nombre+sexo; [] si falla."""
    try:
        datos = json.loads(fam.ninos or "[]")
    except (ValueError, TypeError):
        return []
    if not isinstance(datos, list):
        return []
    return [nino for e in datos if (nino := _sanear_nino(e)) is not None]


def _dto(fam: Familia) -> dict:
    """Vista pública de una familia (SIN el hash de la contraseña ni del PIN)."""
    return {
        "id": fam.id,
        "email": fam.email,
        "nombre_familia": fam.nombre_familia,
        "ninos": _ninos_lista(fam),
        "tiene_pin": bool(fam.pin_familia_hash),
    }


# ---------------------------------------------------------------------------
# Verificación del correo (OTP)
# ---------------------------------------------------------------------------
def _nuevo_codigo() -> str:
    """Código de verificación de 6 dígitos (OTP)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _asignar_codigo(fam: Familia) -> str:
    """Genera un código nuevo, lo guarda HASHEADO en la fila y devuelve el código en claro."""
    codigo = _nuevo_codigo()
    fam.codigo_hash = seguridad.hashear(codigo)
    fam.codigo_expira = datetime.now(UTC) + timedelta(minutes=_CODIGO_TTL_MIN)
    fam.codigo_intentos = 0
    return codigo


# ---------------------------------------------------------------------------
# Alta (self-signup)
# ---------------------------------------------------------------------------
def crear(email: str, password: str, nombre_familia: str) -> dict:
    """Da de alta una familia (self-signup).

    Devuelve un dict con el resultado. Si la verificación de correo está DESACTIVADA
    (por defecto), el alta es inmediata y viene con sesión iniciada::

        {"verificacion_requerida": False, "familia": {...}, "token": "…", "canal": None}

    Si está ACTIVADA (`config.EMAIL_VERIFICACION`), la cuenta queda pendiente y se envía
    un código; NO hay token todavía (hay que llamar a `verificar_codigo`)::

        {"verificacion_requerida": True, "familia": None, "token": None, "canal": "email"|"consola"}

    Lanza ValueError (→ 400) si el correo ya está registrado y VERIFICADO, o los datos
    no son válidos. Un correo registrado pero SIN verificar se puede "re-dar de alta"
    (actualiza credenciales y reenvía el código).
    """
    email = _normalizar_email(email)
    nombre_familia = (nombre_familia or "").strip()
    _validar_signup(email, password, nombre_familia)

    db.init_db()
    with db.get_session() as sesion:
        fam = sesion.exec(select(Familia).where(Familia.email == email)).first()
        if fam is not None and fam.verificada:
            raise ValueError("Ya hay una familia registrada con ese correo. Inicia sesión.")
        if fam is None:
            fam = Familia(id=secrets.token_hex(8), email=email, password_hash="", nombre_familia="")
        # Alta nueva o re-alta de una cuenta aún sin verificar: (re)fijamos credenciales.
        fam.password_hash = seguridad.hashear(password)
        fam.nombre_familia = nombre_familia

        if not settings_service.get("EMAIL_VERIFICACION"):
            fam.verificada = True
            fam.codigo_hash = None
            fam.codigo_expira = None
            fam.codigo_intentos = 0
            sesion.add(fam)
            sesion.commit()
            logger.info("Nueva familia registrada: %s (%s).", fam.nombre_familia, fam.email)
            return {
                "verificacion_requerida": False,
                "familia": _dto(fam),
                "token": _crear_sesion(fam.id),
                "canal": None,
            }

        # Verificación activa: cuenta pendiente + código por correo.
        fam.verificada = False
        codigo = _asignar_codigo(fam)
        sesion.add(fam)
        sesion.commit()  # commit ANTES de enviar: si el envío falla, el reenvío funciona
        canal = email_service.enviar_codigo(email, nombre_familia, codigo, _CODIGO_TTL_MIN)
        logger.info("Alta pendiente de verificación: %s (canal=%s).", email, canal)
        return {"verificacion_requerida": True, "familia": None, "token": None, "canal": canal}


def verificar_codigo(email: str, codigo: str, ip: str = "?") -> tuple[dict, str]:
    """Verifica el código (OTP) de un alta pendiente y devuelve ``(familia, token)``.

    Lanza BloqueoLoginError (→ 429) si la IP está bloqueada, o ValueError (→ 400) si el
    código es incorrecto, ha caducado o se agotaron los intentos.
    """
    _comprobar_bloqueo(ip)
    time.sleep(_RETARDO_LOGIN)
    email = _normalizar_email(email)

    db.init_db()
    with db.get_session() as sesion:
        fam = sesion.exec(select(Familia).where(Familia.email == email)).first()
        if fam is None:
            _registrar_fallo(ip)
            raise ValueError("Código o correo incorrectos.")
        if fam.verificada:  # ya verificada: idempotente, iniciamos sesión
            _limpiar_fallos(ip)
            return _dto(fam), _crear_sesion(fam.id)

        expira = fam.codigo_expira
        if expira is not None and expira.tzinfo is None:
            expira = expira.replace(tzinfo=UTC)
        if fam.codigo_hash is None or expira is None or expira < datetime.now(UTC):
            raise ValueError("El código ha caducado. Pide uno nuevo.")
        if (fam.codigo_intentos or 0) >= _CODIGO_MAX_INTENTOS:
            raise ValueError("Demasiados intentos con este código. Pide uno nuevo.")
        if not seguridad.verificar((codigo or "").strip(), fam.codigo_hash):
            fam.codigo_intentos = (fam.codigo_intentos or 0) + 1
            sesion.add(fam)
            sesion.commit()
            _registrar_fallo(ip)
            raise ValueError("Código o correo incorrectos.")

        # Correcto: activamos la cuenta y limpiamos el código.
        fam.verificada = True
        fam.codigo_hash = None
        fam.codigo_expira = None
        fam.codigo_intentos = 0
        sesion.add(fam)
        sesion.commit()
        _limpiar_fallos(ip)
        logger.info("Familia verificada: %s (%s).", fam.nombre_familia, fam.email)
        return _dto(fam), _crear_sesion(fam.id)


def reenviar_codigo(email: str) -> str:
    """Reenvía un código nuevo a un alta pendiente. Devuelve el canal (``email``/``consola``).

    Lanza ValueError (→ 400) si no hay cuenta con ese correo o ya está verificada.
    """
    email = _normalizar_email(email)
    db.init_db()
    with db.get_session() as sesion:
        fam = sesion.exec(select(Familia).where(Familia.email == email)).first()
        if fam is None:
            raise ValueError("No hay ninguna cuenta pendiente con ese correo.")
        if fam.verificada:
            raise ValueError("Esta cuenta ya está verificada. Inicia sesión.")
        codigo = _asignar_codigo(fam)
        sesion.add(fam)
        sesion.commit()
        return email_service.enviar_codigo(email, fam.nombre_familia, codigo, _CODIGO_TTL_MIN)


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------
def login(email: str, password: str, ip: str = "?") -> tuple[dict, str]:
    """Valida email+contraseña y devuelve ``(familia, token)``.

    Lanza BloqueoLoginError (→ 429) si la IP está bloqueada por intentos, o
    ValueError (→ 400) si las credenciales no son correctas. Aplica retardo fijo y
    cuenta los fallos por IP (anti-fuerza-bruta, igual que el login de admin).
    """
    _comprobar_bloqueo(ip)
    time.sleep(_RETARDO_LOGIN)
    email = _normalizar_email(email)

    db.init_db()
    with db.get_session() as sesion:
        fam = sesion.exec(select(Familia).where(Familia.email == email)).first()
        # Mismo mensaje para email inexistente y contraseña mala: no revelamos si un
        # correo está o no registrado. Verificamos el hash aunque no exista la familia
        # NO es necesario aquí porque el retardo fijo ya iguala los tiempos.
        if (
            fam is None
            or not fam.activo
            or not seguridad.verificar(password or "", fam.password_hash)
        ):
            _registrar_fallo(ip)
            raise ValueError("Correo o contraseña incorrectos.")
        # Contraseña correcta pero cuenta sin verificar: no damos sesión (el mensaje solo
        # se ve tras acertar la contraseña, así que no filtra el estado de un correo ajeno).
        if not fam.verificada:
            _limpiar_fallos(ip)
            raise ValueError(
                "Tu cuenta aún no está verificada. Revisa tu correo o pide un código nuevo."
            )
        _limpiar_fallos(ip)
        return _dto(fam), _crear_sesion(fam.id)


def logout(token: str | None) -> None:
    """Cierra la sesión: borra el token del dispositivo de la tabla de sesiones."""
    if not token:
        return
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(SesionFamilia, _hash_token(token))
        if fila is not None:
            sesion.delete(fila)
            sesion.commit()


# ---------------------------------------------------------------------------
# Sesiones persistentes (token de vida larga en SQLite, solo su hash)
# ---------------------------------------------------------------------------
def _hash_token(token: str) -> str:
    """Hash del token de sesión (SHA-256). En la BBDD solo guardamos esto."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _crear_sesion(familia_id: str) -> str:
    """Crea una sesión persistente y devuelve el token en claro (solo se ve aquí)."""
    token = secrets.token_urlsafe(32)
    db.init_db()
    with db.get_session() as sesion:
        sesion.add(
            SesionFamilia(
                token_hash=_hash_token(token),
                familia_id=familia_id,
                expira_en=datetime.now(UTC) + timedelta(days=_SESION_DIAS),
            )
        )
        sesion.commit()
    return token


def validar_sesion(token: str | None) -> dict | None:
    """Devuelve la familia (dict público) si el token es una sesión viva, o None.

    Limpia de paso la sesión si ha caducado. Como la app la usan niños en el mismo
    equipo, no invalidamos por IP: el token es el que manda.
    """
    if not token:
        return None
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(SesionFamilia, _hash_token(token))
        if fila is None:
            return None
        expira = fila.expira_en
        if expira.tzinfo is None:  # SQLite devuelve datetimes naive: los tratamos como UTC
            expira = expira.replace(tzinfo=UTC)
        if expira < datetime.now(UTC):
            sesion.delete(fila)
            sesion.commit()
            return None
        fam = sesion.get(Familia, fila.familia_id)
        if fam is None or not fam.activo:
            return None
        return _dto(fam)


def hay_familias() -> bool:
    """¿Existe ya alguna familia registrada? (para adaptar el primer arranque)."""
    db.init_db()
    with db.get_session() as sesion:
        return sesion.exec(select(Familia)).first() is not None


# ---------------------------------------------------------------------------
# Perfil de familia: nombre + niños (multi-perfil, Hito 9.2c)
# ---------------------------------------------------------------------------
def actualizar_perfil(
    familia_id: str, nombre_familia: str | None = None, ninos: list[dict] | None = None
) -> dict:
    """Edita el nombre de la familia y/o la lista de niños (cada uno nombre+sexo).

    Devuelve el perfil actualizado. Lanza ValueError (→ 400) si el nombre queda vacío o
    la lista de niños supera el tope.
    """
    db.init_db()
    with db.get_session() as sesion:
        fam = sesion.get(Familia, familia_id)
        if fam is None:
            raise ValueError("La familia no existe.")
        if nombre_familia is not None:
            limpio = (nombre_familia or "").strip()
            if not limpio:
                raise ValueError("El nombre de familia no puede estar vacío.")
            fam.nombre_familia = limpio
        if ninos is not None:
            limpios = [nino for e in ninos if (nino := _sanear_nino(e)) is not None]
            if len(limpios) > _MAX_NINOS:
                raise ValueError(f"Como mucho {_MAX_NINOS} niños por familia.")
            fam.ninos = json.dumps(limpios, ensure_ascii=False)
        sesion.add(fam)
        sesion.commit()
        sesion.refresh(fam)
        return _dto(fam)


# ---------------------------------------------------------------------------
# PIN de familia (protege foto + edición de perfil; NO da acceso a Admin)
# ---------------------------------------------------------------------------
def set_pin_familia(familia_id: str, pin_nuevo: str, pin_actual: str | None = None) -> None:
    """Pone o cambia el PIN de familia (4 dígitos). Si ya había uno, exige el actual.

    Lanza ValueError (→ 400) si el PIN nuevo no son 4 dígitos o el actual no coincide.
    """
    db.init_db()
    with db.get_session() as sesion:
        fam = sesion.get(Familia, familia_id)
        if fam is None:
            raise ValueError("La familia no existe.")
        if fam.pin_familia_hash and not seguridad.verificar(
            (pin_actual or "").strip(), fam.pin_familia_hash
        ):
            raise ValueError("El PIN actual no es correcto.")
        if not _RE_PIN_FAMILIA.match((pin_nuevo or "").strip()):
            raise ValueError("El PIN de familia debe tener exactamente 4 dígitos.")
        fam.pin_familia_hash = seguridad.hashear(pin_nuevo.strip())
        sesion.add(fam)
        sesion.commit()


def verificar_pin_familia(familia_id: str, pin: str) -> bool:
    """¿Es correcto el PIN de familia? (consentimiento de foto / editar perfil).

    Si la familia NO tiene PIN configurado, devuelve True (no hay barrera que superar).
    """
    db.init_db()
    with db.get_session() as sesion:
        fam = sesion.get(Familia, familia_id)
        if fam is None:
            return False
        if not fam.pin_familia_hash:
            return True
        return seguridad.verificar((pin or "").strip(), fam.pin_familia_hash)


# ---------------------------------------------------------------------------
# Borrado de cuenta (derecho de supresión RGPD, art. 17)
# ---------------------------------------------------------------------------
def eliminar(familia_id: str) -> None:
    """Elimina una familia y TODOS sus datos: la cuenta y sus sesiones persistentes.

    Es el derecho de supresión (RGPD art. 17) en autoservicio. Como la lista de niños
    vive en la propia fila de la familia, borrar la fila borra también esos datos. Tras
    esto, cualquier token de sesión de esa familia deja de ser válido (ya no hay fila)."""
    db.init_db()
    with db.get_session() as sesion:
        for s in sesion.exec(
            select(SesionFamilia).where(SesionFamilia.familia_id == familia_id)
        ).all():
            sesion.delete(s)
        fam = sesion.get(Familia, familia_id)
        if fam is not None:
            sesion.delete(fam)
            logger.info("Familia ELIMINADA (RGPD): %s (%s).", fam.nombre_familia, fam.email)
        sesion.commit()

    # Purga también su auditoría (dato personal del menor). Import perezoso para no
    # crear un ciclo (auditoria_service importa settings, no familias).
    from backend.services import auditoria_service

    auditoria_service.eliminar_familia(familia_id)


# ---------------------------------------------------------------------------
# Dependencia de FastAPI: exige una sesión de familia válida
# ---------------------------------------------------------------------------
def requiere_familia(x_family_token: str | None = Header(default=None)) -> dict:
    """Deja pasar solo con una sesión de familia válida; devuelve la familia (dict).

    Protege los endpoints de gestión del perfil (editar niños, PIN). El flujo del
    niño (jugar) NO la lleva: va abierto dentro de la sesión ya iniciada.
    """
    familia = validar_sesion(x_family_token)
    if familia is None:
        raise HTTPException(
            status_code=401, detail="Inicia sesión con tu familia para gestionar el perfil."
        )
    return familia


def familia_opcional(x_family_token: str | None = Header(default=None)) -> dict | None:
    """Como `requiere_familia` pero SIN exigir sesión: devuelve la familia o None.

    Para los endpoints del flujo del niño (generar/chat), que van abiertos pero cuya
    actividad queremos ATRIBUIR a la familia en la auditoría cuando hay sesión.
    """
    return validar_sesion(x_family_token)
