"""Tests de blindaje de la ENTRADA (H2, tareas 3 y 4).

- Límite de tamaño de las subidas: `leer_con_limite` corta con 413 tanto por el
  tamaño ya conocido (`size`) como leyendo por trozos si `size` no viene.
- Validación de longitud: una `pregunta` demasiado larga a /api/ask → 422 (la
  rechaza Pydantic antes de tocar ningún servicio ni la red).
"""

import asyncio
import io

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from backend.routers.limites import leer_con_limite


def _upload(data: bytes, *, size: int | None) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="x.bin", size=size)


def test_subida_bajo_limite_devuelve_los_bytes():
    data = b"a" * 1000
    up = _upload(data, size=len(data))
    assert asyncio.run(leer_con_limite(up, max_mb=1, etiqueta="documento")) == data


def test_subida_sobre_limite_413_por_size():
    # 2 MB con size conocido → rechazo rápido sin leer a memoria.
    data = b"a" * (2 * 1024 * 1024)
    up = _upload(data, size=len(data))
    with pytest.raises(HTTPException) as info:
        asyncio.run(leer_con_limite(up, max_mb=1, etiqueta="documento"))
    assert info.value.status_code == 413


def test_subida_sobre_limite_413_por_trozos_si_size_none():
    # size=None fuerza el camino de lectura por trozos, que también debe cortar.
    data = b"a" * (2 * 1024 * 1024)
    up = _upload(data, size=None)
    with pytest.raises(HTTPException) as info:
        asyncio.run(leer_con_limite(up, max_mb=1, etiqueta="documento"))
    assert info.value.status_code == 413


def test_pregunta_demasiado_larga_es_422():
    # TestClient SIN context manager: no dispara el lifespan (ni red ni seeding).
    # El 422 lo produce la validación de Pydantic antes de llegar al servicio.
    from backend.main import app

    cliente = TestClient(app)
    r = cliente.post("/api/ask", json={"personaje_id": "t-rex", "pregunta": "x" * 1000})
    assert r.status_code == 422


def test_pregunta_vacia_es_422():
    from backend.main import app

    cliente = TestClient(app)
    r = cliente.post("/api/ask", json={"personaje_id": "t-rex", "pregunta": ""})
    assert r.status_code == 422
