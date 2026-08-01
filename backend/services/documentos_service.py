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
import logging
from datetime import UTC, datetime
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

logger = logging.getLogger(__name__)

# Extensiones de archivo soportadas (mismas que ingest.py).
EXTENSIONES = {".pdf", ".txt", ".md"}


class ConflictoDocumentoError(ValueError):
    """Ya existe un documento con ese nombre para este personaje (→ HTTP 409).

    Hereda de ValueError como TranslationError, pero el router la captura ANTES
    del `except ValueError` genérico para devolver 409 en vez de 400: el frontend
    necesita distinguir con fiabilidad "nombre repetido, ¿sobrescribir?" de
    cualquier otro error de validación.
    """


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
        # Lo normal aquí es que aún no hubiera chunks de este personaje (nada que
        # borrar). Se registra con la traza por si fuese un fallo real de ChromaDB:
        # así no se pierde sin rastro, pero el reindexado continúa igualmente.
        logger.warning(
            "No se pudieron borrar los chunks previos de '%s' antes de reindexar "
            "(normalmente porque aún no había ninguno).",
            personaje_id,
            exc_info=True,
        )
    n_archivos, n_chunks = _indexar_personaje(collection, personaje_id)
    return {"personaje_id": personaje_id, "archivos": n_archivos, "chunks": n_chunks}


# Progreso del reindexado GLOBAL en curso, sondeado por el frontend para pintar
# una barra que avanza (GET /api/reindex/estado). Un único global en memoria
# basta: la app está pensada para un adulto administrando en un solo proceso
# local (mismo supuesto que las sesiones de admin_service). El progreso es por
# PERSONAJE (no por chunk): suficientemente granular para una barra visible sin
# acoplar el conteo al indexado interno de ChromaDB.
_progreso_reindex_todo: dict = {
    "en_curso": False,
    "total": 0,
    "hecho": 0,
    "personaje_actual": None,
}


def estado_reindexado_todo() -> dict:
    """Estado actual del reindexado global (para sondeo). Incluye `porcentaje`."""
    p = _progreso_reindex_todo
    porcentaje = (p["hecho"] / p["total"] * 100) if p["total"] else 0.0
    return {**p, "porcentaje": porcentaje}


def reindexar_todo() -> dict:
    """Reindexado GLOBAL: borra la colección entera y la reconstruye desde cero.

    Actualiza `_progreso_reindex_todo` personaje a personaje mientras dura.
    """
    coleccion = settings_service.get("CHROMA_COLLECTION")
    client = _get_client()
    try:
        client.delete_collection(coleccion)
    except Exception:
        # Lo normal es que la colección no existiera todavía (primer indexado). Se
        # registra con la traza por si fuese otro fallo, sin cortar el reindexado.
        logger.warning(
            "No se pudo borrar la colección '%s' antes del reindexado global "
            "(normalmente porque aún no existía).",
            coleccion,
            exc_info=True,
        )
    collection = client.get_or_create_collection(name=coleccion, metadata={"hnsw:space": "cosine"})

    base = config.DOCUMENTOS_DIR
    carpetas = sorted(d for d in base.iterdir() if d.is_dir()) if base.is_dir() else []

    _progreso_reindex_todo.update(
        en_curso=True, total=len(carpetas), hecho=0, personaje_actual=None
    )
    total_archivos = 0
    total_chunks = 0
    try:
        for carpeta in carpetas:
            _progreso_reindex_todo["personaje_actual"] = carpeta.name
            a, c = _indexar_personaje(collection, carpeta.name)
            total_archivos += a
            total_chunks += c
            _progreso_reindex_todo["hecho"] += 1
    finally:
        _progreso_reindex_todo.update(en_curso=False, personaje_actual=None)

    # La colección se ha borrado y recreado: el handle cacheado del chat quedó
    # obsoleto. Forzamos a reabrirla en la siguiente pregunta.
    rag_service.reiniciar_coleccion()
    return {"personajes": len(carpetas), "archivos": total_archivos, "chunks": total_chunks}


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
        "actualizado_en": fila.actualizado_en.isoformat(),
        "copiado_de_id": fila.copiado_de_id,
    }


def listar(personaje_id: str) -> list[dict]:
    """Documentos de un personaje (metadatos), más recientes primero."""
    db.init_db()
    with db.get_session() as sesion:
        filas = sesion.exec(select(Documento).where(Documento.personaje_id == personaje_id)).all()
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
    sobrescribir: bool = False,
    reindexar: bool = True,
    copiado_de_id: int | None = None,
) -> dict:
    """Inserta (o reemplaza, si `sobrescribir`) la fila de metadatos.

    Si ya existe un documento con ese nombre para el personaje y `sobrescribir` es
    False, lanza ConflictoDocumentoError (→ HTTP 409) en vez de pisarlo en
    silencio. Reindexa al personaje salvo que `reindexar=False` (lo usa la subida
    múltiple, que reindexa una sola vez al final en vez de una vez por fichero).
    """
    db.init_db()
    with db.get_session() as sesion:
        previos = sesion.exec(
            select(Documento).where(
                Documento.personaje_id == personaje_id,
                Documento.nombre_archivo == nombre_archivo,
            )
        ).all()
        if previos and not sobrescribir:
            raise ConflictoDocumentoError(
                f"Ya existe un documento llamado '{nombre_archivo}' para este personaje."
            )
        for p in previos:
            sesion.delete(p)
        ahora = datetime.now(UTC)
        fila = Documento(
            personaje_id=personaje_id,
            nombre_archivo=nombre_archivo,
            origen=origen,
            url_origen=url_origen,
            idioma_original=idioma_original,
            traducido=traducido,
            creado_en=ahora,
            actualizado_en=ahora,
            copiado_de_id=copiado_de_id,
        )
        sesion.add(fila)
        sesion.commit()
        resultado = _a_dict(fila)

    if reindexar:
        reindexar_personaje(personaje_id)
    return resultado


def _preparar_texto(texto: str) -> tuple[str, bool, str]:
    """Detecta el idioma (DeepL) y traduce a inglés SOLO si hace falta.

    Ya no hay checkbox "ya está en inglés": se llama SIEMPRE a DeepL (no ofrece
    un endpoint de detección aparte del de traducir), y se decide con
    `detected_source_lang`. Si ya estaba en inglés, se devuelve el texto
    ORIGINAL (no el eco de DeepL) para no arriesgarse a alterar un documento que
    no necesitaba tocarse. Devuelve (texto, traducido, idioma_detectado).
    """
    texto_traducido, idioma = translation_service.traducir_a_ingles(texto)
    if idioma == "en":
        return texto, False, "en"
    return texto_traducido, True, idioma


def _nombre_con_idioma(stem: str, ext: str, idioma: str, traducido: bool) -> str:
    """Nombre de fichero que indica el idioma de origen (mismo patrón para subida y URL).

    Ya en inglés → "<stem>_en<ext>" (conserva la extensión original). Traducido →
    "<stem>_<idioma>.en.md" (siempre texto plano: es el resultado de la traducción).
    """
    if not traducido:
        return f"{stem}_en{ext}"
    return f"{stem}_{idioma}.en.md"


def subir(
    personaje_id: str,
    nombre_archivo: str,
    contenido: bytes,
    sobrescribir: bool = False,
    reindexar: bool = True,
) -> dict:
    """Guarda un documento subido y reindexa al personaje.

    - Valida el personaje y la extensión (.pdf/.txt/.md).
    - Detecta el idioma con DeepL SIEMPRE (ver `_preparar_texto`): si no está en
      inglés, lo traduce y lo guarda como `<nombre>_<idioma>.en.md`; si ya está,
      conserva el fichero ORIGINAL tal cual (bytes y extensión), solo renombrado
      a `<nombre>_en<ext>` para indicar el idioma de origen.
    - Si ya existe un documento con ese nombre y `sobrescribir` es False, lanza
      ConflictoDocumentoError (→ 409) en vez de pisarlo.
    Lanza ValueError (→ 400) si algo es inválido o si DeepL no está disponible
    (ahora obligatorio para CUALQUIER subida, no solo para traducir).
    """
    _exigir_personaje(personaje_id)
    nombre = Path(nombre_archivo).name.strip()  # evita rutas ("../")
    if not nombre:
        raise ValueError("Nombre de archivo vacío.")
    ext = Path(nombre).suffix.lower()
    if ext not in EXTENSIONES:
        raise ValueError(f"Formato no soportado: '{ext or nombre}'. Sube un .pdf, .txt o .md.")
    if not contenido:
        raise ValueError("El archivo está vacío.")

    texto = _texto_desde_bytes(nombre, contenido)
    if not texto.strip():
        raise ValueError("No se pudo extraer texto del archivo (¿PDF escaneado como imagen?).")
    texto_final, traducido, idioma = _preparar_texto(texto)
    stem = Path(nombre).stem
    nombre_guardado = _nombre_con_idioma(stem, ext, idioma, traducido)

    if not traducido:
        # Ya estaba en inglés: conservamos el fichero ORIGINAL tal cual (texto o PDF).
        carpeta = config.DOCUMENTOS_DIR / personaje_id
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / nombre_guardado).write_bytes(contenido)
    else:
        _guardar_fichero(personaje_id, nombre_guardado, texto_final)

    return _registrar(
        personaje_id,
        nombre_guardado,
        origen="subido",
        traducido=traducido,
        idioma_original=idioma,
        sobrescribir=sobrescribir,
        reindexar=reindexar,
    )


def subir_varios(
    personaje_id: str,
    archivos: list[tuple[str, bytes]],
    sobrescribir: bool = False,
) -> dict:
    """Sube varios ficheros de golpe; reindexa al personaje UNA sola vez al final.

    Mejor esfuerzo: un fichero inválido (formato, vacío, conflicto de nombre sin
    `sobrescribir`, fallo de traducción) no aborta el resto. Devuelve
    {"documentos": [...subidos con éxito...], "errores": [{"nombre", "detalle"}, ...]}.
    """
    _exigir_personaje(personaje_id)
    documentos: list[dict] = []
    errores: list[dict] = []
    for nombre_archivo, contenido in archivos:
        try:
            documentos.append(
                subir(
                    personaje_id,
                    nombre_archivo,
                    contenido,
                    sobrescribir=sobrescribir,
                    reindexar=False,
                )
            )
        except ValueError as exc:
            errores.append({"nombre": nombre_archivo, "detalle": str(exc)})
    if documentos:
        reindexar_personaje(personaje_id)
    return {"documentos": documentos, "errores": errores}


def ingesta_url(personaje_id: str, url: str, sobrescribir: bool = False) -> dict:
    """Descarga un artículo de Wikipedia, detecta su idioma y lo traduce si hace falta.

    Reutiliza fetch_wikipedia (parseo de URL + descarga limpia por secciones). El
    idioma de la URL (p. ej. "simple" o "en") ya no se usa para decidir si
    traducir —era una suposición, no una detección real—: se detecta el texto
    descargado igual que en `subir`, vía DeepL.
    Lanza ValueError (→ 400) si la URL no es válida, el artículo no existe, o
    DeepL no está disponible; ConflictoDocumentoError (→ 409) si ya existe un
    documento con ese nombre y `sobrescribir` es False.
    """
    _exigir_personaje(personaje_id)
    from backend import fetch_wikipedia

    try:
        _lang, titulo_slug = fetch_wikipedia._parsear_url(url)
        titulo_real, contenido = fetch_wikipedia._descargar(_lang, titulo_slug)
    except (ValueError, ImportError) as exc:
        raise ValueError(str(exc)) from exc

    texto, traducido, idioma = _preparar_texto(contenido)
    nombre = _nombre_con_idioma(titulo_slug.lower(), ".md", idioma, traducido)
    _guardar_fichero(personaje_id, nombre, texto)
    return _registrar(
        personaje_id,
        nombre,
        origen="url",
        traducido=traducido,
        idioma_original=idioma,
        url_origen=url,
        sobrescribir=sobrescribir,
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

    # Borrar el fichero de disco (best-effort): la fila ya se borró de la BBDD. Si
    # el fichero no se puede eliminar (permisos, bloqueo), se registra con la traza
    # en vez de tragarse el error, porque quedaría un fichero huérfano en disco.
    try:
        (config.DOCUMENTOS_DIR / personaje_id / nombre).unlink(missing_ok=True)
    except OSError:
        logger.warning(
            "No se pudo borrar el fichero de disco '%s' del personaje '%s' (la fila "
            "de la BBDD sí se borró; puede quedar un fichero huérfano).",
            nombre,
            personaje_id,
            exc_info=True,
        )

    reindexar_personaje(personaje_id)


# ---------------------------------------------------------------------------
# Visor: ver/editar contenido, descargar, copiar entre personajes
# ---------------------------------------------------------------------------
def _obtener_fila(personaje_id: str, documento_id: int) -> Documento:
    """Carga una fila validando que pertenece a ese personaje, o lanza ValueError."""
    db.init_db()
    with db.get_session() as sesion:
        fila = sesion.get(Documento, documento_id)
        if fila is None or fila.personaje_id != personaje_id:
            raise ValueError("No existe ese documento para este personaje.")
        sesion.expunge(fila)
        return fila


def obtener_contenido(personaje_id: str, documento_id: int) -> dict:
    """Devuelve el texto actual de un documento (para verlo/editarlo).

    Los .pdf no se reescriben in-place (son binarios): se devuelve el texto
    extraído, marcado como no editable. Lanza ValueError si no existe o el
    fichero falta en disco.
    """
    fila = _obtener_fila(personaje_id, documento_id)
    ruta = config.DOCUMENTOS_DIR / personaje_id / fila.nombre_archivo
    if not ruta.is_file():
        raise ValueError(f"El fichero '{fila.nombre_archivo}' no está en disco.")
    if ruta.suffix.lower() == ".pdf":
        return {"contenido": leer_texto(ruta), "editable": False}
    return {"contenido": ruta.read_text(encoding="utf-8"), "editable": True}


def actualizar_contenido(personaje_id: str, documento_id: int, contenido: str) -> dict:
    """Reemplaza el texto de un documento .txt/.md existente y reindexa.

    Detecta el idioma con DeepL y traduce si hace falta (mismo camino que al
    subir — ya no hay checkbox "ya está en inglés"). No renombra el fichero
    aunque cambie el estado de traducción: a diferencia de `subir()`, aquí el
    documento ya tiene un `id` de referencia y renombrar su fichero sería
    sorprendente. Lanza ValueError si no existe, es un .pdf, o el contenido
    queda vacío.
    """
    fila = _obtener_fila(personaje_id, documento_id)
    ruta = config.DOCUMENTOS_DIR / personaje_id / fila.nombre_archivo
    if ruta.suffix.lower() == ".pdf":
        raise ValueError("No se puede editar el contenido de un PDF; bórralo y sube uno nuevo.")
    if not contenido.strip():
        raise ValueError("El contenido no puede quedar vacío.")

    texto_final, traducido, idioma = _preparar_texto(contenido)
    ruta.write_text(texto_final, encoding="utf-8")

    with db.get_session() as sesion:
        fila_db = sesion.get(Documento, documento_id)
        fila_db.traducido = traducido
        fila_db.idioma_original = idioma
        fila_db.actualizado_en = datetime.now(UTC)
        sesion.add(fila_db)
        sesion.commit()
        resultado = _a_dict(fila_db)

    reindexar_personaje(personaje_id)
    return resultado


def ruta_fichero(personaje_id: str, documento_id: int) -> Path:
    """Resuelve la ruta en disco de un documento, para servirlo tal cual (descarga)."""
    fila = _obtener_fila(personaje_id, documento_id)
    ruta = config.DOCUMENTOS_DIR / personaje_id / fila.nombre_archivo
    if not ruta.is_file():
        raise ValueError(f"El fichero '{fila.nombre_archivo}' no está en disco.")
    return ruta


def copiar_a(
    personaje_id_origen: str,
    documento_id: int,
    personajes_destino: list[str],
    sobrescribir: bool = False,
) -> dict:
    """Copia un documento a uno o varios personajes destino (copia INDEPENDIENTE:
    fichero y fila propios; editar/borrar la copia nunca afecta al original).

    Mejor esfuerzo por destino: uno que falle (no existe, es el propio origen, o
    conflicto de nombre sin `sobrescribir`) no aborta los demás. Devuelve
    {"copiados": [...], "errores": [{"personaje_id", "detalle"}, ...]}.
    """
    fila = _obtener_fila(personaje_id_origen, documento_id)
    ruta_origen = config.DOCUMENTOS_DIR / personaje_id_origen / fila.nombre_archivo
    if not ruta_origen.is_file():
        raise ValueError(f"El fichero '{fila.nombre_archivo}' no está en disco.")
    contenido = ruta_origen.read_bytes()

    copiados: list[dict] = []
    errores: list[dict] = []
    for destino in personajes_destino:
        try:
            if destino == personaje_id_origen:
                raise ValueError("El personaje destino debe ser distinto del de origen.")
            _exigir_personaje(destino)
            carpeta = config.DOCUMENTOS_DIR / destino
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / fila.nombre_archivo).write_bytes(contenido)
            copiados.append(
                _registrar(
                    destino,
                    fila.nombre_archivo,
                    origen=fila.origen,
                    traducido=fila.traducido,
                    idioma_original=fila.idioma_original,
                    url_origen=fila.url_origen,
                    sobrescribir=sobrescribir,
                    copiado_de_id=documento_id,
                )
            )
        except ValueError as exc:
            errores.append({"personaje_id": destino, "detalle": str(exc)})
    return {"copiados": copiados, "errores": errores}
