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
        # Personajes: id + nombre + prompt de imagen + voz + categoría + emoji.
        # Desde el Hito 4 el catálogo se lee de esta tabla (personajes_service) y
        # el frontend lo consume por API, así que sembramos TODOS los campos.
        for pid, datos in personajes_cfg.PROMPTS.items():
            fila = sesion.get(Personaje, pid)
            if fila is None:
                sesion.add(
                    Personaje(
                        id=pid,
                        nombre=personajes_cfg.NOMBRES.get(pid, pid),
                        categoria=personajes_cfg.CATEGORIAS.get(pid),
                        emoji=personajes_cfg.EMOJIS.get(pid),
                        prompt_imagen=datos["prompt"],
                        voz_id=personajes_cfg.VOCES.get(pid),
                        activo=True,
                    )
                )
                personajes_nuevos += 1
            else:
                # Backfill: BBDD sembradas antes del Hito 4 no tienen categoría/emoji.
                # Solo rellenamos lo que falte; nunca pisamos un valor ya editado.
                if fila.categoria is None:
                    fila.categoria = personajes_cfg.CATEGORIAS.get(pid)
                if fila.emoji is None:
                    fila.emoji = personajes_cfg.EMOJIS.get(pid)
                sesion.add(fila)

        # Ubicaciones: id + nombre + emoji + prompt. Desde el Hito 6 el catálogo se
        # lee de esta tabla (ubicaciones_service) y el frontend lo consume por API.
        for uid, datos in ubicaciones_cfg.UBICACIONES.items():
            fila = sesion.get(Ubicacion, uid)
            if fila is None:
                sesion.add(
                    Ubicacion(
                        id=uid,
                        nombre=ubicaciones_cfg.NOMBRES.get(uid),
                        emoji=ubicaciones_cfg.EMOJIS.get(uid),
                        prompt=datos["prompt"],
                        activo=True,
                    )
                )
                ubicaciones_nuevas += 1
            else:
                # Backfill: BBDD sembradas antes del Hito 6 no tienen nombre/emoji.
                if fila.nombre is None:
                    fila.nombre = ubicaciones_cfg.NOMBRES.get(uid)
                if fila.emoji is None:
                    fila.emoji = ubicaciones_cfg.EMOJIS.get(uid)
                sesion.add(fila)

        sesion.commit()

    return {
        "ajustes": ajustes_nuevos,
        "personajes": personajes_nuevos,
        "ubicaciones": ubicaciones_nuevas,
    }
