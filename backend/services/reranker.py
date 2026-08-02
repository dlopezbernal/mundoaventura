"""
services/reranker.py — Reordenado de candidatos con un cross-encoder (Hito 4.3)
==============================================================================

El retrieval de ChromaDB usa un **bi-encoder**: embebe la pregunta y cada ficha por
SEPARADO y compara vectores (distancia coseno). Es rápido pero pierde matices, porque
nunca "lee" la pregunta y la ficha juntas.

Un **cross-encoder** (reranker) sí las lee JUNTAS ("¿responde este texto a esta
pregunta?") y da una puntuación de relevancia mucho más fina. El truco clásico de un
RAG bueno es un embudo en dos pasos:

  1) RECUPERAR ANCHO: el bi-encoder trae N candidatos baratos (p. ej. 10).
  2) REORDENAR: el cross-encoder puntúa esos N y nos quedamos con los mejores (top-3).

Así juntamos lo barato (bi-encoder sobre miles de chunks) con lo preciso (cross-encoder
sobre unos pocos). Igual que `embeddings.py`, corre con **fastembed (ONNX/CPU, sin
torch)** — coherente con el "backend ligero" del proyecto.

El modelo es multilingüe: puntúa bien una pregunta en español contra fichas en inglés
(medido), lo que además prepara el terreno para quitar DeepL en H4.4.

La puntuación es un *logit* crudo: **más alto = más relevante** (positivo para un buen
match, negativo para uno malo). Ojo: va en sentido CONTRARIO a la distancia coseno
(donde MENOR = mejor). El Evaluator lo tiene en cuenta (ver rag_service).
"""

import logging

from backend.services import settings_service

logger = logging.getLogger(__name__)

# Registro de rerankers. "off" = sin reranker (camino de siempre: solo distancia coseno).
_RERANKERS: dict[str, dict | None] = {
    "off": None,
    "jina-v2": {"modelo": "jinaai/jina-reranker-v2-base-multilingual"},
}

RERANKERS_DISPONIBLES = list(_RERANKERS)

# Modelos fastembed cargados (por nombre): la carga descarga el ONNX la 1ª vez.
_modelos: dict[str, object] = {}


def reranker_actual() -> str:
    """Id del reranker vigente (cae a 'off' si el ajuste trae algo raro)."""
    r = settings_service.get("RERANKER")
    return r if r in _RERANKERS else "off"


def _spec() -> dict | None:
    return _RERANKERS[reranker_actual()]


def activo() -> bool:
    """True si hay un reranker configurado (hay que reordenar tras el retrieval)."""
    return _spec() is not None


def _modelo():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    nombre = _spec()["modelo"]
    if nombre not in _modelos:
        logger.info("Cargando reranker '%s' (fastembed/ONNX, CPU)...", nombre)
        _modelos[nombre] = TextCrossEncoder(nombre)
    return _modelos[nombre]


def rerank(pregunta: str, documentos: list[str]) -> list[float]:
    """Puntúa cada documento frente a la pregunta (más alto = más relevante).

    Devuelve una lista de floats alineada con `documentos` (misma longitud/orden).
    NO reordena: solo puntúa; el orden lo aplica quien llama (rag_service), que así
    conserva los metadatos y distancias en paralelo.
    """
    if not documentos:
        return []
    return [float(s) for s in _modelo().rerank(pregunta, documentos)]
