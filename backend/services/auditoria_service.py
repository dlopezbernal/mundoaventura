"""
services/auditoria_service.py — Registro de auditoría de uso (informe al adulto)
================================================================================

Guarda en SQLite (tabla `auditoria`) lo que hace cada familia/niño, para poder
enseñar un INFORME al adulto (pestaña Admin → Auditoría) y exportarlo a CSV.

Dos niveles, gobernados por ajustes de `settings_service` (editables en caliente):
  - AUDITORIA_ACTIVA (por defecto ON): registra METADATOS — evento, quién/cuándo,
    ids de personaje/ubicación, origen de la respuesta… SIN el texto.
  - AUDITORIA_CONTENIDO (por defecto OFF): guarda ADEMÁS el texto de las preguntas
    y respuestas (dato sensible de un menor → opt-in explícito).

PRIVACIDAD / RGPD: es dato personal de un menor. Se purga por retención
(AUDITORIA_RETENCION_DIAS) y con la supresión de la cuenta
(familias_service.eliminar → eliminar_familia). `familia_id` permite borrar solo
lo de una familia.

Regla de oro: registrar NUNCA debe romper el flujo del niño. Todo va envuelto en
try/except best-effort; si el log falla, se traga el error (con un warning).
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import delete, select

from backend import db
from backend.models import Auditoria
from backend.services import settings_service

logger = logging.getLogger(__name__)


# Tipos de evento (para filtrar el informe con nombres estables).
class Evento:
    LOGIN = "login"
    LOGOUT = "logout"
    SIGNUP = "signup"
    PERFIL = "perfil"  # alta/edición de los niños de la familia
    ESCENA = "escena"  # generación de imagen (personaje + ubicación/foto)
    PREGUNTA = "pregunta"  # una pregunta del niño en el chat (+ respuesta)


def _activa() -> bool:
    try:
        return bool(settings_service.get("AUDITORIA_ACTIVA"))
    except Exception:  # noqa: BLE001 — si settings falla, no auditamos (best-effort)
        return False


def _con_contenido() -> bool:
    try:
        return bool(settings_service.get("AUDITORIA_CONTENIDO"))
    except Exception:  # noqa: BLE001
        return False


def registrar(
    tipo: str,
    *,
    familia_id: str | None = None,
    familia_nombre: str | None = None,
    nino: str | None = None,
    detalle: dict[str, Any] | None = None,
    contenido: str | None = None,
    ip: str | None = None,
) -> None:
    """Registra un evento de auditoría. BEST-EFFORT: nunca lanza al llamador.

    Respeta los toggles: si AUDITORIA_ACTIVA está OFF no guarda nada; el `contenido`
    (texto de preguntas/respuestas) solo se guarda si AUDITORIA_CONTENIDO está ON.
    """
    try:
        if not _activa():
            return
        fila = Auditoria(
            tipo=tipo,
            familia_id=familia_id,
            familia_nombre=familia_nombre,
            nino=nino,
            detalle=json.dumps(detalle, ensure_ascii=False) if detalle else None,
            contenido=contenido if (contenido and _con_contenido()) else None,
            ip=ip,
        )
        db.init_db()
        with db.get_session() as sesion:
            sesion.add(fila)
            sesion.commit()
    except Exception:  # noqa: BLE001 — auditar jamás debe romper el flujo del niño
        logger.warning("No se pudo registrar el evento de auditoría '%s'.", tipo, exc_info=True)


def _fila_a_dict(f: Auditoria) -> dict[str, Any]:
    creado = f.creado_en
    if creado.tzinfo is None:
        creado = creado.replace(tzinfo=UTC)
    return {
        "id": f.id,
        "creado_en": creado.isoformat(),
        "tipo": f.tipo,
        "familia_id": f.familia_id,
        "familia_nombre": f.familia_nombre,
        "nino": f.nino,
        "detalle": f.detalle,
        "contenido": f.contenido,
        "ip": f.ip,
    }


def listar(
    *,
    limite: int = 200,
    offset: int = 0,
    tipo: str | None = None,
    familia_id: str | None = None,
) -> dict[str, Any]:
    """Devuelve eventos (más recientes primero) con filtros opcionales y el total."""
    db.init_db()
    with db.get_session() as sesion:
        cond = []
        if tipo:
            cond.append(Auditoria.tipo == tipo)
        if familia_id:
            cond.append(Auditoria.familia_id == familia_id)

        consulta = select(Auditoria)
        for c in cond:
            consulta = consulta.where(c)
        consulta = consulta.order_by(Auditoria.creado_en.desc()).offset(offset).limit(limite)
        filas = sesion.exec(consulta).all()

        total_q = select(Auditoria)
        for c in cond:
            total_q = total_q.where(c)
        total = len(sesion.exec(total_q).all())

    return {"eventos": [_fila_a_dict(f) for f in filas], "total": total}


def exportar_csv(*, tipo: str | None = None, familia_id: str | None = None) -> str:
    """Vuelca todos los eventos (con los filtros dados) a texto CSV para el informe."""
    import csv
    import io

    db.init_db()
    with db.get_session() as sesion:
        consulta = select(Auditoria)
        if tipo:
            consulta = consulta.where(Auditoria.tipo == tipo)
        if familia_id:
            consulta = consulta.where(Auditoria.familia_id == familia_id)
        filas = sesion.exec(consulta.order_by(Auditoria.creado_en.desc())).all()

    buffer = io.StringIO()
    campos = [
        "creado_en",
        "tipo",
        "familia_nombre",
        "familia_id",
        "nino",
        "detalle",
        "contenido",
        "ip",
    ]
    escritor = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore")
    escritor.writeheader()
    for f in filas:
        escritor.writerow(_fila_a_dict(f))
    return buffer.getvalue()


def purgar_antiguos() -> int:
    """Borra los registros más viejos que AUDITORIA_RETENCION_DIAS. Devuelve cuántos."""
    try:
        dias = int(settings_service.get("AUDITORIA_RETENCION_DIAS"))
    except Exception:  # noqa: BLE001
        dias = 90
    limite = datetime.now(UTC) - timedelta(days=dias)
    db.init_db()
    with db.get_session() as sesion:
        viejos = sesion.exec(select(Auditoria).where(Auditoria.creado_en < limite)).all()
        n = len(viejos)
        for f in viejos:
            sesion.delete(f)
        sesion.commit()
    if n:
        logger.info("Auditoría: purgados %s registros con más de %s días.", n, dias)
    return n


def eliminar_familia(familia_id: str) -> int:
    """Borra TODA la auditoría de una familia (supresión RGPD). Devuelve cuántos."""
    db.init_db()
    with db.get_session() as sesion:
        filas = sesion.exec(select(Auditoria).where(Auditoria.familia_id == familia_id)).all()
        n = len(filas)
        sesion.exec(delete(Auditoria).where(Auditoria.familia_id == familia_id))
        sesion.commit()
    return n
