"""
routers/conversacion.py — Endpoint HTTP de la conversación (RAG)
================================================================

Una puerta de entrada (la lógica vive en services/chat_service.py, que orquesta
rag_service para el texto y voice_service para la voz):

  POST /api/ask  → el niño envía {personaje_id, pregunta} y recibe la respuesta
                   del personaje, fundamentada en la enciclopedia.
"""

import json
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend import config
from backend.ratelimit import limiter
from backend.routers import errores
from backend.schemas.conversacion import AskRequest, AskResponse
from backend.services import chat_service

router = APIRouter(prefix="/api", tags=["Conversación (RAG)"])


# `def` (no `async def`) A PROPÓSITO: chat_service.responder llama a SDKs SÍNCRONOS
# con I/O de red (DeepL, LLM, ChromaDB, ElevenLabs). Como `def`, FastAPI lo ejecuta
# en su threadpool y el event loop queda LIBRE para atender otras peticiones; como
# `async def` bloquearía el servidor entero durante todo el pipeline (medido en
# scripts/bench_concurrencia.py y docs/mediciones/H2-concurrencia.md).
#
# Rate limit por IP (slowapi): al superarlo, el personaje responde "en personaje"
# (ver ratelimit.manejar_rate_limit), no un 429 crudo. `request` es obligatorio
# para que slowapi identifique al cliente.
@router.post("/ask", response_model=AskResponse)
@limiter.limit(lambda: config.RATE_LIMIT_ASK)
def ask(request: Request, req: AskRequest):
    """Responde a la pregunta del niño como el personaje elegido (RAG + voz)."""
    try:
        result = chat_service.responder(
            personaje_id=req.personaje_id,
            pregunta=req.pregunta,
            nombre_nino=req.nombre_nino,
            sexo_nino=req.sexo_nino,
        )
    except ValueError as exc:
        # Personaje inexistente o falta el token -> 400 (petición incorrecta).
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Cualquier otro fallo (red, LLM, ChromaDB) -> 500 genérico + error_id (el
        # detalle real se registra en el servidor, no se filtra al cliente).
        raise errores.error_500(exc, "generar la respuesta del chat") from exc

    return result


def _sse(evento: dict) -> str:
    """Formatea un evento como un frame SSE: `event: <tipo>` + `data: <json>`."""
    return f"event: {evento['tipo']}\ndata: {json.dumps(evento, ensure_ascii=False)}\n\n"


# SSE (Server-Sent Events) para el streaming del Hito 8. Mantiene `/api/ask` (JSON)
# intacto —el runner y los clientes antiguos lo siguen usando— y añade este canal que
# emite `fuentes`/`token`/`audio_chunk`/`fin` según se generan, para que el niño
# empiece a leer/oír al instante en vez de esperar a toda la respuesta.
#
# `def` (no `async def`): la generación llama a SDKs SÍNCRONOS de red; Starlette itera
# el generador síncrono en el threadpool, así el event loop no se bloquea.
@router.post("/ask/stream")
@limiter.limit(lambda: config.RATE_LIMIT_ASK)
def ask_stream(request: Request, req: AskRequest):
    """Igual que /api/ask pero en STREAMING (SSE): texto por trozos + voz por frases."""

    def generar() -> Iterator[str]:
        try:
            for evento in chat_service.responder_streaming(
                req.personaje_id, req.pregunta, req.nombre_nino, req.sexo_nino
            ):
                yield _sse(evento)
        except ValueError as exc:
            # Personaje inexistente, falta de token o DeepL caído -> mensaje claro.
            yield _sse({"tipo": "error", "mensaje": str(exc)})
        except Exception as exc:
            # Fallo interno: mensaje genérico + error_id (el detalle se loguea, no se filtra).
            yield _sse(
                {"tipo": "error", "mensaje": errores.mensaje_generico(exc, "chat en streaming")}
            )

    # text/event-stream + sin buffering intermedio (proxies/nginx) para que los
    # trozos lleguen en cuanto se emiten.
    return StreamingResponse(
        generar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
