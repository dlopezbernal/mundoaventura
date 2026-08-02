"""Tests del cliente único de ChromaDB (Hito 5).

No tocan disco: monkeypatchean `chromadb.PersistentClient` por un doble que cuenta
cuántas veces se construye. Fijan el invariante del gate: UN SOLO cliente en todo
el backend, compartido por el chat (rag_service) y la ingesta (documentos_service).
"""

import chromadb
import pytest

from backend.services import documentos_service, embeddings, rag_service, vector_store


@pytest.fixture(autouse=True)
def _reset_cliente():
    """Deja el cliente único a None antes y después: el _FakeClient de un test NO
    debe filtrarse al resto de la suite (que usa el ChromaDB real)."""
    vector_store.reiniciar()
    yield
    vector_store.reiniciar()


class _FakeCollection:
    def count(self):
        return 5  # no vacía (evita el warning de colección vacía)


class _FakeClient:
    """Cuenta construcciones y recuerda con qué nombre se pidió la colección."""

    instancias = 0

    def __init__(self, *args, **kwargs):
        _FakeClient.instancias += 1
        self.ultimo_nombre = None

    def get_or_create_collection(self, name, metadata=None):
        self.ultimo_nombre = name
        return _FakeCollection()


def _instalar(monkeypatch):
    _FakeClient.instancias = 0
    vector_store.reiniciar()  # olvida cualquier cliente previo
    monkeypatch.setattr(chromadb, "PersistentClient", _FakeClient)


def test_cliente_es_singleton(monkeypatch):
    _instalar(monkeypatch)
    c1 = vector_store.cliente()
    c2 = vector_store.cliente()
    assert c1 is c2
    assert _FakeClient.instancias == 1  # se construyó UNA sola vez


def test_reiniciar_fuerza_recrear(monkeypatch):
    _instalar(monkeypatch)
    vector_store.cliente()
    vector_store.reiniciar()
    vector_store.cliente()
    assert _FakeClient.instancias == 2


def test_chat_e_ingesta_comparten_el_mismo_cliente(monkeypatch):
    """rag_service y documentos_service pasan por el MISMO cliente único."""
    _instalar(monkeypatch)
    rag_service._get_collection()
    documentos_service._get_collection()
    # Un solo PersistentClient para ambos servicios (el gate de H5).
    assert _FakeClient.instancias == 1


def test_coleccion_por_defecto_usa_el_backend_vigente(monkeypatch):
    _instalar(monkeypatch)
    monkeypatch.setattr(embeddings, "coleccion_actual", lambda: "documentos_test")
    cliente = vector_store.cliente()
    vector_store.coleccion()
    assert cliente.ultimo_nombre == "documentos_test"
