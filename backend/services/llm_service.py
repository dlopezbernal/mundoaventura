"""
services/llm_service.py — Capa de proveedor de LLM (Hito 5)
==========================================================

Un ÚNICO punto por el que pasan TODAS las llamadas al modelo de lenguaje, para
poder cambiar de proveedor tocando CONFIGURACIÓN, no código. Es el habilitador de
H6 (comparar cinco LLMs sin reescribir nada).

Dos dialectos detrás de la misma interfaz (`LLM_PROVIDER`):

  - `replicate` (por defecto, LEGACY): el camino de la línea base. Envuelve
    `replicate_client.run` con el MISMO `input` dict de siempre
    (`{prompt, system_prompt, max_tokens, temperature}`). Reproduce el baseline
    byte a byte (ver el test de fijación en tests/test_llm_service.py).
  - `openai`: el SDK `openai` con `base_url` configurable. Ese protocolo lo hablan
    Groq, Mistral, Gemini (endpoint compatible), OpenRouter, Together, Cerebras y
    **Ollama local** — un solo camino de código, N proveedores.

Interfaz pública:
  completar(system, user, max_tokens=None, temperature=None, etiqueta="LLM") -> str
  completar_streaming(...) -> Iterator[str]   # esqueleto; lo consumirá H8
  info() -> dict   # proveedor, modelo, base_url (NUNCA la clave)

El modelo, el proveedor y la base_url son ajustes en caliente (`settings_service`);
la clave del endpoint openai-compatible es un secreto (`config.LLM_API_KEY`, .env).
"""

import logging
from collections.abc import Iterator

from backend import config, debug_log
from backend.services import replicate_client, settings_service

logger = logging.getLogger(__name__)

_PROVEEDORES_VALIDOS = ("replicate", "openai")

# Cliente openai-compatible, creado una sola vez (singleton perezoso). Se recrea con
# reiniciar() cuando cambia la clave (pantalla de APIs) o la base_url.
_openai_client = None


def _provider() -> str:
    """Proveedor vigente (cae a 'replicate' si el ajuste trae algo raro)."""
    p = settings_service.get("LLM_PROVIDER")
    return p if p in _PROVEEDORES_VALIDOS else "replicate"


def _modelo() -> str:
    return settings_service.get("LLM_MODEL")


def _resolver_generacion(max_tokens: int | None, temperature: float | None) -> tuple[int, float]:
    """Rellena max_tokens/temperature con los ajustes vigentes si vienen en None.

    Mismo criterio que el `_llamar_llm` original: `temperature is None` → el ajuste
    LLM_TEMPERATURE (el juez del Evaluator pasa 0.0 explícito y NO cae aquí);
    `max_tokens` vacío → LLM_MAX_TOKENS.
    """
    if temperature is None:
        temperature = settings_service.get("LLM_TEMPERATURE")
    if not max_tokens:
        max_tokens = settings_service.get("LLM_MAX_TOKENS")
    return max_tokens, temperature


def completar(
    system: str,
    user: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
    etiqueta: str = "LLM",
) -> str:
    """Genera una respuesta del LLM y devuelve el texto (proveedor según config)."""
    max_tokens, temperature = _resolver_generacion(max_tokens, temperature)
    if _provider() == "openai":
        return _completar_openai(system, user, max_tokens, temperature, etiqueta)
    return _completar_replicate(system, user, max_tokens, temperature, etiqueta)


def _completar_replicate(
    system: str, user: str, max_tokens: int, temperature: float, etiqueta: str
) -> str:
    """Dialecto Replicate (LEGACY): el `input` dict EXACTO de la línea base."""
    modelo = _modelo()
    debug_log.trazar_prompt(f"Replicate · {etiqueta} ({modelo})", system=system, user=user)
    salida = replicate_client.run(
        modelo,
        input={
            "prompt": user,
            "system_prompt": system,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        etiqueta=f"Replicate · {etiqueta}",
    )
    # Replicate devuelve la respuesta "en trocitos" (streaming): los unimos.
    return "".join(salida).strip()


def _cliente_openai():
    """Cliente openai-compatible (singleton perezoso). base_url + clave configurables."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        base_url = settings_service.get("LLM_BASE_URL") or None
        # Muchos endpoints locales (Ollama) no exigen clave; el SDK sí requiere un
        # valor no vacío, así que ponemos un marcador si no hay clave configurada.
        _openai_client = OpenAI(
            base_url=base_url,
            api_key=config.LLM_API_KEY or "sk-no-key",
            timeout=config.LLM_TIMEOUT,
            max_retries=max(config.HTTP_MAX_INTENTOS - 1, 0),
        )
    return _openai_client


def _completar_openai(
    system: str, user: str, max_tokens: int, temperature: float, etiqueta: str
) -> str:
    """Dialecto OpenAI-compatible: chat.completions con mensajes system+user."""
    modelo = _modelo()
    debug_log.trazar_prompt(f"OpenAI-compat · {etiqueta} ({modelo})", system=system, user=user)
    resp = _cliente_openai().chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


def completar_streaming(
    system: str,
    user: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
    etiqueta: str = "LLM",
) -> Iterator[str]:
    """Genera la respuesta en trocitos (para H8, streaming al frontend).

    ESQUELETO por ahora: emite el texto completo como un único trozo, para que la
    interfaz exista sin cambiar el comportamiento. H8 la implementará de verdad
    (con `stream=True` en openai y el iterador nativo de Replicate).
    """
    yield completar(system, user, max_tokens, temperature, etiqueta)


def info() -> dict:
    """Describe el LLM vigente (proveedor/modelo/base_url). NUNCA incluye la clave."""
    return {
        "provider": _provider(),
        "model": _modelo(),
        "base_url": settings_service.get("LLM_BASE_URL"),
    }


def reiniciar() -> None:
    """Olvida el cliente openai cacheado (tras cambiar clave o base_url en caliente)."""
    global _openai_client
    _openai_client = None


def probar() -> dict:
    """Prueba ligera del endpoint openai-compatible (para la pantalla de APIs)."""
    if _provider() != "openai":
        return {"ok": True, "mensaje": "Proveedor Replicate (se prueba en su propia tarjeta)."}
    try:
        _cliente_openai().models.list()
        return {"ok": True, "mensaje": "Endpoint LLM conectado."}
    except Exception as exc:  # noqa: BLE001 — informe de estado, no propagamos
        return {"ok": False, "mensaje": f"No se pudo conectar con el endpoint LLM: {exc}"}
