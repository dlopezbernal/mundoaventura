"""
services/documentos_service.py — Documentos del RAG por personaje (Hito 5)
==========================================================================

Gestiona la BASE DE CONOCIMIENTO del chat sin tocar código ni la terminal:

  - SUBIR un `.pdf/.txt/.md` a `backend/documentos/<personaje_id>/`.
  - INGESTA DESDE URL (Wikipedia): descarga el artículo limpio (reutiliza
    fetch_wikipedia) y lo guarda como `.md`.
  - TRADUCIR ES→EN al guardar (DeepL) si el adulto NO marca "ya está en inglés":
    los embeddings rinden mucho mejor en inglés.
  - LISTAR / BORRAR los documentos de un personaje (metadatos en la tabla
    `documentos`; el fichero vive en disco).
  - REINDEXAR en ChromaDB de forma INCREMENTAL: al cambiar los documentos de un
    personaje solo se reconstruyen SUS chunks (`delete(where={personaje_id})` +
    reindexar su carpeta), sin tocar los del resto. También hay un reindexado
    global (borra y reconstruye toda la colección).

El troceado (chunk_size/overlap) y el nombre de la colección se leen de
settings_service, igual que el chat y el script `ingest.py`, para que todos usen
SIEMPRE la misma configuración.
"""

import io
from datetime import datetime
from pathlib import Path

import chromadb
from sqlmodel import select

from backend import config, db
from backend.models import Documento
from backend.services import (
    personajes_service,
    rag_service,
    settings_service,
    translation_service,
)

# Extensiones de archivo soportadas (mismas que ingest.py).
EXTENSIONES = {".pdf", ".txt", ".md"}


# ---------------------------------------------------------------------------
# Lectura de texto y troceado (fuente única, reutilizada por ingest.py)
# ---------------------------------------------------------------------------
def leer_texto(ruta: Path) -> str:
    """Extrae el texto de un archivo (.pdf con pypdf; .txt/.md como texto plano)."""
    if ruta.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        lector = PdfReader(str(ruta))
        return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)
    return ruta.read_text(encoding="utf-8")


def _texto_desde_bytes(nombre: str, contenido: bytes) -> str:
    """Extrae el texto de un fichero recibido en memoria (para subidas)."""
    if nombre.lower().endswith(".pdf"):
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(contenido))
        return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)
    return contenido.decode("utf-8", errors="replace")


def _crear_splitter():
    """Crea el troceador con solape (chunk_size/overlap desde settings_service)."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(
        chunk_size=settings_service.get("CHUNK_SIZE"),
        chunk_overlap=settings_service.get("CHUNK_OVERLAP"),
    )


# ---------------------------------------------------------------------------
# Acceso a ChromaDB (cliente propio; chromadb comparte el System por ruta)
# ---------------------------------------------------------------------------
_client: chromadb.ClientAPI | None = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _client


def _get_collection():
    """Abre (o crea) la colección con la MISMA métrica coseno que usa el chat."""
    return _get_client().get_or_create_collection(
        name=settings_service.get("CHROMA_COLLECTION"),
        metadata={"hnsw:space": "cosine"},
    )


def _archivos_de(personaje_id: str) -> list[Path]:
    """Documentos indexables de un personaje, ordenados (por nombre)."""
    carpeta = config.DOCUMENTOS_DIR / personaje_id
    if not carpeta.is_dir():
        return []
    return [f for f in sorted(carpeta.rglob("*")) if f.suffix.lower() in EXTENSIONES]


def _indexar_personaje(collection, personaje_id: str) -> tuple[int, int]:
    """Trocea e indexa TODOS los documentos de un personaje. Devuelve (archivos, chunks)."""
    splitter = _crear_splitter()
    n_archivos = 0
    n_chunks = 0
    for archivo in _archivos_de(personaje_id):
        texto = leer_texto(archivo)
        chunks = splitter.split_text(texto)
        if not chunks:
            continue
        metadatos = [{"personaje_id": personaje_id, "source": archivo.name} for _ in chunks]
        ids = [f"{personaje_id}::{archivo.name}::{i}" for i in range(len(chunks))]
        collection.add(documents=chunks, metadatas=metadatos, ids=ids)
        n_archivos += 1
        n_chunks += len(chunks)
    return n_archivos, n_chunks


def reindexar_personaje(personaje_id: str) -> dict:
    """Reindexado INCREMENTAL: borra solo los chunks de este personaje y los recrea.

    Así cambiar los documentos de un personaje no obliga a reprocesar los del resto.
    """
    collection = _get_collection()
    try:
        collection.delete(where={"personaje_id": personaje_id})
    except Exception:
        pass  # aún no había chunks de este personaje: nada que borrar
    n_archivos, n_chunks = _indexar_personaje(collection, personaje_id)
    return {"personaje_id": personaje_id, "archivos": n_archivos, "chunks": n_chunks}


def reindexar_todo() -> dict:
    """Reindexado GLOBAL: borra la colección entera y la reconstruye desde cero."""
    coleccion = settings_service.get("CHROMA_COLLECTION")
    client = _get_client()
    try:
        client.delete_collection(coleccion)
    except Exception:
        pass  # no existía todavía
    collection = client.get_or_create_collection(
        name=coleccion, metadata={"hnsw:space": "cosine"}
    )

    total_archivos = 0
    total_chunks = 0
    personajes = 0
    base = config.DOCUMENTOS_DIR
    if base.is_dir():
        for carpeta in sorted(d for d in base.iterdir() if d.is_dir()):
            a, c = _indexar_personaje(collection, carpeta.name)
            total_archivos += a
            total_chunks += c
            personajes += 1

    # La colección se ha borrado y recreado: el handle cacheado del chat quedó
    # obsoleto. Forzamos a reabrirla en la siguiente pregunta.
    rag_service.reiniciar_coleccion()
    return {"personajes": personajes, "archivos": total_archivos, "chunks": total_chunks}


# ---------------------------------------------------------------------------
# Metadatos (tabla `documentos`) + operaciones de alta/baja/listado
# ---------------------------------------------------------------------------
def _a_dict(fila: Documento) -> dict:
    return {
        "id": fila.id,
        "personaje_id": fila.personaje_id,
        "nombre_archivo": fila.nombre_archivo,
        "origen": fila.origen,
        "url_origen": fila.url_origen,
        "idioma_original": fila.idioma_original,
        "traducido": fila.traducido,
        "creado_en": fila.creado_en.isoformat(),
    }


def listar(personaje_id: str) -> list[dict]:
    """Documentos de un personaje (metadatos), más recientes primero."""
    db.init_db()
    with db.get_session() as sesion:
        filas = sesion.exec(
            select(Documento).where(Documento.personaje_id == personaje_id)
        ).all()
    filas.sort(key=lambda f: f.creado_en, reverse=True)
    return [_a_dict(f) for f in filas]


def _exigir_personaje(personaje_id: str) -> None:
    if not personajes_service.existe(personaje_id):
        raise ValueError(f"No existe el personaje '{personaje_id}'.")


def _guardar_fichero(personaje_id: str, nombre: str, texto: str) -> Path:
    """Escribe `texto` en documentos/<personaje_id>/<nombre> (crea la carpeta)."""
    carpeta = config.DOCUMENTOS_DIR / personaje_id
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / nombre
    destino.write_text(texto, encoding="utf-8")
    return destino


def _registrar(
    personaje_id: str,
    nombre_archivo: str,
    origen: str,
    traducido: bool,
    idioma_original: str | None,
    url_origen: str | None = None,
) -> dict:
    """Inserta (o reemplaza) la fila de metadatos y reindexa al personaje."""
    db.init_db()
    with db.get_session() as sesion:
        # De-duplicar por (personaje, nombre_archivo): si ya existía, lo reemplazamos.
        previos = sesion.exec(
            select(Documento).where(
                Documento.personaje_id == personaje_id,
                Documento.nombre_archivo == nombre_archivo,
            )
        ).all()
        for p in previos:
            sesion.delete(p)
        fila = Documento(
            personaje_id=personaje_id,
            nombre_archivo=nombre_archivo,
            origen=origen,
            url_origen=url_origen,
            idioma_original=idioma_original,
            traducido=traducido,
            creado_en=datetime.utcnow(),
        )
        sesion.add(fila)
        sesion.commit()
        resultado = _a_dict(fila)

    reindexar_personaje(personaje_id)
    return resultado


def _preparar_texto(texto: str, ya_en_ingles: bool) -> tuple[str, bool, str | None]:
    """Traduce el texto a inglés si procede. Devuelve (texto, traducido, idioma_original)."""
    if ya_en_ingles:
        return texto, False, "en"
    traducido = translation_service.traducir_a_ingles(texto)
    return traducido, True, "es"


def subir(personaje_id: str, nombre_archivo: str, contenido: bytes, ya_en_ingles: bool) -> dict:
    """Guarda un documento subido y reindexa al personaje.

    - Valida el personaje y la extensión (.pdf/.txt/.md).
    - Si NO está en inglés, extrae el texto, lo traduce (DeepL) y lo guarda como
      `<nombre>.en.md` (el índice necesita texto en inglés en disco). Si ya está en
      inglés, guarda el fichero tal cual.
    Lanza ValueError (→ 400) si algo es inválido o si DeepL no está disponible al traducir.
    """
    _exigir_personaje(personaje_id)
    nombre = Path(nombre_archivo).name.strip()  # evita rutas ("../")
    if not nombre:
        raise ValueError("Nombre de archivo vacío.")
    ext = Path(nombre).suffix.lower()
    if ext not in EXTENSIONES:
        raise ValueError(
            f"Formato no soportado: '{ext or nombre}'. Sube un .pdf, .txt o .md."
        )
    if not contenido:
        raise ValueError("El archivo está vacío.")

    if ya_en_ingles:
        # Guardamos el fichero original tal cual (texto o PDF).
        carpeta = config.DOCUMENTOS_DIR / personaje_id
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / nombre).write_bytes(contenido)
        return _registrar(personaje_id, nombre, origen="subido", traducido=False, idioma_original="en")

    # Traducir: extraemos el texto, lo pasamos a inglés y lo guardamos como .md.
    texto = _texto_desde_bytes(nombre, contenido)
    if not texto.strip():
        raise ValueError("No se pudo extraer texto del archivo (¿PDF escaneado como imagen?).")
    texto_en, traducido, idioma = _preparar_texto(texto, ya_en_ingles=False)
    nombre_guardado = f"{Path(nombre).stem}.en.md"
    _guardar_fichero(personaje_id, nombre_guardado, texto_en)
    return _registrar(
        personaje_id, nombre_guardado, origen="subido", traducido=traducido, idioma_original=idioma
    )


def ingesta_url(personaje_id: str, url: str, ya_en_ingles: bool) -> dict:
    """Descarga un artículo de Wikipedia, (opcional) lo traduce y lo indexa.

    Reutiliza fetch_wikipedia (parseo de URL + descarga limpia por secciones).
    Lanza ValueError (→ 400) si la URL no es válida, el artículo no existe, o
    DeepL no está disponible al traducir.
    """
    _exigir_personaje(personaje_id)
    from backend import fetch_wikipedia

    try:
        lang, titulo_slug = fetch_wikipedia._parsear_url(url)
        titulo_real, contenido = fetch_wikipedia._descargar(lang, titulo_slug)
    except (ValueError, ImportError) as exc:
        raise ValueError(str(exc)) from exc

    ya = ya_en_ingles or lang in ("en", "simple")
    texto, traducido, idioma = _preparar_texto(contenido, ya_en_ingles=ya)
    sufijo = "en" if ya else lang
    nombre = f"{titulo_slug.lower()}_{sufijo}{'.en' if traducido else ''}.md"
    _guardar_fichero(personaje_id, nombre, texto)
    return _registrar(
        personaje_id, nombre, origen="url", traducido=traducido, idioma_original=idioma, url_origen=url
    )


def eliminar(personaje_id: str, documento_id: int) -> None:
    """Borra un documento (fichero + fila) y reindexa al personaje.

    Lanza ValueError (→ 400) si el documento no existe o no es de ese personaje.
    """
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Documento, documento_id)
        if fila is None or fila.personaje_id != personaje_id:
            raise ValueError("No existe ese documento para este personaje.")
        nombre = fila.nombre_archivo
        sesion.delete(fila)
        sesion.commit()

    # Borrar el fichero de disco (best-effort).
    try:
        (config.DOCUMENTOS_DIR / personaje_id / nombre).unlink(missing_ok=True)
    except OSError:
        pass

    reindexar_personaje(personaje_id)
