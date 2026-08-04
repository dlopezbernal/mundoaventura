"""Tests de la auditoría de uso (Hito 10): servicio + toggles + endpoints + RGPD.

Se aísla la BBDD en tmp por test (como test_familias). Los toggles se controlan
con settings_service.set_many sobre la BBDD temporal (invalidando su caché).
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from backend import config, db
from backend.main import app
from backend.models import Auditoria
from backend.services import admin_service, auditoria_service, familias_service, settings_service
from backend.services.auditoria_service import Evento

_CLIENTE = TestClient(app)


@pytest.fixture(autouse=True)
def _entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "test_auditoria.sqlite3")
    monkeypatch.setattr(db, "_engine", None)
    settings_service._cache = None  # la caché de ajustes debe releer la BBDD temporal
    db.init_db()
    yield
    monkeypatch.setattr(db, "_engine", None)
    settings_service._cache = None


def _envejecer(id_fila: int, dias: int) -> None:
    """Retrasa `creado_en` de una fila para probar la retención."""
    with db.get_session() as sesion:
        fila = sesion.get(Auditoria, id_fila)
        fila.creado_en = datetime.now(UTC) - timedelta(days=dias)
        sesion.add(fila)
        sesion.commit()


# --- Toggle ACTIVA ---
def test_no_registra_si_desactivada():
    settings_service.set_many({"AUDITORIA_ACTIVA": False})
    auditoria_service.registrar(Evento.LOGIN, familia_id="f1")
    assert auditoria_service.listar()["total"] == 0


def test_registra_metadatos_por_defecto():
    auditoria_service.registrar(
        Evento.ESCENA, familia_id="f1", familia_nombre="Casa", detalle={"personaje_id": "t-rex"}
    )
    res = auditoria_service.listar()
    assert res["total"] == 1
    assert res["eventos"][0]["tipo"] == "escena"
    assert "t-rex" in res["eventos"][0]["detalle"]


# --- Toggle CONTENIDO ---
def test_contenido_no_se_guarda_por_defecto():
    auditoria_service.registrar(Evento.PREGUNTA, contenido="P: hola\nR: qué tal")
    assert auditoria_service.listar()["eventos"][0]["contenido"] is None


def test_contenido_se_guarda_si_activado():
    settings_service.set_many({"AUDITORIA_CONTENIDO": True})
    auditoria_service.registrar(Evento.PREGUNTA, contenido="P: hola\nR: qué tal")
    assert auditoria_service.listar()["eventos"][0]["contenido"] == "P: hola\nR: qué tal"


# --- Filtros / total ---
def test_filtro_por_tipo():
    auditoria_service.registrar(Evento.LOGIN, familia_id="f1")
    auditoria_service.registrar(Evento.PREGUNTA, familia_id="f1")
    assert auditoria_service.listar(tipo="login")["total"] == 1
    assert auditoria_service.listar()["total"] == 2


# --- CSV ---
def test_export_csv_incluye_filas():
    auditoria_service.registrar(Evento.LOGIN, familia_id="f1", familia_nombre="Casa")
    csv = auditoria_service.exportar_csv()
    assert "creado_en,tipo" in csv.splitlines()[0]
    assert "login" in csv


# --- Retención ---
def test_purga_borra_los_antiguos():
    auditoria_service.registrar(Evento.LOGIN, familia_id="f1")
    with db.get_session() as sesion:
        id_fila = sesion.exec(select(Auditoria)).first().id
    _envejecer(id_fila, 200)  # retención por defecto = 90 días
    assert auditoria_service.purgar_antiguos() == 1
    assert auditoria_service.listar()["total"] == 0


# --- RGPD: borrado por familia ---
def test_eliminar_familia_purga_solo_esa():
    auditoria_service.registrar(Evento.LOGIN, familia_id="f1")
    auditoria_service.registrar(Evento.LOGIN, familia_id="f2")
    assert auditoria_service.eliminar_familia("f1") == 1
    quedan = auditoria_service.listar()["eventos"]
    assert len(quedan) == 1
    assert quedan[0]["familia_id"] == "f2"


def test_supresion_cuenta_purga_su_auditoria():
    auditoria_service.registrar(Evento.LOGIN, familia_id="f1")
    familias_service.eliminar("f1")  # supresión RGPD (aunque la familia no exista ya)
    assert auditoria_service.listar()["total"] == 0


# --- Endpoints (admin) ---
def test_endpoint_lista_y_export(monkeypatch):
    app.dependency_overrides[admin_service.requiere_admin] = lambda: None
    try:
        auditoria_service.registrar(Evento.LOGIN, familia_id="f1", familia_nombre="Casa")
        r = _CLIENTE.get("/api/auditoria")
        assert r.status_code == 200
        assert r.json()["total"] == 1
        exp = _CLIENTE.get("/api/auditoria/export")
        assert exp.status_code == 200
        assert exp.headers["content-type"].startswith("text/csv")
        assert "login" in exp.text
    finally:
        app.dependency_overrides.pop(admin_service.requiere_admin, None)
