"""
routers/conversacion.py — Endpoint HTTP de la conversación (RAG)
================================================================

Una puerta de entrada (la lógica vive en services/chat_service.py, que orquesta
rag_service para el texto y voice_service para la voz):

  POST /api/ask  → el niño envía {personaje_id, pregunta} y recibe la respuesta
                   del personaje, fundamentada en la enciclopedia.
"""

from fastapi import APIRouter, HTTPException, Request

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
        )
    except ValueError as exc:
        # Personaje inexistente o falta el token -> 400 (petición incorrecta).
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Cualquier otro fallo (red, LLM, ChromaDB) -> 500 genérico + error_id (el
        # detalle real se registra en el servidor, no se filtra al cliente).
        raise errores.error_500(exc, "generar la respuesta del chat") from exc

    return result
