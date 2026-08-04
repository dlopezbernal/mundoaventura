"""
services/vector_store.py — Cliente ÚNICO de ChromaDB (Hito 5)
============================================================

Antes `rag_service` (consulta) y `documentos_service` (indexado) creaban cada uno
su propio `PersistentClient` sobre la MISMA carpeta. Además `rag_service` cacheaba
el objeto-colección; cuando un reindexado global la borraba y recreaba, ese handle
quedaba obsoleto — de ahí que existiera `reiniciar_coleccion()` para "olvidarlo".

Aquí centralizamos un cliente único (singleton perezoso) y devolvemos la colección
FRESCA en cada llamada (`get_or_create_collection` es una operación ligera de
metadatos). Sin objeto-colección cacheado no hay handle que se quede obsoleto tras
un borrado/recreación, así que esa clase de bug desaparece y `reiniciar_coleccion`
ya no hace falta.

ChromaDB usa DISTANCIA COSENO (`hnsw:space="cosine"`, 0=idéntico … 2=opuesto),
configurada IDÉNTICA en indexado y consulta. El nombre de la colección depende del
backend de embeddings vigente (`embeddings.coleccion_actual()`): cada backend tiene
su colección versionada propia, para comparar sin pisar la de la línea base.
"""

import chromadb

from backend import config
from backend.services import embeddings

# Cliente único con persistencia en disco (singleton perezoso). El índice sobrevive
# entre reinicios (config.CHROMA_DIR), así que no hay que recalcularlo cada vez.
_client: chromadb.ClientAPI | None = None


def cliente() -> chromadb.ClientAPI:
    """Devuelve el cliente único de ChromaDB (lo crea la primera vez)."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _client


def coleccion(nombre: str | None = None):
    """Abre (o crea) una colección con métrica coseno.

    `nombre` por defecto = la colección del backend de embeddings vigente. Se pasa
    explícito solo en el reindexado global (que borra y recrea esa misma colección).
    """
    return cliente().get_or_create_collection(
        name=nombre or embeddings.coleccion_actual(),
        metadata={"hnsw:space": "cosine"},
    )


def reiniciar() -> None:
    """Olvida el cliente cacheado (p. ej. si cambiara la ruta de la BBDD en caliente)."""
    global _client
    _client = None
