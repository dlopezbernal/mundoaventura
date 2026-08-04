"""
services/embeddings.py — Backend de embeddings del RAG, seleccionable (Hito 4)
==============================================================================

ChromaDB usaba su embedding_function por defecto: `all-MiniLM-L6-v2`, **monolingüe
inglés**. De ahí venía toda la dependencia de DeepL (traducir documentos y preguntas
al inglés). H4 introduce **embeddings multilingües locales** con `fastembed` (ONNX
sobre CPU, sin torch), que embeben el español directamente.

El backend es un ajuste (`EMBEDDING_BACKEND`, seleccionable en caliente) para poder
COMPARAR contra la línea base de forma justa:

  - `minilm-en`   : camino ORIGINAL. Usa el embedding_function por defecto de Chroma
                    (all-MiniLM-L6-v2) sobre la colección `documentos_en`. Reproduce
                    exactamente la línea base (requiere traducir la pregunta ES→EN).
  - `multi-minilm`: `paraphrase-multilingual-MiniLM-L12-v2` (118M, 384-dim, rápido en
                    CPU). Multilingüe: embebe el español sin traducir. Colección propia.
  - `e5-large`    : `multilingual-e5-large` (fuerte pero 2.24 GB y más lento; exige
                    prefijos `query:`/`passage:`). Alternativa a medir.

Para `minilm-en` seguimos delegando en Chroma (`add(documents=...)` /
`query(query_texts=...)`). Para los multilingües embebemos NOSOTROS (fastembed) y
pasamos los vectores explícitos, porque e5 exige prefijos distintos en consulta y en
documento y el embedding_function de Chroma es el mismo para ambos (no los distingue).
"""

import logging

from backend.services import settings_service

logger = logging.getLogger(__name__)

# Registro de backends. `None` = camino original (embedding_function de Chroma).
_BACKENDS: dict[str, dict | None] = {
    "minilm-en": None,
    "multi-minilm": {
        "modelo": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "coleccion": "documentos_ml_minilm",
        "prefijo_query": "",
        "prefijo_passage": "",
    },
    "e5-large": {
        "modelo": "intfloat/multilingual-e5-large",
        "coleccion": "documentos_ml_e5",
        "prefijo_query": "query: ",
        "prefijo_passage": "passage: ",
    },
}

BACKENDS_DISPONIBLES = list(_BACKENDS)

# Modelos fastembed cargados (por nombre): la carga descarga el ONNX la 1ª vez.
_modelos: dict[str, object] = {}


def backend_actual() -> str:
    """Id del backend vigente (cae a 'minilm-en' si el ajuste trae algo raro)."""
    b = settings_service.get("EMBEDDING_BACKEND")
    return b if b in _BACKENDS else "minilm-en"


def _spec() -> dict | None:
    return _BACKENDS[backend_actual()]


def usa_manuales() -> bool:
    """True si hay que embeber NOSOTROS (backend multilingüe), False para el camino Chroma."""
    return _spec() is not None


def coleccion_actual() -> str:
    """Nombre de la colección de ChromaDB del backend vigente."""
    spec = _spec()
    return spec["coleccion"] if spec else settings_service.get("CHROMA_COLLECTION")


def _modelo():
    from fastembed import TextEmbedding

    nombre = _spec()["modelo"]
    if nombre not in _modelos:
        logger.info("Cargando modelo de embeddings '%s' (fastembed/ONNX, CPU)...", nombre)
        _modelos[nombre] = TextEmbedding(nombre)
    return _modelos[nombre]


def embed_passages(textos: list[str]) -> list[list[float]]:
    """Embebe una lista de fragmentos (con el prefijo de 'passage' si el modelo lo exige)."""
    pref = _spec()["prefijo_passage"]
    modelo = _modelo()
    return [[float(x) for x in vec] for vec in modelo.embed([pref + t for t in textos])]


def embed_query(texto: str) -> list[float]:
    """Embebe una consulta (con el prefijo de 'query' si el modelo lo exige)."""
    pref = _spec()["prefijo_query"]
    vec = next(iter(_modelo().embed([pref + texto])))
    return [float(x) for x in vec]
