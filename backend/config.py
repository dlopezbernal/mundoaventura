"""
config.py — Configuración central del backend
================================================

Aquí leemos la configuración desde el archivo `.env` (variables de entorno) y
la dejamos disponible para el resto del backend en un único sitio.

¿Por qué un archivo de config separado?
  - Para no repetir rutas ni "valores mágicos" por todo el código.
  - Para poder cambiar de modelo de Replicate tocando solo el .env.

La generación de imágenes ya NO se hace en local: se delega a Replicate.com.
Por eso aquí no hay nada de GPU/CUDA ni de Stable Diffusion: solo el token de
Replicate y los parámetros de la imagen que pedimos.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 1) Localizar la raíz del proyecto y cargar el .env
# ---------------------------------------------------------------------------
# __file__ es la ruta de ESTE archivo (backend/config.py).
#   .parent       -> carpeta backend/
#   .parent.parent -> raíz del proyecto (capston/)
# Trabajar con rutas absolutas evita errores según desde dónde arranques el server.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# load_dotenv lee el archivo .env y vuelca sus variables al entorno (os.environ).
# Si el .env no existe, simplemente no carga nada y usamos los valores por defecto.
load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------------------------
# 2) Replicate.com (generación de la escena en la nube)
# ---------------------------------------------------------------------------
# Token de la API de Replicate. La librería `replicate` lo lee del entorno
# automáticamente (variable REPLICATE_API_TOKEN), pero lo exponemos aquí para
# poder VALIDAR que está configurado y avisar con un mensaje claro si falta.
REPLICATE_API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN", "").strip()

# Modelo de texto-a-imagen que genera la escena (personaje + ubicación).
# Por defecto FLUX schnell: muy rápido y barato, calidad excelente.
REPLICATE_MODEL: str = os.getenv("REPLICATE_MODEL", "black-forest-labs/flux-schnell").strip()

# Modelo de EDICIÓN de imagen para el modo "Usar mi foto": en una sola llamada
# estiliza la foto del niño a Pixar 3D y añade el personaje de forma coherente.
# FLUX Kontext está pensado justo para "edita esto y conserva el resto".
REPLICATE_EDIT_MODEL: str = os.getenv(
    "REPLICATE_EDIT_MODEL", "black-forest-labs/flux-kontext-pro"
).strip()

# Proporción de la imagen generada ("1:1", "16:9", "9:16", "4:3"...).
IMG_ASPECT_RATIO: str = os.getenv("IMG_ASPECT_RATIO", "16:9").strip()

# Formato del archivo de salida ("png", "jpg", "webp").
IMG_OUTPUT_FORMAT: str = os.getenv("IMG_OUTPUT_FORMAT", "png").strip()

# Nº de pasos de difusión. FLUX schnell ("schnell" = rápido en alemán) está
# DESTILADO para dar su mejor resultado en SOLO 4 pasos (su máximo): más pasos no
# mejoran y solo restan velocidad. Lo dejamos configurable pero con 4 por defecto.
IMG_NUM_STEPS: int = int(os.getenv("IMG_NUM_STEPS", "4"))

# Límite de tokens del codificador de texto CLIP de FLUX. FLUX usa DOS codificadores
# en paralelo: CLIP (corto, trunca a ~77 tokens) y T5 (largo, admite cientos). Si el
# prompt supera este límite, CLIP descarta el final del texto, pero T5 lo sigue
# leyendo. Por eso colocamos lo más importante AL PRINCIPIO (entra en CLIP) y el
# estilo/encuadre AL FINAL (puede caer fuera de CLIP, pero T5 lo tiene en cuenta) y,
# si nos pasamos, avisamos con un warning (no es un error: la imagen se genera igual).
CLIP_TOKEN_LIMIT: int = int(os.getenv("CLIP_TOKEN_LIMIT", "77"))


# ---------------------------------------------------------------------------
# 3) Conversación (RAG): LLM en Replicate + base vectorial ChromaDB
# ---------------------------------------------------------------------------
# Modelo de lenguaje que responde como el personaje. Por defecto Llama 3 (8B):
# rápido, barato y suficientemente bueno para respuestas cortas para niños.
REPLICATE_LLM_MODEL: str = os.getenv("REPLICATE_LLM_MODEL", "meta/meta-llama-3-8b-instruct").strip()

# Tope de longitud de la respuesta del LLM (en "tokens" ≈ trozos de palabra).
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "300"))

# Cuántas fichas recupera ChromaDB por pregunta para dárselas al LLM como contexto.
RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "3"))

# --- Evaluator: cómo se decide si una pregunta se responde con el RAG o no ---
# Modos (ver rag_service.py):
#   "umbral"  → SOLO la distancia de ChromaDB decide (gratis, sin LLM).
#   "llm"     → SOLO el LLM-juez decide (más listo, pero cuesta una llamada extra).
#   "hibrido" → el umbral resuelve los casos claros (gratis) y el LLM solo desempata
#               los dudosos. Mejor relación calidad/coste. (Recomendado)
EVALUATOR_MODE: str = os.getenv("EVALUATOR_MODE", "hibrido").strip().lower()
if EVALUATOR_MODE not in ("umbral", "llm", "hibrido"):
    EVALUATOR_MODE = "hibrido"  # valor seguro si el .env trae algo raro

# Umbrales de DISTANCIA de ChromaDB (métrica coseno: 0 = idéntico, 2 = opuesto).
#   distancia <= BAJO  → claramente relevante  (RAG)
#   distancia >= ALTO  → claramente irrelevante (GENERAL)
#   entre ambos        → "dudoso" (en modo híbrido, lo desempata el LLM)
# Son ORIENTATIVOS: actívate DEBUG (muestra "d=...") y ajústalos a tus preguntas.
# Valores calibrados CON traducción activa (pregunta y fichas en inglés):
# los aciertos caen ~0.68 (< BAJO → RAG gratis) y lo irrelevante ~0.95+ (≥ ALTO).
EVALUATOR_UMBRAL_BAJO: float = float(os.getenv("EVALUATOR_UMBRAL_BAJO", "0.75"))
EVALUATOR_UMBRAL_ALTO: float = float(os.getenv("EVALUATOR_UMBRAL_ALTO", "0.95"))

# Si el Evaluator decide GENERAL (las fichas no sirven), ¿el personaje responde con
# su conocimiento propio (una llamada MÁS al LLM, la que genera la respuesta) o con
# un mensaje FIJO de "no lo sé" sin llamar a ningún modelo? True = comportamiento de
# siempre (fallback a conocimiento general). False = chat estrictamente anclado a
# los documentos: fuera de ellos, respuesta fija y sin coste de LLM.
PERMITIR_CONOCIMIENTO_GENERAL: bool = os.getenv(
    "PERMITIR_CONOCIMIENTO_GENERAL", "true"
).strip().lower() in ("1", "true", "yes", "on")

# --- Traducción (DeepL) ---
# Los documentos están en INGLÉS (mejora la calidad de los embeddings). Para
# buscar bien, traducimos la pregunta del niño ES→EN con DeepL antes del retrieval.
# Sin clave, el sistema sigue funcionando (busca con la pregunta en español, peor).
# Consigue una clave gratis (500.000 caracteres/mes) en https://www.deepl.com/pro-api
DEEPL_API_KEY: str = os.getenv("DEEPL_API_KEY", "").strip()

# Carpeta donde ChromaDB guarda su índice vectorial (persistente entre reinicios).
CHROMA_DIR: Path = (PROJECT_ROOT / os.getenv("CHROMA_DIR", "backend/chroma_db")).resolve()

# --- Base de datos de configuración (SQLite) ---
# Fichero SQLite donde viven los AJUSTES editables en caliente y el catálogo
# (personajes, ubicaciones, documentos). NO guarda secretos (las claves API
# siguen en el .env). Es "bootstrap": la RUTA de la BBDD sí se lee del .env, pero
# su CONTENIDO (los ajustes) se edita desde la UI, no desde aquí. Ver
# services/settings_service.py. No se versiona (está en .gitignore).
CONFIG_DB_PATH: Path = (
    PROJECT_ROOT / os.getenv("CONFIG_DB_PATH", "backend/config_db.sqlite3")
).resolve()

# --- Ingesta de documentos (chunking) ---
# Carpeta raíz de los documentos, organizada por personaje:
#   backend/documentos/<personaje_id>/<archivo.pdf|.txt|.md>
DOCUMENTOS_DIR: Path = (PROJECT_ROOT / os.getenv("DOCUMENTOS_DIR", "backend/documentos")).resolve()

# Troceado (chunking) con solape, en caracteres:
#   CHUNK_SIZE    → tamaño de cada fragmento.
#   CHUNK_OVERLAP → cuántos caracteres se repiten entre un chunk y el siguiente,
#                   para no perder ideas que queden partidas en la frontera.
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "120"))

# Nombre de la colección de ChromaDB donde viven los chunks de los documentos.
CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "documentos_en")


# ---------------------------------------------------------------------------
# 3b) Voz (ElevenLabs): transcripción (Scribe/STT) + síntesis (Flash/TTS)
# ---------------------------------------------------------------------------
# ElevenLabs es el TERCER proveedor (junto a Replicate y DeepL). Una sola clave
# cubre las dos mitades: transcribir la pregunta hablada del niño (Scribe) y dar
# voz a la respuesta del personaje (Flash). Modalidad pago por uso.
# Sin esta clave, la voz queda desactivada pero el chat de TEXTO sigue funcionando.
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "").strip()

# Modelo de transcripción (voz → texto). Scribe entiende bien el español.
ELEVENLABS_STT_MODEL: str = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v1").strip()

# Modelo de síntesis (texto → voz). Multilingual v2: la voz más nítida y natural en
# español (turbo/flash suenan "embarrados" — verificado en A/B). La latencia extra
# es despreciable para respuestas cortas de chat, y la claridad importa más con niños.
# Alternativas (menos claras): eleven_turbo_v2_5 o eleven_flash_v2_5 (más rápidas/baratas).
ELEVENLABS_TTS_MODEL: str = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2").strip()

# Formato del audio devuelto por el TTS (mp3; el frontend React lo reproduce
# como base64 con el Audio() del navegador: "data:audio/mpeg;base64,...").
TTS_OUTPUT_FORMAT: str = os.getenv("TTS_OUTPUT_FORMAT", "mp3_44100_128").strip()

# Idioma de la transcripción (la pregunta del niño se dice en español).
STT_LANG: str = os.getenv("STT_LANG", "es").strip()


# ---------------------------------------------------------------------------
# 3c) Personajes: límite del catálogo
# ---------------------------------------------------------------------------
# Tope fijo de personajes (activos + inactivos). A diferencia de los ajustes de
# settings_service, esto NO es editable desde el menú de configuración: es una
# decisión de despliegue (control de costes/alcance), fijada por quien instala
# la app, no por el adulto que la usa día a día.
MAX_PERSONAJES: int = int(os.getenv("MAX_PERSONAJES", "10"))


# ---------------------------------------------------------------------------
# 3d) Resiliencia de red: timeouts y reintentos (Hito 2)
# ---------------------------------------------------------------------------
# Sin timeout, una llamada colgada a un proveedor deja la petición esperando para
# siempre (y ocupa un hilo del threadpool). Sin reintentos, un 429/5xx puntual del
# free tier tumba la petición. Todos los valores se pueden ajustar desde el .env.
#
# Timeout (segundos) de cada cliente de proveedor:
#   - Replicate genera imágenes/LLM: puede tardar bastante → margen amplio.
#   - ElevenLabs (STT/TTS) es más rápido.
#   - DeepL gestiona su PROPIO timeout + backoff internamente (deepl.http_client);
#     aquí solo fijamos su timeout de conexión de forma explícita (ver translation_service).
REPLICATE_TIMEOUT: float = float(os.getenv("REPLICATE_TIMEOUT", "120"))
ELEVENLABS_TIMEOUT: float = float(os.getenv("ELEVENLABS_TIMEOUT", "60"))
DEEPL_TIMEOUT: float = float(os.getenv("DEEPL_TIMEOUT", "10"))

# Reintentos con backoff exponencial + jitter ante errores TRANSITORIOS (429 y 5xx,
# más timeouts/errores de conexión). HTTP_MAX_INTENTOS es el nº TOTAL de intentos
# (p. ej. 3 = 1 original + 2 reintentos). La espera del intento n es
# BACKOFF_BASE * 2^(n-1) segundos (± jitter), tope HTTP_BACKOFF_MAX. Solo aplica a
# Replicate y ElevenLabs: DeepL ya reintenta por su cuenta (no lo duplicamos).
HTTP_MAX_INTENTOS: int = int(os.getenv("HTTP_MAX_INTENTOS", "3"))
HTTP_BACKOFF_BASE: float = float(os.getenv("HTTP_BACKOFF_BASE", "0.5"))
HTTP_BACKOFF_MAX: float = float(os.getenv("HTTP_BACKOFF_MAX", "8"))


# ---------------------------------------------------------------------------
# 3e) Límites de tamaño de las subidas (Hito 2)
# ---------------------------------------------------------------------------
# Los endpoints multipart (foto, audio, documentos) cargaban el fichero entero en
# memoria sin comprobar nada: una URL pública podía subir un fichero gigante y
# tumbar el proceso. Se leen por trozos con un tope; por encima → HTTP 413. En MB,
# configurables desde el .env.
MAX_IMAGEN_MB: float = float(os.getenv("MAX_IMAGEN_MB", "10"))
MAX_AUDIO_MB: float = float(os.getenv("MAX_AUDIO_MB", "5"))
MAX_DOCUMENTO_MB: float = float(os.getenv("MAX_DOCUMENTO_MB", "20"))


def _leer_bool(nombre: str, por_defecto: str = "false") -> bool:
    """Lee una variable de entorno como booleano (acepta true/1/yes/on)."""
    return os.getenv(nombre, por_defecto).strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# 4) Modo desarrollo
# ---------------------------------------------------------------------------
# Cuando DEBUG está activo, el BACKEND imprime en SU consola (uvicorn) el origen
# de cada respuesta del chat (🟢 RAG / 🟡 GENERAL) y la traza de los prompts que
# envía a los servicios externos. NO se muestra en el frontend: la interfaz que ve
# el niño queda siempre limpia. En la versión final se deja en false.
# (El botón "Probar conexión" del frontend se controla aparte con VITE_DEBUG en
# frontend-react/.env, no con esta variable.)
DEBUG: bool = _leer_bool("DEBUG", "false")


def describe() -> dict:
    """Devuelve la configuración actual en forma de diccionario.

    Útil para mostrarla en el endpoint /health y depurar rápidamente. NUNCA
    incluimos el token: solo si está configurado o no.
    """
    return {
        "replicate_model": REPLICATE_MODEL,
        "replicate_edit_model": REPLICATE_EDIT_MODEL,
        "replicate_llm_model": REPLICATE_LLM_MODEL,
        "aspect_ratio": IMG_ASPECT_RATIO,
        "output_format": IMG_OUTPUT_FORMAT,
        "clip_token_limit": CLIP_TOKEN_LIMIT,
        "token_configurado": bool(REPLICATE_API_TOKEN),
        "evaluator_mode": EVALUATOR_MODE,
        "evaluator_umbral_bajo": EVALUATOR_UMBRAL_BAJO,
        "evaluator_umbral_alto": EVALUATOR_UMBRAL_ALTO,
        "deepl_configurado": bool(DEEPL_API_KEY),
        "debug": DEBUG,
    }
