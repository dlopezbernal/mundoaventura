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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import config
from backend.routers import generation

# ---------------------------------------------------------------------------
# 1) Crear la aplicación
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Máquina del Tiempo en tu Habitación — Backend",
    description="Servidor de IA. Genera una escena (ubicación + personaje) con Replicate.",
    version="0.3.0",
)

# ---------------------------------------------------------------------------
# 2) CORS — permitir que el frontend se conecte
# ---------------------------------------------------------------------------
# CORS es una regla de seguridad de los navegadores: por defecto, una web solo
# puede llamar a su propio dominio. Como el frontend (Flet) y el backend pueden
# estar en orígenes distintos (sobre todo con el túnel de Colab), abrimos el
# acceso ("*"). Esto es una práctiva para el proyecto Capston del curso IA. 
# No hacer esto en Proyecto!!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # cualquier origen puede llamar a la API
    allow_credentials=True,
    allow_methods=["*"],      # GET, POST, etc.
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 3) Enchufar los routers (los endpoints de cada fase)
# ---------------------------------------------------------------------------
# Generación de la escena (ubicación + personaje) con Replicate.
# (Las fases de voz/RAG se añadirán aquí en su momento.)
app.include_router(generation.router)


# ---------------------------------------------------------------------------
# 4) Endpoints básicos de salud / información
# ---------------------------------------------------------------------------
@app.get("/", tags=["Info"])
def root():
    """Mensaje de bienvenida. Útil para comprobar que el server responde."""
    return {
        "proyecto": "Máquina del Tiempo en tu Habitación",
        "fases_activas": ["Elegir ubicación + personaje → escena (Replicate)"],
        "documentacion": "/docs",
    }


@app.get("/health", tags=["Info"])
def health():
    """Comprobación de estado: confirma el modelo de Replicate y si hay token.

    Devuelve la configuración actual. Muy útil para verificar de un vistazo que
    el token de Replicate está configurado.
    """
    return {"status": "ok", **config.describe()}
