"""
backend/ingest.py — Ingesta e indexado de documentos (RAG con chunking)
========================================================================

Este script prepara la base de conocimiento del chat a partir de DOCUMENTOS
EXTENSOS (en inglés), usando LangChain para la fase de troceado (chunking).

Flujo (es la "fase de preparación" del RAG):
  1. CARGAR   → recorre backend/documentos/<personaje_id>/ y extrae el TEXTO de
                cada archivo (.pdf con pypdf; .txt/.md leídos directamente).
  2. TROCEAR  → parte cada documento en chunks con SOLAPE usando LangChain
                (RecursiveCharacterTextSplitter, chunk_size + chunk_overlap).
                El solape evita perder ideas que queden partidas en la frontera.
  3. INDEXAR  → guarda cada chunk en ChromaDB con su metadato `personaje_id`
                (sacado del nombre de la carpeta), para que en el chat cada
                personaje solo "vea" sus propios documentos.

Nota: para leer los archivos NO usamos los cargadores de `langchain-community`
(está en proceso de retirada). Leemos el texto a mano y dejamos a LangChain solo
lo que de verdad aporta aquí: el troceado con solape.

Cómo ejecutarlo (desde la raíz del proyecto, con el venv activado):

    python -m backend.ingest

  - Por defecto BORRA y reconstruye la colección (reindexado limpio).
  - Ejecútalo la PRIMERA vez y cada vez que añadas/cambies documentos.

Importante: los documentos deben estar EN INGLÉS (los embeddings rinden mucho
mejor). En el chat, la pregunta del niño se traduce ES→EN automáticamente.
"""

import argparse
import sys
from pathlib import Path

import chromadb

# En Windows la consola puede usar cp1252 y romper al imprimir emojis (✅, ·...).
# Forzamos UTF-8 en la salida para que el resumen no falle en ningún terminal.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Permite ejecutar el script tanto con "python -m backend.ingest" como directamente.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend import config  # noqa: E402

# Extensiones de archivo soportadas.
EXTENSIONES = {".pdf", ".txt", ".md"}


def _leer_texto(ruta: Path) -> str:
    """Extrae todo el texto de un archivo (.pdf, .txt o .md) como una cadena.

    - PDF: con pypdf, concatenando el texto de todas las páginas.
    - txt/md: leyendo el archivo directamente.
    """
    if ruta.suffix.lower() == ".pdf":
        # Importamos aquí para dar un error claro si falta pypdf.
        from pypdf import PdfReader

        lector = PdfReader(str(ruta))
        return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)

    # .txt y .md son texto plano.
    return ruta.read_text(encoding="utf-8")


def _crear_splitter():
    """Crea el troceador con solape (la pieza clave del chunking)."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    # RecursiveCharacterTextSplitter intenta cortar por límites "naturales"
    # (párrafos, frases, palabras) antes que por mitad de palabra, y aplica el
    # solape entre chunks consecutivos.
    return RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )


def main(reset: bool = True) -> None:
    base = config.DOCUMENTOS_DIR
    if not base.exists():
        print(f"❌ No existe la carpeta de documentos: {base}")
        sys.exit(1)

    # 1) Abrir (o reiniciar) la colección de ChromaDB.
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    if reset:
        try:
            client.delete_collection(config.CHROMA_COLLECTION)
            print(f"♻️  Colección '{config.CHROMA_COLLECTION}' borrada (reindexado limpio).")
        except Exception:
            pass  # no existía todavía: no pasa nada

    collection = client.get_or_create_collection(
        name=config.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},  # misma métrica que usa el chat
    )

    splitter = _crear_splitter()
    print(f"Troceado: chunk_size={config.CHUNK_SIZE}, overlap={config.CHUNK_OVERLAP}\n")

    total_chunks = 0
    total_archivos = 0

    # 2) Recorrer una carpeta por personaje.
    carpetas = sorted([d for d in base.iterdir() if d.is_dir()])
    if not carpetas:
        print("⚠️  No hay carpetas de personaje en backend/documentos/. Nada que indexar.")
        return

    for carpeta in carpetas:
        personaje_id = carpeta.name
        archivos = [f for f in sorted(carpeta.rglob("*")) if f.suffix.lower() in EXTENSIONES]
        if not archivos:
            print(f"[{personaje_id}] (sin documentos)")
            continue

        print(f"[{personaje_id}]")
        for archivo in archivos:
            texto = _leer_texto(archivo)
            chunks = splitter.split_text(texto)  # lista de cadenas (los fragmentos)

            if not chunks:
                print(f"   · {archivo.name}: 0 chunks (vacío)")
                continue

            # 3) Indexar los chunks con su personaje y archivo de origen.
            metadatos = [
                {"personaje_id": personaje_id, "source": archivo.name} for _ in chunks
            ]
            ids = [f"{personaje_id}::{archivo.name}::{i}" for i in range(len(chunks))]

            collection.add(documents=chunks, metadatas=metadatos, ids=ids)
            total_chunks += len(chunks)
            total_archivos += 1
            print(f"   · {archivo.name}: {len(chunks)} chunks")

    print(
        f"\n✅ Indexado completo: {total_archivos} archivos → {total_chunks} chunks "
        f"en la colección '{config.CHROMA_COLLECTION}'."
    )
    if total_chunks == 0:
        print("   (Aún no has puesto documentos. Mira backend/documentos/README.md)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta de documentos para el RAG.")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="No borrar la colección antes de indexar (por defecto sí se borra).",
    )
    args = parser.parse_args()
    main(reset=not args.no_reset)
