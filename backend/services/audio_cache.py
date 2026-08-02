"""
services/audio_cache.py — Caché en disco del audio TTS (Hito 8)
===============================================================

Los niños repiten preguntas, y las frases fijas (`MENSAJE_SIN_INFORMACION`,
`FRASE_PRUEBA_VOZ`) se re-sintetizan enteras cada vez: es dinero regalado a
ElevenLabs. Esta caché guarda el mp3 ya sintetizado en disco, con clave
`hash(voz_id, modelo_tts, texto)`, y lo reutiliza cuando vuelve a hacer falta.

Es una caché deliberadamente simple (un fichero .mp3 por clave, sin expiración):
el audio de una frase dada con una voz dada NO cambia, así que no hay que
invalidar nada. Si el directorio no se puede escribir, se degrada a "sin caché"
(nunca rompe el TTS). Lo usa el streaming por frases de `chat_service`.
"""

import hashlib
import logging
from pathlib import Path

from backend import config

logger = logging.getLogger(__name__)

# Directorio de la caché (gitignored). Se crea a demanda.
_DIR = config.PROJECT_ROOT / "backend" / ".cache" / "tts"


def clave(voz_id: str, modelo_tts: str, texto: str) -> str:
    """Hash estable de (voz, modelo, texto). Mismo trío → mismo mp3, siempre."""
    crudo = f"{voz_id}\x00{modelo_tts}\x00{texto}".encode()
    return hashlib.sha256(crudo).hexdigest()


def _ruta(clave_hash: str) -> Path:
    return _DIR / f"{clave_hash}.mp3"


def obtener(clave_hash: str) -> bytes | None:
    """Devuelve el mp3 cacheado (bytes) o None si no está / no se puede leer."""
    ruta = _ruta(clave_hash)
    try:
        if ruta.is_file():
            return ruta.read_bytes()
    except OSError as exc:  # disco ilegible: se trata como fallo de caché, no error
        logger.warning("No se pudo leer la caché de audio (%s): %s", ruta.name, exc)
    return None


def guardar(clave_hash: str, audio_bytes: bytes) -> None:
    """Guarda el mp3 en la caché (escritura atómica). Un fallo NO rompe el TTS."""
    try:
        _DIR.mkdir(parents=True, exist_ok=True)
        ruta = _ruta(clave_hash)
        tmp = ruta.with_suffix(".mp3.tmp")
        tmp.write_bytes(audio_bytes)
        tmp.replace(ruta)
    except OSError as exc:
        logger.warning("No se pudo escribir la caché de audio: %s", exc)
