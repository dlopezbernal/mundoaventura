"""Tests de la capa de proveedor de STT (Hito 7).

Verifican el DESPACHO por `STT_PROVIDER` y, sobre todo, el **fallback automático**:
si el STT local no carga (paquete/DLLs ausentes) o falla, la app cae a la nube y no
se queda muda. Nada aquí carga faster-whisper de verdad ni llama a la red: se mockean
el modelo local, el cliente de Groq y el cliente de ElevenLabs.
"""

import sys
import types

import pytest

from backend import config
from backend.services import stt_service

# Valores por defecto que devuelve el settings_service falso (los que lee stt_service).
_DEFAULTS = {
    "STT_PROVIDER": "elevenlabs",
    "STT_LANG": "es",
    "STT_LOCAL_MODEL": "large-v3-turbo",
    "STT_LOCAL_DEVICE": "cuda",
    "STT_LOCAL_COMPUTE": "int8",
    "ELEVENLABS_STT_MODEL": "scribe_v1",
    "GROQ_STT_MODEL": "whisper-large-v3",
    "DEBUG": False,
}


@pytest.fixture
def fake_settings(monkeypatch):
    """Sustituye settings_service.get por un diccionario controlable desde el test."""
    valores = dict(_DEFAULTS)
    monkeypatch.setattr(stt_service.settings_service, "get", lambda k: valores.get(k))
    stt_service.reiniciar()  # empieza sin singletons cacheados
    yield valores
    stt_service.reiniciar()


class _Segmento:
    def __init__(self, text):
        self.text = text


class _ModeloLocalFalso:
    """Imita faster_whisper.WhisperModel: transcribe() devuelve (segmentos, info)."""

    def transcribe(self, audio, language=None):
        return (iter([_Segmento(" hola"), _Segmento(" mundo")]), {"language": language})


def test_provider_por_defecto_es_elevenlabs(fake_settings):
    fake_settings["STT_PROVIDER"] = "loquesea-raro"
    assert stt_service._provider() == "elevenlabs"


def test_dispatch_local_usa_faster_whisper(fake_settings, monkeypatch):
    fake_settings["STT_PROVIDER"] = "local"
    monkeypatch.setattr(stt_service, "_cargar_modelo_local", lambda: _ModeloLocalFalso())
    assert stt_service.transcribir(b"audio") == "hola mundo"


def test_local_que_falla_cae_a_elevenlabs(fake_settings, monkeypatch, caplog):
    """Si el modelo local no carga (ImportError, DLLs…), se avisa y se usa la nube."""
    fake_settings["STT_PROVIDER"] = "local"

    def _revienta():
        raise ImportError("faster_whisper no instalado")

    monkeypatch.setattr(stt_service, "_cargar_modelo_local", _revienta)
    monkeypatch.setattr(stt_service, "_transcribir_elevenlabs", lambda b: "(desde la nube)")
    with caplog.at_level("WARNING"):
        assert stt_service.transcribir(b"audio") == "(desde la nube)"
    assert any("local" in r.message.lower() for r in caplog.records)


def test_dispatch_groq(fake_settings, monkeypatch):
    fake_settings["STT_PROVIDER"] = "groq"

    class _Resp:
        text = "  transcrito por groq  "

    class _ClienteGroq:
        class audio:  # noqa: N801 — imita el namespace del SDK openai
            class transcriptions:
                @staticmethod
                def create(model, file, language):
                    return _Resp()

    monkeypatch.setattr(stt_service, "_cliente_openai_groq", lambda: _ClienteGroq())
    assert stt_service.transcribir(b"audio") == "transcrito por groq"


def test_groq_sin_clave_lanza_stterror(fake_settings, monkeypatch):
    fake_settings["STT_PROVIDER"] = "groq"
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    with pytest.raises(stt_service.STTError):
        stt_service.transcribir(b"audio")


def test_elevenlabs_delega_en_cliente_de_voice_service(fake_settings, monkeypatch):
    fake_settings["STT_PROVIDER"] = "elevenlabs"

    class _Resultado:
        text = " hola desde scribe "

    class _ClienteEleven:
        class speech_to_text:  # noqa: N801
            @staticmethod
            def convert(file, model_id, language_code):
                return _Resultado()

    from backend.services import voice_service

    monkeypatch.setattr(voice_service, "_get_client", lambda: _ClienteEleven())
    # resiliencia.reintentar solo ejecuta el lambda una vez si no hay error.
    assert stt_service.transcribir(b"audio") == "hola desde scribe"


def test_modelo_local_se_reconstruye_si_cambia_la_firma(fake_settings, monkeypatch):
    """El modelo local se cachea, pero se RECONSTRUYE si cambia modelo/device/compute."""
    instancias = {"n": 0}

    class _WhisperModel:
        def __init__(self, modelo, device, compute_type):
            instancias["n"] += 1

    modulo_falso = types.ModuleType("faster_whisper")
    modulo_falso.WhisperModel = _WhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", modulo_falso)

    stt_service._cargar_modelo_local()
    stt_service._cargar_modelo_local()  # misma firma → NO reconstruye
    assert instancias["n"] == 1

    fake_settings["STT_LOCAL_MODEL"] = "small"  # cambia la firma
    stt_service._cargar_modelo_local()
    assert instancias["n"] == 2


def test_reiniciar_limpia_singletons(fake_settings, monkeypatch):
    monkeypatch.setattr(stt_service, "_modelo_local", object())
    monkeypatch.setattr(stt_service, "_cliente_groq", object())
    stt_service.reiniciar()
    assert stt_service._modelo_local is None
    assert stt_service._cliente_groq is None


def test_info_describe_el_proveedor_vigente(fake_settings):
    fake_settings["STT_PROVIDER"] = "local"
    assert stt_service.info() == {"provider": "local", "model": "large-v3-turbo"}
    fake_settings["STT_PROVIDER"] = "groq"
    assert stt_service.info() == {"provider": "groq", "model": "whisper-large-v3"}
