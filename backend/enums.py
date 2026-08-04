"""
enums.py — Enumeraciones del dominio (Hito 5)
=============================================

Cadenas "mágicas" que antes viajaban sueltas por el código ("RAG", "umbral",
"subido"…) y era fácil escribir mal sin que nada avisara. Se centralizan aquí como
`StrEnum`: un miembro **ES** su cadena (`Origen.RAG == "RAG"` es True), así que la
serialización JSON y las comparaciones con strings siguen funcionando IGUAL —el
cambio es puramente de legibilidad y autocompletado, sin romper el contrato.
"""

from enum import StrEnum


class Origen(StrEnum):
    """De dónde sale la respuesta del personaje (campo `origen` de /api/ask)."""

    RAG = "RAG"  # fundamentada en las fichas recuperadas
    GENERAL = "GENERAL"  # conocimiento propio del LLM (las fichas no servían)
    SIN_INFO = "SIN_INFO"  # fichas no válidas y conocimiento general desactivado


class MetodoDecision(StrEnum):
    """Cómo decidió el Evaluator el reparto RAG/no-RAG (campo `metodo`)."""

    UMBRAL = "umbral"  # por distancia coseno (gratis)
    LLM = "llm"  # desempate del LLM-juez
    RERANK = "rerank"  # por la puntuación del reranker (cross-encoder)


class ModoEvaluator(StrEnum):
    """Ajuste EVALUATOR_MODE: cómo se decide RAG vs GENERAL."""

    UMBRAL = "umbral"
    LLM = "llm"
    HIBRIDO = "hibrido"


class OrigenDocumento(StrEnum):
    """Cómo entró un documento del RAG a la base de conocimiento."""

    SUBIDO = "subido"  # subida de fichero
    URL = "url"  # ingesta desde URL de Wikipedia
