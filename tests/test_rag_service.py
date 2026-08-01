"""Tests de `_clasificar_umbral` (rag_service): el árbitro gratis del Evaluator.

Clasifica una distancia coseno en 'relevante' / 'dudoso' / 'irrelevante' según los
umbrales BAJO/ALTO. Se monkeypatchean los umbrales para no depender de la BBDD y
fijar los bordes exactos (<= BAJO y >= ALTO).
"""

import pytest

from backend.services import rag_service

_UMBRALES = {"EVALUATOR_UMBRAL_BAJO": 0.75, "EVALUATOR_UMBRAL_ALTO": 0.95}


@pytest.fixture(autouse=True)
def _umbrales_fijos(monkeypatch):
    monkeypatch.setattr(rag_service.settings_service, "get", lambda clave: _UMBRALES[clave])


@pytest.mark.parametrize("distancia", [0.0, 0.5, 0.75])
def test_por_debajo_o_en_el_umbral_bajo_es_relevante(distancia):
    assert rag_service._clasificar_umbral(distancia) == "relevante"


@pytest.mark.parametrize("distancia", [0.76, 0.85, 0.94])
def test_entre_los_umbrales_es_dudoso(distancia):
    assert rag_service._clasificar_umbral(distancia) == "dudoso"


@pytest.mark.parametrize("distancia", [0.95, 1.2, 2.0])
def test_en_o_por_encima_del_umbral_alto_es_irrelevante(distancia):
    assert rag_service._clasificar_umbral(distancia) == "irrelevante"
