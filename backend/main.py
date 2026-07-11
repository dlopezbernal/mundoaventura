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

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import config, seed
from backend.routers import config as config_router
from backend.routers import conversacion, generation, transcription
from backend.services import translation_service, voice_service

# En Windows la consola puede usar cp1252 y romper al imprimir emojis (✅, ⚠️...),
# lo que llegaría a tumbar el arranque (el hook de startup imprime "DeepL conectado ✅").
# Forzamos UTF-8 en la salida para que ningún print falle según el terminal.
# (Mismo apaño que backend/ingest.py.)
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
        print(
            f"[Arranque] BBDD de configuración lista. Sembrados nuevos → "
            f"ajustes={creados['ajustes']}, personajes={creados['personajes']}, "
            f"ubicaciones={creados['ubicaciones']}. ✅"
        )
    except Exception as exc:
        # Si el seeding falla, la app sigue: settings_service cae a los defaults.
        print(f"[Arranque] ⚠️  No se pudo preparar/sembrar la BBDD de configuración: {exc}")

    est = translation_service.estado()
    if est["deepl_ok"]:
        print("[Arranque] DeepL conectado. ✅")
    else:
        print("[Arranque] ⚠️  DeepL NO disponible (OBLIGATORIO para el chat):")
        print(f"[Arranque]     {est['deepl_mensaje']}")

    est_voz = voice_service.estado()
    if est_voz["elevenlabs_ok"]:
        print("[Arranque] ElevenLabs (voz) configurado. ✅")
    else:
        print("[Arranque] ⚠️  ElevenLabs NO configurado (voz desactivada):")
        print(f"[Arranque]     {est_voz['elevenlabs_mensaje']}")

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
    origen.strip()
    for origen in os.getenv("CORS_ORIGINS", "").split(",")
    if origen.strip()
] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],      # GET, POST, etc.
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 3) Enchufar los routers (los endpoints de cada fase)
# ---------------------------------------------------------------------------
# Generación de la escena (ubicación + personaje) con Replicate.
app.include_router(generation.router)
# Conversación con el personaje (RAG: ChromaDB + LLM en Replicate).
app.include_router(conversacion.router)
# Transcripción de voz (STT): la pregunta hablada del niño → texto (ElevenLabs Scribe).
app.include_router(transcription.router)
# Configuración: ajustes editables en caliente (SQLite + settings_service).
app.include_router(config_router.router)


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
