"""
frontend/api_client.py — Cliente HTTP hacia el backend
=======================================================

Este módulo es el "teléfono" del frontend: encapsula CÓMO se habla con el
backend, para que la interfaz (main.py) no tenga que saber de URLs ni base64.

Si mañana cambia la API, solo tocamos aquí.
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# Cargamos el .env de la raíz del proyecto para leer BACKEND_URL.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# URL del backend. Por defecto, el backend local. Con Colab, se pone la del túnel.
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


class BackendError(Exception):
    """Error al comunicarnos con el backend (lo mostramos al usuario)."""


def check_health() -> dict:
    """Pregunta al backend por su estado (/health). Devuelve el JSON o lanza error."""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise BackendError(f"No se pudo contactar con el backend en {BACKEND_URL}: {exc}")


def generate(ubicacion_id: str, personaje_id: str) -> dict:
    """Pide al backend generar la escena del personaje en la ubicación elegidos.

    Parámetros
    ----------
    ubicacion_id : str  identificador de la ubicación (ej. "laboratorio").
    personaje_id : str  identificador del personaje (ej. "t-rex").

    Devuelve un dict con, entre otros, "result_png_base64": la escena generada
    (imagen en base64).
    """
    url = f"{BACKEND_URL}/api/generate"

    try:
        payload = {"personaje_id": personaje_id, "ubicacion_id": ubicacion_id}
        # timeout holgado por si Replicate va con cola; FLUX schnell suele tardar pocos segundos.
        response = requests.post(url, json=payload, timeout=120)

        response.raise_for_status()
        return response.json()

    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:
            detail = exc.response.text if exc.response is not None else ""
        raise BackendError(f"El backend devolvió un error: {detail or exc}")
    except requests.RequestException as exc:
        raise BackendError(f"Fallo de conexión con el backend: {exc}")


def ask(personaje_id: str, pregunta: str) -> dict:
    """Envía una pregunta (texto) al personaje y devuelve su respuesta (RAG).

    Devuelve un dict con, entre otros:
      - "respuesta": el texto que dice el personaje (en primera persona).
      - "fuentes":   las fichas de la enciclopedia en las que se apoyó.
    """
    url = f"{BACKEND_URL}/api/ask"

    try:
        payload = {"personaje_id": personaje_id, "pregunta": pregunta}
        # timeout holgado: la 1ª pregunta puede tardar (ChromaDB descarga su
        # modelo de embeddings) y luego está la latencia del LLM en Replicate.
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()

    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:
            detail = exc.response.text if exc.response is not None else ""
        raise BackendError(f"El backend devolvió un error: {detail or exc}")
    except requests.RequestException as exc:
        raise BackendError(f"Fallo de conexión con el backend: {exc}")


def transcribe(audio_path: str) -> str:
    """Sube el audio grabado (multipart) a /api/transcribe y devuelve el texto.

    Se usa cuando el niño pregunta por voz: graba → transcribe → el texto entra
    al mismo flujo que una pregunta escrita.
    """
    url = f"{BACKEND_URL}/api/transcribe"

    try:
        with open(audio_path, "rb") as f:
            files = {"audio": (Path(audio_path).name, f, "application/octet-stream")}
            # timeout holgado: Scribe puede tardar unos segundos en clips largos.
            response = requests.post(url, files=files, timeout=60)

        response.raise_for_status()
        return response.json().get("texto", "")

    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:
            detail = exc.response.text if exc.response is not None else ""
        raise BackendError(f"El backend devolvió un error: {detail or exc}")
    except requests.RequestException as exc:
        raise BackendError(f"Fallo de conexión con el backend: {exc}")


def generate_on_photo(image_path: str, personaje_id: str) -> dict:
    """Pide al backend estilizar la foto del niño y añadir el personaje.

    Sube la foto (multipart) al endpoint /api/generate-on-photo. Devuelve un dict
    con "result_png_base64": la foto en estilo Pixar 3D con el personaje añadido.
    """
    url = f"{BACKEND_URL}/api/generate-on-photo"

    try:
        with open(image_path, "rb") as f:
            files = {"image": (Path(image_path).name, f, "application/octet-stream")}
            data = {"personaje_id": personaje_id}
            # timeout holgado: la edición (Kontext) tarda más que schnell.
            response = requests.post(url, files=files, data=data, timeout=180)

        response.raise_for_status()
        return response.json()

    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:
            detail = exc.response.text if exc.response is not None else ""
        raise BackendError(f"El backend devolvió un error: {detail or exc}")
    except requests.RequestException as exc:
        raise BackendError(f"Fallo de conexión con el backend: {exc}")
