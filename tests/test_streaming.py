"""Tests del streaming de texto (Hito 8): llm_service + rag_service.

Cubren que `completar_streaming` cede los trozos del proveedor (Replicate/openai) y
que `rag_service.responder_streaming` emite primero un evento 'meta' y luego un
'token' por cada trozo. Nada llama a un LLM real: se mockean el cliente/proveedor.
El endpoint JSON (`completar`/`responder`) no se toca aquí (sus tests siguen).
"""

import pytest

from backend.services import llm_service, rag_service

_LLM_DEFAULTS = {
    "LLM_PROVIDER": "replicate",
    "LLM_MODEL": "meta/meta-llama-3-8b-instruct",
    "LLM_MAX_TOKENS": 300,
    "LLM_TEMPERATURE": 0.3,
}


@pytest.fixture
def fake_llm_settings(monkeypatch):
    valores = dict(_LLM_DEFAULTS)
    monkeypatch.setattr(llm_service.settings_service, "get", lambda k: valores.get(k))
    return valores


def test_completar_streaming_replicate_cede_los_trozos(fake_llm_settings, monkeypatch):
    fake_llm_settings["LLM_PROVIDER"] = "replicate"
    # replicate_client.run devuelve un iterador de trozos: lo simulamos.
    monkeypatch.setattr(
        llm_service.replicate_client, "run", lambda *a, **k: iter(["Hola", " ", "mundo"])
    )
    assert list(llm_service.completar_streaming("sys", "usr")) == ["Hola", " ", "mundo"]


def test_completar_streaming_openai_cede_los_deltas(fake_llm_settings, monkeypatch):
    fake_llm_settings["LLM_PROVIDER"] = "openai"

    class _Delta:
        def __init__(self, content):
            self.content = content

    class _Choice:
        def __init__(self, content):
            self.delta = _Delta(content)

    class _Evento:
        def __init__(self, content):
            self.choices = [_Choice(content)]

    class _ClienteOpenAI:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(model, messages, max_tokens, temperature, stream):
                    assert stream is True
                    # Un delta vacío por medio: se debe filtrar.
                    return iter([_Evento("Ho"), _Evento("la"), _Evento(None), _Evento("!")])

    monkeypatch.setattr(llm_service, "_cliente_openai", lambda: _ClienteOpenAI())
    assert list(llm_service.completar_streaming("sys", "usr")) == ["Ho", "la", "!"]


def test_responder_streaming_emite_meta_y_luego_tokens(monkeypatch):
    """Camino RAG: primero un evento 'meta' con fuentes, luego un 'token' por trozo."""
    prep = {
        "personaje_id": "t-rex",
        "pregunta": "hola",
        "nombre": "T-Rex",
        "origen": "RAG",
        "metodo": "rerank",
        "distancia": 0.4,
        "rerank_score": 1.2,
        "pregunta_traducida": "hello",
        "fuentes": ["[Dieta] come carne"],
        "system": "sys",
        "user": "usr",
        "etiqueta": "RAG",
        "respuesta_fija": None,
    }
    monkeypatch.setattr(rag_service, "_preparar", lambda pid, p: prep)
    monkeypatch.setattr(
        rag_service.llm_service,
        "completar_streaming",
        lambda *a, **k: iter(["Soy", " un", " T-Rex"]),
    )
    monkeypatch.setattr(rag_service, "_trazar_origen", lambda *a, **k: None)

    eventos = list(rag_service.responder_streaming("t-rex", "hola"))
    assert eventos[0]["tipo"] == "meta"
    assert eventos[0]["origen"] == "RAG"
    assert eventos[0]["fuentes"] == ["[Dieta] come carne"]
    tokens = [e["texto"] for e in eventos[1:] if e["tipo"] == "token"]
    assert tokens == ["Soy", " un", " T-Rex"]


def test_responder_streaming_sin_info_un_solo_token_sin_llm(monkeypatch):
    """SIN_INFO: texto fijo como único token, sin llamar al LLM de streaming."""
    prep = {
        "personaje_id": "t-rex",
        "pregunta": "hola",
        "nombre": "T-Rex",
        "origen": "SIN_INFO",
        "metodo": "umbral",
        "distancia": 1.9,
        "rerank_score": None,
        "pregunta_traducida": "hello",
        "fuentes": [],
        "system": None,
        "user": None,
        "etiqueta": None,
        "respuesta_fija": "Uy, eso no lo sé todavía.",
    }
    monkeypatch.setattr(rag_service, "_preparar", lambda pid, p: prep)

    def _no_debe_llamarse(*a, **k):
        raise AssertionError("SIN_INFO no debe llamar al LLM de streaming")

    monkeypatch.setattr(rag_service.llm_service, "completar_streaming", _no_debe_llamarse)
    monkeypatch.setattr(rag_service, "_trazar_origen", lambda *a, **k: None)

    eventos = list(rag_service.responder_streaming("t-rex", "hola"))
    assert eventos[0]["tipo"] == "meta"
    tokens = [e for e in eventos if e["tipo"] == "token"]
    assert len(tokens) == 1
    assert tokens[0]["texto"] == "Uy, eso no lo sé todavía."
