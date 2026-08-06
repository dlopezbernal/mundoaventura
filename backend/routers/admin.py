"""
routers/admin.py — Acceso de administrador + import/export (Hito 7, 2FA en H9.2d)
=================================================================================

Puerta de entrada al área de Administración (detrás de una contraseña de administración,
con 2FA TOTP opcional) y utilidades de mantenimiento. La lógica vive en admin_service.

  GET  /api/admin/status         → ¿hay contraseña? ¿sesión válida? ¿2FA activo?   (público)
  POST /api/admin/setup          → crea la contraseña la 1ª vez y devuelve token.  (público)
  POST /api/admin/login          → valida contraseña (+2FA si aplica) → token.     (público)
  POST /api/admin/logout         → invalida el token de la cabecera.               (público)
  POST /api/admin/change         → cambia la contraseña (requiere la actual).      (protegido)
  POST /api/admin/2fa/enrolar    → inicia el enrolamiento 2FA (QR + clave).        (protegido)
  POST /api/admin/2fa/confirmar  → confirma y activa el 2FA (recovery codes).      (protegido)
  POST /api/admin/2fa/desactivar → desactiva el 2FA (exige la contraseña).         (protegido)
  GET  /api/admin/export         → descarga la configuración (sin secretos).       (protegido)
  POST /api/admin/import         → restaura configuración (con copia de seguridad).(protegido)

Los endpoints públicos son los mínimos para arrancar/entrar; el resto exige el
token (dependencia requiere_admin). Los SECRETOS (claves API) nunca se exportan.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from backend.schemas.admin import (
    Admin2FAConfirmar,
    Admin2FADesactivar,
    AdminCambiar,
    AdminPassword,
    ImportRequest,
)
from backend.schemas.respuestas import (
    Admin2FAEnrol,
    Admin2FARecovery,
    AdminLoginResponse,
    AdminStatus,
    ConfigExport,
    ImportResult,
    OkResponse,
    TokenResponse,
)
from backend.services import (
    admin_service,
    personajes_service,
    settings_service,
    ubicaciones_service,
)

router = APIRouter(prefix="/api/admin", tags=["Configuración · Admin"])


@router.get("/status", response_model=AdminStatus)
def estado(x_admin_token: str | None = Header(default=None)):
    """¿Hay contraseña configurada? ¿El token sigue válido? ¿Está el 2FA activo?"""
    return {
        "configurado": admin_service.esta_configurado(),
        "sesion_activa": admin_service.validar_token(x_admin_token),
        "dos_factor_activo": admin_service.dos_factor_activo(),
    }


@router.post("/setup", response_model=TokenResponse)
def setup(req: AdminPassword):
    """Crea la contraseña de administración por primera vez (auto-login). 400 si ya existe o es corta."""
    try:
        token = admin_service.configurar(req.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "token": token}


@router.post("/login", response_model=AdminLoginResponse)
def login(req: AdminPassword, request: Request):
    """Valida la contraseña (y el 2FA si está activo) y devuelve un token de sesión.

    Si el 2FA está activo y no se ha aportado código, responde 200 con
    `requiere_2fa=true` y sin token (el frontend pide el código y reintenta). 400 si la
    contraseña o el código son incorrectos; 429 si la IP está bloqueada.
    """
    ip = request.client.host if request.client else "?"
    try:
        token = admin_service.login(req.password, ip, req.codigo)
    except admin_service.Requiere2FAError:
        return {"ok": False, "requiere_2fa": True, "token": ""}
    except admin_service.BloqueoLoginError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "requiere_2fa": False, "token": token}


@router.post("/logout", response_model=OkResponse)
def logout(x_admin_token: str | None = Header(default=None)):
    """Cierra la sesión invalidando el token de la cabecera."""
    admin_service.cerrar_sesion(x_admin_token)
    return {"ok": True}


@router.post(
    "/change",
    dependencies=[Depends(admin_service.requiere_admin)],
    response_model=OkResponse,
)
def cambiar_password(req: AdminCambiar):
    """Cambia la contraseña (requiere la actual). 400 si la actual no es correcta."""
    try:
        admin_service.cambiar(req.password_actual, req.password_nueva)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post(
    "/2fa/enrolar",
    dependencies=[Depends(admin_service.requiere_admin)],
    response_model=Admin2FAEnrol,
)
def enrolar_2fa():
    """Inicia el enrolamiento 2FA: devuelve el QR + la clave (aún NO activa el 2FA)."""
    try:
        return admin_service.iniciar_enrolamiento_2fa()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/2fa/confirmar",
    dependencies=[Depends(admin_service.requiere_admin)],
    response_model=Admin2FARecovery,
)
def confirmar_2fa(req: Admin2FAConfirmar):
    """Confirma el enrolamiento con un código y activa el 2FA. Devuelve los códigos de recuperación."""
    try:
        codigos = admin_service.confirmar_enrolamiento_2fa(req.codigo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "recovery_codes": codigos}


@router.post(
    "/2fa/desactivar",
    dependencies=[Depends(admin_service.requiere_admin)],
    response_model=OkResponse,
)
def desactivar_2fa(req: Admin2FADesactivar):
    """Desactiva el 2FA (exige la contraseña actual). 400 si la contraseña no es correcta."""
    try:
        admin_service.desactivar_2fa(req.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.get(
    "/export",
    dependencies=[Depends(admin_service.requiere_admin)],
    response_model=ConfigExport,
)
def exportar():
    """Devuelve la configuración completa (ajustes + catálogos), SIN secretos."""
    ajustes = {e["clave"]: e["valor"] for e in settings_service.exportar()}
    return {
        "version": 1,
        "exportado_en": datetime.now(UTC).isoformat(),
        "ajustes": ajustes,
        "personajes": personajes_service.listar(incluir_inactivos=True),
        "ubicaciones": ubicaciones_service.listar(incluir_inactivos=True),
    }


# Campos editables al importar (los que aceptan crear/actualizar de cada servicio).
_CAMPOS_PERSONAJE = (
    "nombre",
    "categoria",
    "emoji",
    "prompt_imagen",
    "voz_id",
    "prompt_sistema_override",
    "activo",
)
_CAMPOS_UBICACION = ("nombre", "emoji", "prompt_imagen", "activo")


@router.post(
    "/import",
    dependencies=[Depends(admin_service.requiere_admin)],
    response_model=ImportResult,
)
def importar(req: ImportRequest):
    """Restaura una configuración exportada. Hace COPIA DE SEGURIDAD del SQLite antes.

    Aplica ajustes (validados), y crea/actualiza personajes y ubicaciones. Los
    documentos del RAG y las claves API NO se importan (los ficheros y el `.env`
    se gestionan aparte). 400 si algún valor es inválido.
    """
    datos = req.datos or {}
    backup = admin_service.backup_sqlite()
    try:
        resumen = {"ajustes": 0, "personajes": 0, "ubicaciones": 0}

        ajustes = datos.get("ajustes")
        if isinstance(ajustes, dict) and ajustes:
            settings_service.set_many(ajustes)
            resumen["ajustes"] = len(ajustes)

        for p in datos.get("personajes", []):
            pid = p.get("id")
            if not pid:
                continue
            campos = {k: p[k] for k in _CAMPOS_PERSONAJE if k in p}
            if personajes_service.existe(pid):
                personajes_service.actualizar(pid, campos)
            else:
                personajes_service.crear({"id": pid, **campos})
            resumen["personajes"] += 1

        for u in datos.get("ubicaciones", []):
            uid = u.get("id")
            if not uid:
                continue
            campos = {k: u[k] for k in _CAMPOS_UBICACION if k in u}
            if ubicaciones_service.existe(uid):
                ubicaciones_service.actualizar(uid, campos)
            else:
                ubicaciones_service.crear({"id": uid, **campos})
            resumen["ubicaciones"] += 1
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"ok": True, "resumen": resumen, "backup": backup}
