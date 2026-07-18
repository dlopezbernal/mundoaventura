"""
routers/personajes.py — Endpoints del catálogo de personajes (Hito 4)
=====================================================================

CRUD del catálogo (la lógica vive en services/personajes_service.py) + la lista de
voces de ElevenLabs para el desplegable de la pantalla de configuración:

  GET    /api/personajes         → catálogo (por defecto solo activos; ?todos=1 incluye inactivos).
  POST   /api/personajes         → alta de un personaje nuevo (+ carpeta de documentos).
  PUT    /api/personajes/{id}    → editar campos de un personaje.
  DELETE /api/personajes/{id}    → borrar un personaje del catálogo.
  GET    /api/voices             → voces disponibles en ElevenLabs (para elegir voz_id).
  POST   /api/voices/probar      → sintetiza una frase fija con la voz indicada (botón
                                    "Probar voz" de la pestaña Personajes).

Lo consumen tanto la pantalla del niño (elegir personaje) como la pestaña de
configuración. El control de acceso admin a la edición llega en el Hito 7.
"""

import base64

from fastapi import APIRouter, Depends, HTTPException

from backend import config
from backend.schemas.personajes import PersonajeCrear, PersonajeEditar, VozProbar
from backend.services import admin_service, personajes_service, voice_service

router = APIRouter(prefix="/api", tags=["Configuración · Personajes"])

# Dependencia de adulto: el catálogo se LEE en público (lo usa el niño), pero
# crear/editar/borrar y listar voces exigen el PIN.
_admin = [Depends(admin_service.requiere_admin)]


@router.get("/personajes")
def listar_personajes(todos: bool = False):
    """Catálogo de personajes. Por defecto solo los activos; `?todos=1` incluye inactivos.

    Incluye `limite` (MAX_PERSONAJES) para que la pestaña de configuración pueda
    deshabilitar "Nuevo personaje" sin necesidad de otro endpoint.
    """
    return {
        "personajes": personajes_service.listar(incluir_inactivos=todos),
        "limite": config.MAX_PERSONAJES,
    }


@router.post("/personajes", dependencies=_admin)
def crear_personaje(req: PersonajeCrear):
    """Crea un personaje nuevo y todas sus piezas del invariante. 400 si algo es inválido."""
    try:
        personaje = personajes_service.crear(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "personaje": personaje}


@router.put("/personajes/{personaje_id}", dependencies=_admin)
def editar_personaje(personaje_id: str, req: PersonajeEditar):
    """Actualiza los campos indicados de un personaje (el id no cambia). 400 si inválido."""
    try:
        # exclude_unset: solo tocamos los campos que el cliente envió de verdad
        # (así enviar voz_id=null borra la voz, pero omitirlo la deja intacta).
        personaje = personajes_service.actualizar(personaje_id, req.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "personaje": personaje}


@router.delete("/personajes/{personaje_id}", dependencies=_admin)
def borrar_personaje(personaje_id: str):
    """Borra un personaje del catálogo. 400 si no existe."""
    try:
        personajes_service.eliminar(personaje_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/voices", dependencies=_admin)
def listar_voces():
    """Voces de ElevenLabs para el desplegable: {disponible, voces, mensaje}."""
    return voice_service.listar_voces()


@router.post("/voices/probar", dependencies=_admin)
def probar_voz(req: VozProbar):
    """Sintetiza la frase de prueba con `voz_id` y la devuelve en base64 (mp3)."""
    try:
        audio_bytes = voice_service.sintetizar(voice_service.FRASE_PRUEBA_VOZ, req.voz_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"audio_base64": base64.b64encode(audio_bytes).decode("ascii")}
