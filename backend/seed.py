"""
backend/seed.py — Volcado inicial de "código → BBDD" (idempotente)
==================================================================

Al arrancar por primera vez, vuelca a SQLite los valores que hoy viven en el
código, para que la UI de configuración pueda mostrarlos y editarlos:

  - AJUSTES  (config.py)        → tabla `settings`  (vía settings_service.seed)
  - PERSONAJES (personajes.py)  → tabla `personajes`
  - UBICACIONES (ubicaciones.py)→ tabla `ubicaciones`

Es IDEMPOTENTE: solo inserta lo que aún no existe; nunca pisa lo ya guardado (así
un cambio hecho desde la UI no se revierte en el siguiente arranque).

Importante (compatibilidad hacia atrás): el catálogo se SIEMBRA aquí, pero la app
lo sigue LEYENDO del código por ahora; el cambio a consumirlo desde la BBDD llega
en sus hitos (personajes → Hito 4, ubicaciones → Hito 6).
"""

from backend import db
from backend import personajes as personajes_cfg
from backend import ubicaciones as ubicaciones_cfg
from backend.models import Personaje, Ubicacion
from backend.services import settings_service


def sembrar_todo() -> dict[str, int]:
    """Siembra ajustes + catálogo. Devuelve cuántas filas nuevas creó de cada tipo."""
    ajustes_nuevos = settings_service.seed()

    db.init_db()
    personajes_nuevos = 0
    ubicaciones_nuevas = 0
    with db.get_session() as sesion:
        # Personajes: id + nombre + prompt de imagen + voz (categoría/emoji viven
        # en el frontend; se completarán al mover el catálogo en el Hito 4).
        for pid, datos in personajes_cfg.PROMPTS.items():
            if sesion.get(Personaje, pid) is None:
                sesion.add(
                    Personaje(
                        id=pid,
                        nombre=personajes_cfg.NOMBRES.get(pid, pid),
                        prompt_imagen=datos["prompt"],
                        voz_id=personajes_cfg.VOCES.get(pid),
                        activo=True,
                    )
                )
                personajes_nuevos += 1

        # Ubicaciones: id + prompt (el nombre visible vive en el frontend; Hito 6).
        for uid, datos in ubicaciones_cfg.UBICACIONES.items():
            if sesion.get(Ubicacion, uid) is None:
                sesion.add(Ubicacion(id=uid, prompt=datos["prompt"], activo=True))
                ubicaciones_nuevas += 1

        sesion.commit()

    return {
        "ajustes": ajustes_nuevos,
        "personajes": personajes_nuevos,
        "ubicaciones": ubicaciones_nuevas,
    }
