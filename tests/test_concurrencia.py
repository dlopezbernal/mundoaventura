"""Test de aceptación de concurrencia (H2, tarea 1).

Verifica que `GET /health` responde en < 200 ms MIENTRAS hay 2 peticiones largas
a `/api/ask` en vuelo. Con los endpoints declarados `def`, FastAPI los ejecuta en
su threadpool y el event loop queda libre; si fueran `async def` con una llamada
bloqueante dentro, `/health` esperaría a que terminasen (ver el antes/después en
docs/mediciones/H2-concurrencia.md).

Aquí se usa el transporte ASGI in-process (rápido y determinista para CI): basta
para demostrar el offload al threadpool. La medición fiel entre procesos (uvicorn
real + cliente independiente) vive en scripts/bench_concurrencia.py.
"""

import asyncio
import time

import httpx

from backend.services import chat_service, translation_service, voice_service

_BLOQUEO_S = 1.0  # cada /api/ask "tarda" esto (simula I/O de red bloqueante)


def _stub_responder(personaje_id: str, pregunta: str) -> dict:
    time.sleep(_BLOQUEO_S)  # bloquea el hilo, como un SDK síncrono de red
    return {
        "success": True,
        "personaje_id": personaje_id,
        "pregunta": pregunta,
        "respuesta": "(simulada)",
        "origen": "RAG",
        "audio_base64": None,
    }


def test_health_responde_con_asks_en_vuelo(monkeypatch):
    # Stub del ORQUESTADOR del chat (bloqueo determinista, sin red) y de las sondas
    # de /health. Se stubea chat_service.responder porque es lo que llama el endpoint
    # /api/ask desde H5 (antes era rag_service.responder, ahora envuelto por el TTS).
    monkeypatch.setattr(chat_service, "responder", _stub_responder)
    monkeypatch.setattr(
        translation_service, "estado", lambda: {"deepl_ok": True, "deepl_mensaje": "(stub)"}
    )
    monkeypatch.setattr(
        voice_service, "estado", lambda: {"elevenlabs_ok": True, "elevenlabs_mensaje": "(stub)"}
    )

    from backend.main import app

    async def _run() -> tuple[int, float]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as cli:
            asks = [
                asyncio.create_task(
                    cli.post("/api/ask", json={"personaje_id": "t-rex", "pregunta": "hola"})
                )
                for _ in range(2)
            ]
            await asyncio.sleep(0.1)  # deja que las 2 asks entren en el threadpool

            t0 = time.perf_counter()
            r = await cli.get("/health")
            dt_ms = (time.perf_counter() - t0) * 1000

            await asyncio.gather(*asks)
            return r.status_code, dt_ms

    status, dt_ms = asyncio.run(_run())

    assert status == 200
    # El loop no se bloquea: /health vuelve en milisegundos aunque las asks sigan
    # "trabajando" 1 s cada una. Margen amplio (< 200 ms) para no ser flaky en CI.
    assert dt_ms < 200, f"/health tardó {dt_ms:.0f} ms con 2 asks en vuelo (loop bloqueado)"
