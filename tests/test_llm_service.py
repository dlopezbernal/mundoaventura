"""Tests de la capa de proveedor de LLM (Hito 5).

Dos bloques:

1) FIJACIÓN (escrito ANTES del refactor): pincha la forma EXACTA de la llamada a
   Replicate que hace el sistema hoy. Es la red de seguridad de equivalencia: tras
   introducir `llm_service`, esta llamada debe seguir siendo byte a byte la misma
   (mismo modelo, mismo `input` dict, mismo texto de salida). Prueba que el refactor
   NO cambió el comportamiento con Replicate, SIN gastar API.

2) DISPATCH: que `llm_service.completar` enruta al proveedor correcto según
   LLM_PROVIDER (replicate legacy vs openai-compatible) construyendo la petición
   propia de cada dialecto.
"""

import pytest

from backend.services import settings_service


def _stub_settings(valores: dict):
    """Devuelve un get(clave) que usa `valores` y cae al real para el resto."""
    real = settings_service.get

    def _get(clave):
        return valores.get(clave, real(clave))

    return _get


# ---------------------------------------------------------------------------
# 1) FIJACIÓN: el contrato actual con Replicate (vía rag_service._llamar_llm)
# ---------------------------------------------------------------------------
def test_fijacion_llamada_replicate(monkeypatch):
    """La llamada a Replicate usa el modelo y el input dict EXACTOS de la baseline."""
    from backend.services import rag_service

    capturado = {}

    def _fake_run(modelo, *, input, etiqueta="Replicate"):  # noqa: A002
        capturado["modelo"] = modelo
        capturado["input"] = input
        capturado["etiqueta"] = etiqueta
        return ["Hola ", "soy ", "el T-Rex."]  # iterable de trocitos (streaming)

    # El LLM vive detrás de replicate_client.run; lo interceptamos ahí.
    monkeypatch.setattr("backend.services.replicate_client.run", _fake_run)
    monkeypatch.setattr(
        settings_service,
        "get",
        _stub_settings(
            {
                "LLM_PROVIDER": "replicate",
                "REPLICATE_LLM_MODEL": "meta/meta-llama-3-8b-instruct",
                "LLM_MODEL": "meta/meta-llama-3-8b-instruct",
                "LLM_MAX_TOKENS": 300,
                "LLM_TEMPERATURE": 0.3,
            }
        ),
    )

    salida = rag_service._llamar_llm("SYSTEM_PROMPT", "USER_PROMPT", etiqueta="RAG")

    # El texto se une y se recorta, tal cual hoy.
    assert salida == "Hola soy el T-Rex."
    # Modelo posicional = el configurado.
    assert capturado["modelo"] == "meta/meta-llama-3-8b-instruct"
    # Input dict EXACTO (claves y valores) del dialecto Replicate.
    assert capturado["input"] == {
        "prompt": "USER_PROMPT",
        "system_prompt": "SYSTEM_PROMPT",
        "max_tokens": 300,
        "temperature": 0.3,
    }


def test_fijacion_evaluator_pasa_temperatura_y_tokens_explicitos(monkeypatch):
    """El juez del Evaluator fuerza max_tokens=5 y temperature=0.0 (determinista)."""
    from backend.services import rag_service

    capturado = {}

    def _fake_run(modelo, *, input, etiqueta="Replicate"):  # noqa: A002
        capturado["input"] = input
        return ["YES"]

    monkeypatch.setattr("backend.services.replicate_client.run", _fake_run)
    monkeypatch.setattr(
        settings_service,
        "get",
        _stub_settings(
            {
                "LLM_PROVIDER": "replicate",
                "REPLICATE_LLM_MODEL": "meta/meta-llama-3-8b-instruct",
                "LLM_MODEL": "meta/meta-llama-3-8b-instruct",
                "LLM_MAX_TOKENS": 300,
                "LLM_TEMPERATURE": 0.3,
            }
        ),
    )

    rag_service._llamar_llm("S", "U", max_tokens=5, temperature=0.0, etiqueta="Evaluator")

    assert capturado["input"]["max_tokens"] == 5
    assert capturado["input"]["temperature"] == 0.0


# ---------------------------------------------------------------------------
# 2) DISPATCH: llm_service enruta por LLM_PROVIDER
# ---------------------------------------------------------------------------
def test_completar_provider_replicate_usa_dialecto_replicate(monkeypatch):
    """provider=replicate → replicate_client.run con el input dict de Replicate."""
    from backend.services import llm_service

    capturado = {}

    def _fake_run(modelo, *, input, etiqueta="Replicate"):  # noqa: A002
        capturado["modelo"] = modelo
        capturado["input"] = input
        return ["ok"]

    monkeypatch.setattr("backend.services.replicate_client.run", _fake_run)
    monkeypatch.setattr(
        settings_service,
        "get",
        _stub_settings(
            {
                "LLM_PROVIDER": "replicate",
                "LLM_MODEL": "meta/meta-llama-3-8b-instruct",
                "LLM_MAX_TOKENS": 300,
                "LLM_TEMPERATURE": 0.3,
            }
        ),
    )

    salida = llm_service.completar("S", "U", etiqueta="RAG")

    assert salida == "ok"
    assert capturado["modelo"] == "meta/meta-llama-3-8b-instruct"
    assert capturado["input"] == {
        "prompt": "U",
        "system_prompt": "S",
        "max_tokens": 300,
        "temperature": 0.3,
    }


def test_completar_provider_openai_usa_chat_completions(monkeypatch):
    """provider=openai → SDK openai (base_url configurable), mensajes system+user."""
    from backend.services import llm_service

    capturado = {}

    class _FakeMessage:
        content = "respuesta openai"

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeResp:
        choices = [_FakeChoice()]

    class _FakeCompletions:
        def create(self, **kwargs):
            capturado.update(kwargs)
            return _FakeResp()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    # llm_service crea el cliente openai por dentro; interceptamos su fábrica.
    monkeypatch.setattr(llm_service, "_cliente_openai", lambda: _FakeClient())
    monkeypatch.setattr(
        settings_service,
        "get",
        _stub_settings(
            {
                "LLM_PROVIDER": "openai",
                "LLM_MODEL": "llama3",
                "LLM_MAX_TOKENS": 300,
                "LLM_TEMPERATURE": 0.3,
            }
        ),
    )

    salida = llm_service.completar("S", "U", etiqueta="RAG")

    assert salida == "respuesta openai"
    assert capturado["model"] == "llama3"
    assert capturado["max_tokens"] == 300
    assert capturado["temperature"] == 0.3
    assert capturado["messages"] == [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
    ]


def test_info_no_expone_la_clave(monkeypatch):
    """info() describe proveedor/modelo/base_url pero NUNCA la clave."""
    from backend.services import llm_service

    monkeypatch.setattr(
        settings_service,
        "get",
        _stub_settings(
            {
                "LLM_PROVIDER": "openai",
                "LLM_MODEL": "llama3",
                "LLM_BASE_URL": "http://localhost:11434/v1",
            }
        ),
    )
    info = llm_service.info()
    assert info["provider"] == "openai"
    assert info["model"] == "llama3"
    assert info["base_url"] == "http://localhost:11434/v1"
    assert not any("key" in k.lower() or "token" in k.lower() for k in info)


@pytest.mark.parametrize("provider", ["replicate", "openai"])
def test_completar_streaming_existe(provider):
    """El esqueleto de streaming existe (lo consumirá H8) para ambos proveedores."""
    from backend.services import llm_service

    assert hasattr(llm_service, "completar_streaming")
