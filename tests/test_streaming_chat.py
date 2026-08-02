"""Tests del streaming orquestado (Hito 8): frases, caché de audio, chat_service y SSE.

Verifican el troceado en frases, la caché de audio en disco, que `chat_service.
responder_streaming` intercala audio por frase, y que el endpoint SSE emite frames
`event:`/`data:`. Nada llama a ElevenLabs ni a un LLM real (todo mockeado).
"""

from backend.services import audio_cache, chat_service, rag_service


# ---------------------------------------------------------------------------
# dividir_frases (pura)
# ---------------------------------------------------------------------------
def test_dividir_frases_separa_completas_y_deja_el_resto():
    frases, resto = chat_service.dividir_frases("Hola mundo. ¿Qué tal? Bien")
    assert frases == ["Hola mundo.", "¿Qué tal?"]
    assert resto == " Bien"


def test_dividir_frases_sin_cierre_no_extrae_nada():
    frases, resto = chat_service.dividir_frases("Todavia no termino")
    assert frases == []
    assert resto == "Todavia no termino"


def test_dividir_frases_agrupa_puntos_suspensivos():
    frases, resto = chat_service.dividir_frases("Vaya... ")
    assert frases == ["Vaya..."]
    assert resto == " "


# ---------------------------------------------------------------------------
# audio_cache
# ---------------------------------------------------------------------------
def test_audio_cache_clave_es_estable_y_distingue():
    a = audio_cache.clave("voz1", "modelo", "hola")
    b = audio_cache.clave("voz1", "modelo", "hola")
    c = audio_cache.clave("voz2", "modelo", "hola")
    assert a == b
    assert a != c


def test_audio_cache_guardar_y_obtener(tmp_path, monkeypatch):
    monkeypatch.setattr(audio_cache, "_DIR", tmp_path)
    clave = audio_cache.clave("voz1", "modelo", "hola")
    assert audio_cache.obtener(clave) is None  # miss
    audio_cache.guardar(clave, b"MP3BYTES")
    assert audio_cache.obtener(clave) == b"MP3BYTES"  # hit


# ---------------------------------------------------------------------------
# chat_service.responder_streaming
# ---------------------------------------------------------------------------
def _stream_rag_falso():
    yield {"tipo": "meta", "origen": "RAG", "fuentes": ["[Dieta] carne"]}
    for t in ["Hola", " mundo.", " ¿Qué", " tal?", " Fin"]:
        yield {"tipo": "token", "texto": t}


def test_responder_streaming_intercala_audio_por_frase(monkeypatch):
    monkeypatch.setattr(rag_service, "responder_streaming", lambda pid, p: _stream_rag_falso())
    monkeypatch.setattr(chat_service, "_voz_id", lambda pid: "voz1")
    # El TTS falso devuelve la propia frase como "audio", para poder comprobarla.
    # (Recorta como el real, que hace texto.strip() por dentro.)
    monkeypatch.setattr(
        chat_service, "_sintetizar_cacheado", lambda voz, texto: f"AUDIO:{texto.strip()}"
    )

    eventos = list(chat_service.responder_streaming("t-rex", "hola"))
    tipos = [e["tipo"] for e in eventos]
    assert tipos[0] == "fuentes"
    assert tipos[-1] == "fin"

    audios = [e["audio_base64"] for e in eventos if e["tipo"] == "audio_chunk"]
    # Dos frases cerradas (.?) + el resto "Fin" al final = 3 audios.
    assert audios == ["AUDIO:Hola mundo.", "AUDIO:¿Qué tal?", "AUDIO:Fin"]

    fin = eventos[-1]
    assert fin["respuesta"] == "Hola mundo. ¿Qué tal? Fin"


def test_responder_streaming_sin_voz_no_emite_audio(monkeypatch):
    monkeypatch.setattr(rag_service, "responder_streaming", lambda pid, p: _stream_rag_falso())
    monkeypatch.setattr(chat_service, "_voz_id", lambda pid: None)  # personaje sin voz

    eventos = list(chat_service.responder_streaming("t-rex", "hola"))
    assert not any(e["tipo"] == "audio_chunk" for e in eventos)
    assert eventos[-1]["tipo"] == "fin"


# ---------------------------------------------------------------------------
# Endpoint SSE
# ---------------------------------------------------------------------------
def _client():
    from fastapi.testclient import TestClient

    from backend.main import app

    return TestClient(app)


def test_sse_endpoint_emite_frames(monkeypatch):
    def _fake_stream(personaje_id, pregunta):
        yield {"tipo": "fuentes", "fuentes": [], "origen": "RAG"}
        yield {"tipo": "token", "texto": "Hola"}
        yield {"tipo": "fin", "respuesta": "Hola"}

    monkeypatch.setattr(chat_service, "responder_streaming", _fake_stream)
    r = _client().post("/api/ask/stream", json={"personaje_id": "t-rex", "pregunta": "hola"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "event: token" in r.text
    assert "event: fin" in r.text


def test_sse_endpoint_error_emite_evento_error(monkeypatch):
    def _revienta(personaje_id, pregunta):
        raise ValueError("Personaje desconocido: 'nadie'.")
        yield  # pragma: no cover — hace de esto un generador

    monkeypatch.setattr(chat_service, "responder_streaming", _revienta)
    r = _client().post("/api/ask/stream", json={"personaje_id": "nadie", "pregunta": "hola"})
    assert r.status_code == 200  # el error viaja como evento SSE, no como código HTTP
    assert "event: error" in r.text
    assert "Personaje desconocido" in r.text
