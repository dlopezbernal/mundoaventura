"""Tests de cuota_service — tope diario de imágenes en SQLite (H2, tarea 5).

Usan una BBDD SQLite temporal (tmp_path) para no tocar la real: se apunta
config.CONFIG_DB_PATH al temporal y se resetea el engine cacheado de db.
"""

import pytest

from backend import config, db
from backend.services import cuota_service


@pytest.fixture
def _db_temp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "cuota_test.sqlite3")
    monkeypatch.setattr(db, "_engine", None)  # fuerza recrear el engine en el temporal
    yield
    monkeypatch.setattr(db, "_engine", None)  # y recrear contra la real tras el test


def test_cupo_desactivado_siempre_hay(_db_temp, monkeypatch):
    monkeypatch.setattr(config, "MAX_IMAGENES_DIA", 0)  # <= 0 = sin tope
    assert cuota_service.hay_cupo() is True
    cuota_service.registrar()
    assert cuota_service.hay_cupo() is True


def test_cuenta_hasta_el_tope_y_se_agota(_db_temp, monkeypatch):
    monkeypatch.setattr(config, "MAX_IMAGENES_DIA", 3)
    for _ in range(3):
        assert cuota_service.hay_cupo() is True
        cuota_service.registrar()
    # Consumidas las 3 → ya no queda cupo hoy.
    assert cuota_service.hay_cupo() is False
    assert cuota_service.estado()["imagenes_hoy"] == 3


def test_registrar_incrementa_el_contador(_db_temp, monkeypatch):
    monkeypatch.setattr(config, "MAX_IMAGENES_DIA", 100)
    assert cuota_service.estado()["imagenes_hoy"] == 0
    cuota_service.registrar()
    cuota_service.registrar()
    assert cuota_service.estado()["imagenes_hoy"] == 2
