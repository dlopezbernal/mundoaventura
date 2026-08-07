"""
routers/apis.py — Endpoints de la pantalla "APIs" (claves de proveedores)
==========================================================================

Cinco puertas de entrada (la lógica vive en services/secrets_service.py):

  GET  /api/apis                     → estado de los 3 proveedores (enmascarado).
  PUT  /api/apis                     → guarda claves en el .env y las aplica en caliente.
  POST /api/apis/{proveedor}/test    → prueba de conexión (llamada ligera).
  POST /api/apis/{proveedor}/saldo   → cuota restante (services/saldo_service.py).
  POST /api/apis/{proveedor}/reveal  → devuelve la clave completa (icono del ojo 👁).

Las claves NUNCA se devuelven completas salvo en /reveal (petición explícita y
aparte). Toda esta zona va detrás del acceso admin (requiere_admin, aplicado en
bloque desde main.py).
"""

from fastapi import APIRouter, HTTPException

from backend.schemas.apis import ApisUpdateRequest
from backend.schemas.respuestas import (
    ApiRevealResponse,
    ApiSaldoResult,
    ApisGuardarResponse,
    ApisResponse,
    ApiTestResult,
)
from backend.services import secrets_service

router = APIRouter(prefix="/api/apis", tags=["Configuración · APIs"])


@router.get("", response_model=ApisResponse)
def listar_apis():
    """Estado de los 3 proveedores (configurado + clave enmascarada)."""
    return {"proveedores": secrets_service.estado()}


@router.put("", response_model=ApisGuardarResponse)
def guardar_apis(req: ApisUpdateRequest):
    """Guarda claves en el .env y las aplica en caliente. 400 si alguna es inválida."""
    try:
        proveedores = secrets_service.guardar(req.claves)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "proveedores": proveedores}


@router.post("/{proveedor}/test", response_model=ApiTestResult)
def probar_api(proveedor: str):
    """Prueba de conexión de un proveedor: {ok, mensaje}."""
    try:
        return secrets_service.probar(proveedor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{proveedor}/saldo", response_model=ApiSaldoResult)
def saldo_api(proveedor: str):
    """Cuánta cuota queda en un proveedor: {disponible, ok, mensaje, medidas, panel_url}.

    Es POST y no GET a propósito, igual que `/test`: no es un recurso que se pueda
    cachear, y en el caso del LLM la consulta **gasta una petición de inferencia**
    (es la única que devuelve las cabeceras de cuota). Nada la dispara sola: solo
    el botón del adulto.
    """
    try:
        return secrets_service.saldo(proveedor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{proveedor}/reveal", response_model=ApiRevealResponse)
def revelar_api(proveedor: str):
    """Devuelve la clave COMPLETA de un proveedor (para el icono del ojo)."""
    try:
        return {"proveedor": proveedor, "clave": secrets_service.revelar(proveedor)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
