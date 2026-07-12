"""
routers/admin.py — Acceso de administrador + import/export (Hito 7)
===================================================================

Puerta de entrada al área de configuración (toda ella detrás de un PIN de adulto)
y utilidades de mantenimiento. La lógica de sesión vive en admin_service.

  GET  /api/admin/status   → ¿hay PIN configurado? ¿la sesión actual es válida?  (público)
  POST /api/admin/setup    → crea el PIN la primera vez y devuelve token.        (público)
  POST /api/admin/login    → valida el PIN y devuelve token.                     (público)
  POST /api/admin/logout   → invalida el token de la cabecera.                   (público)
  POST /api/admin/change   → cambia el PIN (requiere el actual).                 (protegido)
  GET  /api/admin/export   → descarga la configuración (sin secretos).           (protegido)
  POST /api/admin/import   → restaura configuración (con copia de seguridad).    (protegido)

Los endpoints públicos son los mínimos para arrancar/entrar; el resto exige el
token (dependencia requiere_admin). Los SECRETOS (claves API) nunca se exportan.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException

from backend.schemas.admin import AdminCambiar, AdminPin, ImportRequest
from backend.services import (
    admin_service,
    personajes_service,
    settings_service,
    ubicaciones_service,
)

router = APIRouter(prefix="/api/admin", tags=["Configuración · Admin"])


@router.get("/status")
def estado(x_admin_token: str | None = Header(default=None)):
    """¿Hay PIN configurado? ¿El token de la cabecera sigue siendo válido?"""
    return {
        "configurado": admin_service.esta_configurado(),
        "sesion_activa": admin_service.validar_token(x_admin_token),
    }


@router.post("/setup")
def setup(req: AdminPin):
    """Crea el PIN de adulto por primera vez (auto-login). 400 si ya existe o es corto."""
    try:
        token = admin_service.configurar(req.pin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "token": token}


@router.post("/login")
def login(req: AdminPin):
    """Valida el PIN y devuelve un token de sesión. 400 si el PIN es incorrecto."""
    try:
        token = admin_service.login(req.pin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "token": token}


@router.post("/logout")
def logout(x_admin_token: str | None = Header(default=None)):
    """Cierra la sesión invalidando el token de la cabecera."""
    admin_service.cerrar_sesion(x_admin_token)
    return {"ok": True}


@router.post("/change", dependencies=[Depends(admin_service.requiere_admin)])
def cambiar_pin(req: AdminCambiar):
    """Cambia el PIN (requiere el actual). 400 si el actual no es correcto."""
    try:
        admin_service.cambiar(req.pin_actual, req.pin_nuevo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/export", dependencies=[Depends(admin_service.requiere_admin)])
def exportar():
    """Devuelve la configuración completa (ajustes + catálogos), SIN secretos."""
    ajustes = {e["clave"]: e["valor"] for e in settings_service.exportar()}
    return {
        "version": 1,
        "exportado_en": datetime.utcnow().isoformat(),
        "ajustes": ajustes,
        "personajes": personajes_service.listar(incluir_inactivos=True),
        "ubicaciones": ubicaciones_service.listar(incluir_inactivos=True),
    }


# Campos editables al importar (los que aceptan crear/actualizar de cada servicio).
_CAMPOS_PERSONAJE = (
    "nombre", "categoria", "emoji", "prompt_imagen", "voz_id",
    "prompt_sistema_override", "activo",
)
_CAMPOS_UBICACION = ("nombre", "emoji", "prompt_imagen", "activo")


@router.post("/import", dependencies=[Depends(admin_service.requiere_admin)])
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
