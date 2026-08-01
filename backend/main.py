"""
main.py — Punto de entrada del BACKEND (servidor de IA)
========================================================

Este archivo crea la aplicación FastAPI y la pone en marcha. Para arrancarla:

    uvicorn backend.main:app --reload

  - "backend.main"  -> este archivo (módulo)
  - "app"           -> la variable FastAPI de abajo
  - "--reload"      -> reinicia solo al guardar cambios (cómodo en desarrollo)

Luego abre la documentación interactiva en:  http://127.0.0.1:8000/docs
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import config, logging_config, seed
from backend.routers import admin as admin_router
from backend.routers import apis as apis_router
from backend.routers import config as config_router
from backend.routers import conversacion, generation, transcription
from backend.routers import documentos as documentos_router
from backend.routers import personajes as personajes_router
from backend.routers import ubicaciones as ubicaciones_router
from backend.services import (
    acceso_service,
    admin_service,
    translation_service,
    voice_service,
)

# Configurar el logging ANTES que nada, para que cualquier mensaje del arranque
# (incluido el fallo del apaño de encoding de abajo) salga ya con formato.
logging_config.configurar_logging()
logger = logging.getLogger(__name__)

# Dependencia que exige el PIN de adulto (token de sesión) en los endpoints
# sensibles del área de configuración. Los del flujo del niño no la llevan.
_admin = [Depends(admin_service.requiere_admin)]

# Candado del túnel: código de acceso compartido para los endpoints del niño que
# CUESTAN dinero (generación, chat, voz). Desactivado si ACCESS_CODE está vacío.
_acceso = [Depends(acceso_service.requiere_codigo_acceso)]

# En Windows la consola puede usar cp1252 y romper al emitir emojis (✅, ⚠️...) en
# los logs de arranque. Forzamos UTF-8 en la salida para que ningún mensaje falle
# según el terminal. (Mismo apaño que backend/ingest.py.) El mensaje de fallo es
# ASCII a propósito: si el propio stream no admite UTF-8, loguearlo no debe fallar.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8")
    except Exception as exc:
        logger.debug("No se pudo forzar UTF-8 en %s: %s", getattr(_flujo, "name", _flujo), exc)


# ---------------------------------------------------------------------------
# 1) Ciclo de vida de la app (arranque) + creación
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Comprobaciones al arrancar (patrón `lifespan` moderno de FastAPI).

    Al levantar el servidor: (1) crea la BBDD de configuración y siembra los valores
    del código si aún no existen (idempotente); (2) verifica que DeepL está disponible
    (OBLIGATORIO para el chat) y si ElevenLabs (voz) está configurado. No detenemos el
    servidor si algo falla (para que /docs y /health sigan accesibles), pero avisamos
    con claridad. El código tras `yield` (apagado) no necesita nada por ahora.
    """
    # Configuración: crear tablas + seeding "código → BBDD" (no pisa lo ya guardado).
    try:
        creados = seed.sembrar_todo()
        logger.info(
            "BBDD de configuración lista. Sembrados nuevos → ajustes=%s, personajes=%s, "
            "ubicaciones=%s. ✅",
            creados["ajustes"],
            creados["personajes"],
            creados["ubicaciones"],
        )
    except Exception:
        # Si el seeding falla, la app sigue: settings_service cae a los defaults.
        # exc_info=True registra la traza completa para poder diagnosticarlo.
        logger.warning(
            "No se pudo preparar/sembrar la BBDD de configuración; se usarán los "
            "valores por defecto de config.py. ⚠️",
            exc_info=True,
        )

    # Con la BBDD ya lista, ajustar el nivel de log al ajuste DEBUG vigente.
    logging_config.aplicar_nivel_debug()

    est = translation_service.estado()
    if est["deepl_ok"]:
        logger.info("DeepL conectado. ✅")
    else:
        logger.warning("DeepL NO disponible (OBLIGATORIO para el chat): %s", est["deepl_mensaje"])

    est_voz = voice_service.estado()
    if est_voz["elevenlabs_ok"]:
        logger.info("ElevenLabs (voz) configurado. ✅")
    else:
        logger.warning(
            "ElevenLabs NO configurado (voz desactivada): %s", est_voz["elevenlabs_mensaje"]
        )

    yield


app = FastAPI(
    title="Máquina del Tiempo en tu Habitación — Backend",
    description="Servidor de IA. Genera una escena (ubicación + personaje) con Replicate.",
    version="0.3.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# 2) CORS — permitir que el frontend se conecte
# ---------------------------------------------------------------------------
# CORS es una regla de seguridad de los navegadores: por defecto, una web solo
# puede llamar a su propio dominio. Como el frontend (la SPA React) y el backend
# pueden estar en orígenes distintos (sobre todo con el túnel de Colab), los
# orígenes permitidos se leen de CORS_ORIGINS (lista separada por comas, ver
# .env.example). Sin definirla se permite cualquier origen ("*"): cómodo en
# desarrollo; restríngela si expones el backend a internet.
#
# allow_credentials=False a propósito: la app no usa cookies ni sesiones, y los
# navegadores RECHAZAN la combinación allow_origins=["*"] + credenciales.
_cors_origins = [
    origen.strip() for origen in os.getenv("CORS_ORIGINS", "").split(",") if origen.strip()
] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],  # GET, POST, etc.
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 3) Enchufar los routers (los endpoints de cada fase)
# ---------------------------------------------------------------------------
# Endpoints del niño que cuestan dinero (generación, chat, voz): van detrás del
# candado del túnel (X-Access-Code). Los catálogos (GET) se dejan públicos aparte.
# Generación de la escena (ubicación + personaje) con Replicate.
app.include_router(generation.router, dependencies=_acceso)
# Conversación con el personaje (RAG: ChromaDB + LLM en Replicate).
app.include_router(conversacion.router, dependencies=_acceso)
# Transcripción de voz (STT): la pregunta hablada del niño → texto (ElevenLabs Scribe).
app.include_router(transcription.router, dependencies=_acceso)
# Admin: acceso con PIN de adulto + import/export (endpoints públicos mínimos
# para arrancar; los sensibles se protegen dentro del propio router).
app.include_router(admin_router.router)
# Configuración: ajustes editables en caliente (SQLite + settings_service).
# TODA la zona de config va detrás del PIN de adulto (requiere_admin).
app.include_router(config_router.router, dependencies=_admin)
# Configuración · APIs: claves de los proveedores (leer/escribir el .env).
app.include_router(apis_router.router, dependencies=_admin)
# Configuración · Personajes: el catálogo se LEE en público (lo usa el niño);
# las escrituras y las voces se protegen por ruta dentro del router.
app.include_router(personajes_router.router)
# Configuración · Documentos: base de conocimiento del RAG (todo protegido).
app.include_router(documentos_router.router, dependencies=_admin)
# Configuración · Ubicaciones: catálogo (GET público; escrituras protegidas por ruta).
app.include_router(ubicaciones_router.router)


# ---------------------------------------------------------------------------
# 4) Endpoints básicos de salud / información
# ---------------------------------------------------------------------------
@app.get("/", tags=["Info"])
def root():
    """Mensaje de bienvenida. Útil para comprobar que el server responde."""
    return {
        "proyecto": "Máquina del Tiempo en tu Habitación",
        "fases_activas": [
            "Elegir ubicación + personaje → escena (Replicate)",
            "Conversar con el personaje por texto (RAG: ChromaDB + LLM)",
        ],
        "documentacion": "/docs",
    }


@app.get("/health", tags=["Info"])
def health():
    """Comprobación de estado: token de Replicate, modelo, y conexión con DeepL.

    Devuelve la configuración actual. Muy útil para verificar de un vistazo que
    todo lo necesario (Replicate y DeepL) está bien configurado.
    """
    return {
        "status": "ok",
        **config.describe(),
        **translation_service.estado(),
        **voice_service.estado(),
    }
