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
REPLICATE_MODEL: str = os.getenv(
    "REPLICATE_MODEL", "black-forest-labs/flux-schnell"
).strip()

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


def describe() -> dict:
    """Devuelve la configuración actual en forma de diccionario.

    Útil para mostrarla en el endpoint /health y depurar rápidamente. NUNCA
    incluimos el token: solo si está configurado o no.
    """
    return {
        "replicate_model": REPLICATE_MODEL,
        "replicate_edit_model": REPLICATE_EDIT_MODEL,
        "aspect_ratio": IMG_ASPECT_RATIO,
        "output_format": IMG_OUTPUT_FORMAT,
        "token_configurado": bool(REPLICATE_API_TOKEN),
    }
