"""
backend/fetch_wikipedia.py — Descarga un artículo de Wikipedia para el RAG
===========================================================================

Script de línea de comandos que descarga el texto limpio de un artículo de
Wikipedia y lo guarda en backend/documentos/<personaje_id>/ listo para que
`ingest.py` lo indexe en ChromaDB.

Por qué wikipedia-api y no el HTML de la página:
  - wikipedia-api devuelve el texto segmentado por secciones, sin menús de
    navegación, tablas de datos ni referencias bibliográficas.
  - Podemos filtrar secciones irrelevantes (bibliografía, enlaces externos…)
    antes de guardar, dejando solo lo útil para el RAG.

Cómo ejecutarlo (desde la raíz del proyecto, con el venv activado):

    python -m backend.fetch_wikipedia <personaje_id> <url_wikipedia>

Ejemplos:
    python -m backend.fetch_wikipedia t-rex https://en.wikipedia.org/wiki/Tyrannosaurus
    python -m backend.fetch_wikipedia t-rex https://simple.wikipedia.org/wiki/Tyrannosaurus_rex
    python -m backend.fetch_wikipedia sherlock_holmes https://en.wikipedia.org/wiki/Sherlock_Holmes

Truco: la Wikipedia en inglés simple (simple.wikipedia.org) usa un vocabulario
adaptado a niños y estudiantes, ideal para este proyecto.  Comprueba si existe
el artículo en simple.wikipedia.org antes de usar en.wikipedia.org.

Tras ejecutar este script, reconstruye el índice vectorial con:
    python -m backend.ingest
"""

import argparse
import logging
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

# Permite ejecutar el script tanto con "python -m backend.fetch_wikipedia" como directamente.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend import config, logging_config  # noqa: E402

logging_config.configurar_logging()
logger = logging.getLogger(__name__)

# En Windows la consola puede usar cp1252 y romper al emitir emojis. El mensaje de
# fallo es ASCII a propósito (loguearlo no debe fallar por el propio encoding).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception as exc:
    logger.debug("No se pudo forzar UTF-8 en stdout: %s", exc)

# Secciones sin valor para el RAG: listas de fuentes, enlaces, notas al pie…
_SECCIONES_EXCLUIDAS = frozenset(
    {
        "references",
        "external links",
        "see also",
        "further reading",
        "bibliography",
        "notes",
        "footnotes",
        "citations",
        "sources",
        "in popular culture",
        "gallery",
        "works cited",
    }
)

# User-Agent obligatorio por la política de la API de Wikipedia.
_USER_AGENT = "MaquinaDelTiempoApp/1.0 (dlopezbernal@gmail.com)"


# ---------------------------------------------------------------------------
# Funciones internas
# ---------------------------------------------------------------------------


def _parsear_url(url: str) -> tuple[str, str]:
    """Extrae (lang, title) de una URL de Wikipedia.

    Ejemplos:
        https://en.wikipedia.org/wiki/Tyrannosaurus  →  ("en", "Tyrannosaurus")
        https://simple.wikipedia.org/wiki/T_rex      →  ("simple", "T_rex")
    """
    parsed = urlparse(url)
    if not parsed.hostname or "wikipedia.org" not in parsed.hostname:
        raise ValueError(f"La URL no parece de Wikipedia: {url}")

    lang = parsed.hostname.split(".")[0]  # "en", "simple", "es", …
    partes = [p for p in parsed.path.split("/") if p]
    if len(partes) < 2 or partes[0].lower() != "wiki":
        raise ValueError(
            f"No se puede extraer el título de la URL: {url}\n"
            "Asegúrate de que la URL tenga la forma https://<lang>.wikipedia.org/wiki/<Título>"
        )
    title = unquote(partes[1])
    return lang, title


def _formatear_secciones(secciones, nivel: int = 2) -> str:
    """Convierte las secciones de wikipedia-api a markdown de forma recursiva."""
    partes: list[str] = []
    for sec in secciones:
        if sec.title.lower() in _SECCIONES_EXCLUIDAS:
            continue
        cabecera = f"{'#' * nivel} {sec.title}"
        cuerpo = sec.text.strip()
        bloque = f"{cabecera}\n\n{cuerpo}" if cuerpo else cabecera
        partes.append(bloque)
        if sec.sections:
            sub = _formatear_secciones(sec.sections, nivel + 1)
            if sub:
                partes.append(sub)
    return "\n\n".join(partes)


def _descargar(lang: str, title: str) -> tuple[str, str]:
    """Descarga el artículo y devuelve (título_real, contenido_markdown)."""
    try:
        import wikipediaapi
    except ImportError:
        raise ImportError(
            "Falta la librería 'wikipedia-api'. Instálala con:\n   pip install wikipedia-api"
        ) from None

    wiki = wikipediaapi.Wikipedia(
        user_agent=_USER_AGENT,
        language=lang,
    )
    page = wiki.page(title)
    if not page.exists():
        raise ValueError(
            f"La página '{title}' no existe en Wikipedia (lang={lang}).\n"
            "Comprueba el título exacto o prueba con otro idioma."
        )

    partes = [f"# {page.title}\n\n{page.summary.strip()}"]
    cuerpo = _formatear_secciones(page.sections)
    if cuerpo:
        partes.append(cuerpo)

    return page.title, "\n\n".join(partes)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga un artículo de Wikipedia y lo guarda en backend/documentos/<personaje_id>/.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python -m backend.fetch_wikipedia t-rex "
            "https://en.wikipedia.org/wiki/Tyrannosaurus\n"
            "  python -m backend.fetch_wikipedia t-rex "
            "https://simple.wikipedia.org/wiki/Tyrannosaurus_rex\n"
            "  python -m backend.fetch_wikipedia sherlock_holmes "
            "https://en.wikipedia.org/wiki/Sherlock_Holmes\n"
        ),
    )
    parser.add_argument(
        "personaje_id",
        help="ID del personaje tal como aparece en backend/personajes.py (p.ej. t-rex, sherlock_holmes)",
    )
    parser.add_argument(
        "url",
        help="URL completa del artículo de Wikipedia",
    )
    parser.add_argument(
        "--output",
        metavar="ARCHIVO",
        default=None,
        help="Nombre del archivo .md de salida (por defecto: <titulo>_<lang>.md)",
    )
    args = parser.parse_args()

    # Validar que el personaje existe.
    from backend import personajes as personajes_cfg  # noqa: E402

    if args.personaje_id not in personajes_cfg.NOMBRES:
        ids_validos = ", ".join(personajes_cfg.NOMBRES.keys())
        logger.error(
            "Personaje '%s' no encontrado. IDs válidos: %s",
            args.personaje_id,
            ids_validos,
        )
        sys.exit(1)

    # Parsear URL.
    try:
        lang, titulo_slug = _parsear_url(args.url)
    except ValueError as e:
        logger.error("%s", e)
        sys.exit(1)

    logger.info("🌐 Descargando '%s' de Wikipedia (%s)…", titulo_slug, lang)

    try:
        titulo_real, contenido = _descargar(lang, titulo_slug)
    except (ImportError, ValueError) as e:
        logger.error("%s", e)
        sys.exit(1)

    # Carpeta de destino.
    carpeta = config.DOCUMENTOS_DIR / args.personaje_id
    carpeta.mkdir(parents=True, exist_ok=True)

    nombre_archivo = args.output or f"{titulo_slug.lower()}_{lang}.md"
    destino = carpeta / nombre_archivo

    destino.write_text(contenido, encoding="utf-8")

    num_lineas = contenido.count("\n") + 1
    logger.info("✅ Guardado: %s", destino)
    logger.info("   %s líneas · %s caracteres", num_lineas, f"{len(contenido):,}")
    logger.info("Ahora reconstruye el índice vectorial con:  python -m backend.ingest")


if __name__ == "__main__":
    main()
