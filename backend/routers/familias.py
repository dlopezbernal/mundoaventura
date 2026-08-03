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

from fastapi import APIRouter, Header, HTTPException, Request

from backend.schemas.familias import FamiliaLogin, FamiliaSignup
from backend.schemas.respuestas import (
    FamiliaAuthResponse,
    FamiliaSesion,
    FamiliasEstado,
    OkResponse,
)
from backend.services import familias_service

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


@router.post("/signup", response_model=FamiliaAuthResponse)
def signup(req: FamiliaSignup):
    """Da de alta una familia (auto-login). 400 si el email ya existe o es inválido."""
    try:
        familia, token = familias_service.crear(req.email, req.password, req.nombre_familia)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "token": token, "familia": familia}


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
