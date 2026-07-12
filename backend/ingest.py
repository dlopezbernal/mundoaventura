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

Nota: para leer los archivos usamos Python puro en lugar de los cargadores de
`langchain-community` (TextLoader, UnstructuredMarkdownLoader, PyPDFLoader…).
El motivo no es que langchain-community sea malo, sino que aquí no aporta nada
que no tengamos ya: leer un .txt/.md es un `file.read_text()` directo, y para
PDF ya tenemos `pypdf` como dependencia mínima. Meter langchain-community solo
añadiría ~200 MB de paquetes transitivos para hacer lo mismo. Dejamos a
LangChain lo que SÍ aporta y no está resuelto de otra forma: el troceado con
solape (RecursiveCharacterTextSplitter).

Cómo ejecutarlo (desde la raíz del proyecto, con el venv activado):

    python -m backend.ingest

  - Por defecto BORRA y reconstruye la colección (reindexado limpio).
  - Ejecútalo la PRIMERA vez y cada vez que añadas/cambies documentos.

Importante: los documentos deben estar EN INGLÉS (los embeddings rinden mucho
mejor). En el chat, la pregunta del niño se traduce ES→EN automáticamente.
"""

import sys
from pathlib import Path

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
from backend.services import documentos_service, settings_service  # noqa: E402


def main() -> None:
    """Reindexado GLOBAL desde la terminal (borra y reconstruye toda la colección).

    La lógica de troceado e indexado vive en `documentos_service` (fuente única,
    compartida con el menú de configuración), que también reindexa de forma
    INCREMENTAL por personaje. Aquí solo se lanza el reindexado completo y se
    imprime el resumen, para el flujo clásico `python -m backend.ingest`.
    """
    base = config.DOCUMENTOS_DIR
    if not base.exists():
        print(f"❌ No existe la carpeta de documentos: {base}")
        sys.exit(1)

    print(
        f"Troceado: chunk_size={settings_service.get('CHUNK_SIZE')}, "
        f"overlap={settings_service.get('CHUNK_OVERLAP')}\n"
    )
    resumen = documentos_service.reindexar_todo()
    print(
        f"✅ Indexado completo: {resumen['archivos']} archivos → {resumen['chunks']} chunks "
        f"de {resumen['personajes']} personaje(s) en la colección "
        f"'{settings_service.get('CHROMA_COLLECTION')}'."
    )
    if resumen["chunks"] == 0:
        print("   (Aún no has puesto documentos. Mira backend/documentos/README.md)")


if __name__ == "__main__":
    main()
