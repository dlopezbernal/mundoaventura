"""
routers/conversacion.py — Endpoint HTTP de la conversación (RAG)
================================================================

Una puerta de entrada (la lógica vive en services/rag_service.py):

  POST /api/ask  → el niño envía {personaje_id, pregunta} y recibe la respuesta
                   del personaje, fundamentada en la enciclopedia.
"""

from fastapi import APIRouter, HTTPException

from backend.schemas.conversacion import AskRequest, AskResponse
from backend.services import rag_service

router = APIRouter(prefix="/api", tags=["Conversación (RAG)"])


# `def` (no `async def`) A PROPÓSITO: rag_service.responder llama a SDKs SÍNCRONOS
# con I/O de red (DeepL, Replicate, ChromaDB, ElevenLabs). Como `def`, FastAPI lo
# ejecuta en su threadpool y el event loop queda LIBRE para atender otras peticiones;
# como `async def` bloquearía el servidor entero durante todo el pipeline (medido en
# scripts/bench_concurrencia.py y docs/mediciones/H2-concurrencia.md).
@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """Responde a la pregunta del niño como el personaje elegido (RAG)."""
    try:
        result = rag_service.responder(
            personaje_id=req.personaje_id,
            pregunta=req.pregunta,
        )
    except ValueError as exc:
        # Personaje inexistente o falta el token -> 400 (petición incorrecta).
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Cualquier otro fallo (red, LLM, ChromaDB) -> 500.
        raise HTTPException(
            status_code=500, detail=f"Error al generar la respuesta: {exc}"
        ) from exc

    return result
