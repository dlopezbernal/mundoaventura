"""Tests del reranker (Hito 4.3): reordenado + decisión por puntuación.

No cargan el modelo ONNX ni tocan la red: monkeypatchean `reranker.rerank` y la
colección de ChromaDB para probar la LÓGICA (embudo, reorden, truncado, umbral).
"""

from backend.services import embeddings, rag_service, reranker, settings_service


def _stub_settings(valores: dict):
    """Devuelve un get(clave) que usa `valores` y cae al real para el resto."""
    real = settings_service.get

    def _get(clave):
        return valores.get(clave, real(clave))

    return _get


class _FakeCollection:
    """Colección mínima: devuelve SIEMPRE lo mismo, en un orden fijo, para query()."""

    def __init__(self, docs, dists, metas):
        self._docs, self._dists, self._metas = docs, dists, metas

    def query(self, **_kwargs):
        return {
            "documents": [self._docs],
            "distances": [self._dists],
            "metadatas": [self._metas],
        }

    def count(self):
        return len(self._docs)


# ---------------------------------------------------------------------------
# reranker.py
# ---------------------------------------------------------------------------
def test_reranker_actual_cae_a_off_si_valor_raro(monkeypatch):
    monkeypatch.setattr(settings_service, "get", _stub_settings({"RERANKER": "no-existe"}))
    assert reranker.reranker_actual() == "off"
    assert reranker.activo() is False


def test_reranker_activo_refleja_el_ajuste(monkeypatch):
    monkeypatch.setattr(settings_service, "get", _stub_settings({"RERANKER": "jina-v2"}))
    assert reranker.reranker_actual() == "jina-v2"
    assert reranker.activo() is True


def test_rerank_lista_vacia_no_carga_modelo(monkeypatch):
    # Sin documentos no debe intentar cargar el ONNX (devuelve [] antes).
    monkeypatch.setattr(settings_service, "get", _stub_settings({"RERANKER": "jina-v2"}))
    assert reranker.rerank("pregunta", []) == []


# ---------------------------------------------------------------------------
# _recuperar_contexto: embudo (recuperar ancho → reordenar → top_k)
# ---------------------------------------------------------------------------
def test_recuperar_reordena_por_score_y_trunca(monkeypatch):
    # 4 candidatos recuperados en un orden; el reranker los reordena por relevancia.
    docs = ["c0", "c1", "c2", "c3"]
    dists = [0.5, 0.6, 0.7, 0.8]
    metas = [{"source": s} for s in ("f0", "f1", "f2", "f3")]
    monkeypatch.setattr(rag_service, "_get_collection", lambda: _FakeCollection(docs, dists, metas))
    monkeypatch.setattr(embeddings, "usa_manuales", lambda: False)
    monkeypatch.setattr(reranker, "activo", lambda: True)
    # Puntuaciones que invierten el orden: el mejor es c3, luego c1.
    monkeypatch.setattr(reranker, "rerank", lambda q, d: [0.1, 0.9, 0.2, 1.5])
    monkeypatch.setattr(
        settings_service, "get", _stub_settings({"RAG_TOP_K": 2, "RERANK_CANDIDATOS": 4})
    )

    ctx, dd, mm, scores = rag_service._recuperar_contexto("p", "pregunta")

    assert ctx == ["c3", "c1"]  # reordenado por score desc, truncado a top_k=2
    assert dd == [0.8, 0.6]  # distancias reordenadas EN PARALELO con sus docs
    assert [m["source"] for m in mm] == ["f3", "f1"]
    assert scores == [1.5, 0.9]


def test_recuperar_sin_reranker_no_devuelve_scores(monkeypatch):
    docs, dists, metas = ["c0", "c1"], [0.5, 0.6], [{"source": "f0"}, {"source": "f1"}]
    monkeypatch.setattr(rag_service, "_get_collection", lambda: _FakeCollection(docs, dists, metas))
    monkeypatch.setattr(embeddings, "usa_manuales", lambda: False)
    monkeypatch.setattr(reranker, "activo", lambda: False)
    monkeypatch.setattr(settings_service, "get", _stub_settings({"RAG_TOP_K": 3}))

    ctx, dd, mm, scores = rag_service._recuperar_contexto("p", "pregunta")

    assert ctx == ["c0", "c1"]  # tal cual llega de Chroma (ya ordenado por distancia)
    assert scores is None


# ---------------------------------------------------------------------------
# _decidir_origen: con reranker decide la puntuación (umbral), sin LLM-juez
# ---------------------------------------------------------------------------
def test_decidir_con_reranker_por_encima_del_umbral_es_rag(monkeypatch):
    monkeypatch.setattr(settings_service, "get", _stub_settings({"RERANK_UMBRAL": 0.0}))
    es_rag, metodo, dist, score = rag_service._decidir_origen(
        ["c0", "c1"], [0.7, 0.9], [1.4, -2.0], "q"
    )
    assert es_rag is True
    assert metodo == "rerank"
    assert score == 1.4  # el mejor score
    assert dist == 0.7  # la mejor distancia coseno, informativa


def test_decidir_con_reranker_por_debajo_del_umbral_no_es_rag(monkeypatch):
    monkeypatch.setattr(settings_service, "get", _stub_settings({"RERANK_UMBRAL": 0.0}))
    es_rag, metodo, _dist, score = rag_service._decidir_origen(["c0"], [0.9], [-1.5], "q")
    assert es_rag is False
    assert metodo == "rerank"
    assert score == -1.5


def test_decidir_sin_scores_usa_camino_coseno(monkeypatch):
    # scores=None → NO es camino reranker; cae al umbral coseno de siempre.
    monkeypatch.setattr(
        settings_service,
        "get",
        _stub_settings(
            {
                "EVALUATOR_MODE": "umbral",
                "EVALUATOR_UMBRAL_BAJO": 0.8,
                "EVALUATOR_UMBRAL_ALTO": 0.95,
            }
        ),
    )
    es_rag, metodo, _dist, score = rag_service._decidir_origen(["c0"], [0.5], None, "q")
    assert es_rag is True
    assert metodo == "umbral"
    assert score is None
