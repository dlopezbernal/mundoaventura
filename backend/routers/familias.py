"""
routers/familias.py — Cuentas de familia + sesión (Hito 9.2)
=============================================================

Identidad de la aplicación: cada familia tiene una cuenta (email + contraseña) y una
sesión PERSISTENTE en su dispositivo. Estos endpoints son PÚBLICOS (son la puerta de
entrada); la protección real es que sin una sesión válida el frontend no deja jugar.

  GET  /api/familias/estado  → ¿hay ya alguna familia registrada?          (público)
  GET  /api/familias/me      → ¿hay sesión válida? datos de la familia.     (público)
  POST /api/familias/signup  → alta de familia (auto-login) + token.        (público)
  POST /api/familias/login   → inicia sesión + token.                       (público)
  POST /api/familias/logout  → cierra la sesión (borra el token).           (público)

El token de sesión viaja en la cabecera ``X-Family-Token`` (lo manda el frontend en
cada petición). La contraseña se guarda hasheada; el token solo se guarda hasheado.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from backend.schemas.familias import (
    FamiliaLogin,
    FamiliaPerfilUpdate,
    FamiliaPinSet,
    FamiliaPinVerificar,
    FamiliaReenviar,
    FamiliaSignup,
    FamiliaVerificar,
)
from backend.schemas.respuestas import (
    FamiliaAuthResponse,
    FamiliaDTO,
    FamiliaReenviarResponse,
    FamiliaSesion,
    FamiliasEstado,
    FamiliaSignupResponse,
    OkResponse,
)
from backend.services import email_service, familias_service

# Dependencia: exige sesión de familia y entrega la familia (dict) al handler.
_familia = Depends(familias_service.requiere_familia)

router = APIRouter(prefix="/api/familias", tags=["Familias"])


@router.get("/estado", response_model=FamiliasEstado)
def estado():
    """¿Hay ya alguna familia registrada? (el frontend muestra alta o login)."""
    return {"hay_familias": familias_service.hay_familias()}


@router.get("/me", response_model=FamiliaSesion)
def me(x_family_token: str | None = Header(default=None)):
    """Devuelve la familia de la sesión actual, o autenticada=false si no hay."""
    familia = familias_service.validar_sesion(x_family_token)
    return {"autenticada": familia is not None, "familia": familia}


@router.post("/signup", response_model=FamiliaSignupResponse, response_model_exclude_none=False)
def signup(req: FamiliaSignup):
    """Da de alta una familia.

    Sin verificación de correo (por defecto): responde con sesión iniciada. Con
    verificación activa: la cuenta queda pendiente y se envía un código. 400 si el
    correo ya está registrado o los datos no son válidos; 502 si no se pudo enviar
    el correo de verificación.
    """
    try:
        res = familias_service.crear(req.email, req.password, req.nombre_familia)
    except email_service.EmailError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **res}


@router.post("/verificar", response_model=FamiliaAuthResponse)
def verificar(req: FamiliaVerificar, request: Request):
    """Verifica el código (OTP) y devuelve la sesión. 400 si falla; 429 si IP bloqueada."""
    ip = request.client.host if request.client else "?"
    try:
        familia, token = familias_service.verificar_codigo(req.email, req.codigo, ip)
    except familias_service.BloqueoLoginError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "token": token, "familia": familia}


@router.post("/reenviar", response_model=FamiliaReenviarResponse)
def reenviar(req: FamiliaReenviar):
    """Reenvía el código de verificación a un alta pendiente. 400 si no procede."""
    try:
        canal = familias_service.reenviar_codigo(req.email)
    except email_service.EmailError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "canal": canal}


@router.post("/login", response_model=FamiliaAuthResponse)
def login(req: FamiliaLogin, request: Request):
    """Inicia sesión. 400 si las credenciales fallan; 429 si la IP está bloqueada."""
    ip = request.client.host if request.client else "?"
    try:
        familia, token = familias_service.login(req.email, req.password, ip)
    except familias_service.BloqueoLoginError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "token": token, "familia": familia}


@router.post("/logout", response_model=OkResponse)
def logout(x_family_token: str | None = Header(default=None)):
    """Cierra la sesión invalidando el token del dispositivo."""
    familias_service.logout(x_family_token)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Perfil de familia (multi-perfil, Hito 9.2c) — requieren sesión de familia
# ---------------------------------------------------------------------------
@router.put("/perfil", response_model=FamiliaDTO)
def actualizar_perfil(req: FamiliaPerfilUpdate, familia: dict = _familia):
    """Edita el nombre de la familia y/o la lista de niños. 400 si algo no es válido."""
    ninos = [n.model_dump() for n in req.ninos] if req.ninos is not None else None
    try:
        return familias_service.actualizar_perfil(familia["id"], req.nombre_familia, ninos)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/pin", response_model=OkResponse)
def poner_pin(req: FamiliaPinSet, familia: dict = _familia):
    """Pone o cambia el PIN de familia (4 dígitos). 400 si el actual no coincide o el nuevo no vale."""
    try:
        familias_service.set_pin_familia(familia["id"], req.pin_nuevo, req.pin_actual)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/pin/verificar", response_model=OkResponse)
def verificar_pin(req: FamiliaPinVerificar, familia: dict = _familia):
    """Comprueba el PIN de familia (consentimiento de foto / editar perfil).

    Responde 200 con ``ok`` según el PIN sea correcto o no (no es un error de la petición).
    """
    return {"ok": familias_service.verificar_pin_familia(familia["id"], req.pin)}


@router.delete("/cuenta", response_model=OkResponse)
def eliminar_cuenta(familia: dict = _familia):
    """Elimina la cuenta de la familia y todos sus datos (derecho de supresión RGPD)."""
    familias_service.eliminar(familia["id"])
    return {"ok": True}
