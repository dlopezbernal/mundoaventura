"""
services/settings_service.py — Ajustes vigentes (SQLite) con caché y defaults
=============================================================================

El CORAZÓN del menú de configuración. Hasta ahora cada ajuste era una constante de
`config.py` congelada al importar; para poder editarlos EN CALIENTE (sin reiniciar)
los leemos a través de este servicio:

  1) Devuelve el valor VIGENTE desde la BBDD (SQLite), con caché en memoria.
  2) Si aún no hay nada en la BBDD, cae al VALOR POR DEFECTO (el actual de
     `config.py`). Así, con la BBDD vacía, la app se comporta EXACTAMENTE como hoy
     (compatibilidad hacia atrás).
  3) Al guardar (`set_many`) valida, persiste e invalida la caché: el cambio surte
     efecto en la siguiente petición, sin reiniciar el backend.

Los SECRETOS (claves API) NO se gestionan aquí: viven en el `.env` (ver Hito 2).

`_SPEC` es el registro central de "qué se configura": para cada clave, su tipo,
categoría, valor por defecto (tomado de `config.py`), si cambiarla obliga a
REINDEXAR ChromaDB, un texto de ayuda en español y, si aplica, rango/opciones para
validar. Esta especificación alimentará también la pantalla de ajustes (Hito 3).
"""

from datetime import datetime
from typing import Any

from sqlmodel import select

from backend import config, db
from backend.models import Setting

# Categorías (para agrupar los ajustes en la UI del Hito 3).
CAT_IMAGEN = "imagen"
CAT_RAG = "rag"
CAT_CHUNKING = "chunking"
CAT_LLM = "llm"
CAT_VOZ = "voz"

# Modos válidos del Evaluator (mismo criterio que config.py).
_MODOS_EVALUATOR = ("umbral", "llm", "hibrido")


# ---------------------------------------------------------------------------
# Registro central de ajustes editables (default = valor actual de config.py)
# ---------------------------------------------------------------------------
_SPEC: dict[str, dict[str, Any]] = {
    # --- Imagen / generación ---
    "REPLICATE_MODEL": {
        "categoria": CAT_IMAGEN, "tipo": "str", "default": config.REPLICATE_MODEL,
        "ayuda": "Modelo de texto-a-imagen de Replicate para la escena.",
    },
    "REPLICATE_EDIT_MODEL": {
        "categoria": CAT_IMAGEN, "tipo": "str", "default": config.REPLICATE_EDIT_MODEL,
        "ayuda": "Modelo de edición para el modo 'Usar mi foto'.",
    },
    "IMG_ASPECT_RATIO": {
        "categoria": CAT_IMAGEN, "tipo": "str", "default": config.IMG_ASPECT_RATIO,
        "opciones": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "ayuda": "Proporción de la imagen generada.",
    },
    "IMG_OUTPUT_FORMAT": {
        "categoria": CAT_IMAGEN, "tipo": "str", "default": config.IMG_OUTPUT_FORMAT,
        "opciones": ["png", "jpg", "webp"],
        "ayuda": "Formato del archivo de imagen.",
    },
    "IMG_NUM_STEPS": {
        "categoria": CAT_IMAGEN, "tipo": "int", "default": config.IMG_NUM_STEPS,
        "min": 1, "max": 50,
        "ayuda": "Pasos de difusión. FLUX schnell rinde óptimo con 4 (su máximo).",
    },
    "CLIP_TOKEN_LIMIT": {
        "categoria": CAT_IMAGEN, "tipo": "int", "default": config.CLIP_TOKEN_LIMIT,
        "min": 1, "max": 512,
        "ayuda": "Límite de tokens de CLIP; si el prompt lo supera, solo se avisa.",
    },
    # --- RAG / Evaluator ---
    "EVALUATOR_MODE": {
        "categoria": CAT_RAG, "tipo": "str", "default": config.EVALUATOR_MODE,
        "opciones": list(_MODOS_EVALUATOR),
        "ayuda": "Cómo se decide RAG vs GENERAL: umbral (gratis), llm (juez) o hibrido.",
    },
    "EVALUATOR_UMBRAL_BAJO": {
        "categoria": CAT_RAG, "tipo": "float", "default": config.EVALUATOR_UMBRAL_BAJO,
        "min": 0.0, "max": 2.0, "paso": 0.01,
        "ayuda": "Distancia coseno (0=idéntico, 2=opuesto). ≤ BAJO ⇒ RAG seguro.",
    },
    "EVALUATOR_UMBRAL_ALTO": {
        "categoria": CAT_RAG, "tipo": "float", "default": config.EVALUATOR_UMBRAL_ALTO,
        "min": 0.0, "max": 2.0, "paso": 0.01,
        "ayuda": "Distancia coseno (0=idéntico, 2=opuesto). ≥ ALTO ⇒ GENERAL.",
    },
    "RAG_TOP_K": {
        "categoria": CAT_RAG, "tipo": "int", "default": config.RAG_TOP_K,
        "min": 1, "max": 20,
        "ayuda": "Cuántas fichas recupera ChromaDB por pregunta.",
    },
    # --- Chunking (cambiarlo obliga a REINDEXAR) ---
    "CHUNK_SIZE": {
        "categoria": CAT_CHUNKING, "tipo": "int", "default": config.CHUNK_SIZE,
        "min": 100, "max": 4000, "requires_reindex": True,
        "ayuda": "Tamaño de cada fragmento (caracteres). Cambiarlo exige reindexar.",
    },
    "CHUNK_OVERLAP": {
        "categoria": CAT_CHUNKING, "tipo": "int", "default": config.CHUNK_OVERLAP,
        "min": 0, "max": 1000, "requires_reindex": True,
        "ayuda": "Caracteres que se repiten entre fragmentos. Cambiarlo exige reindexar.",
    },
    "CHROMA_COLLECTION": {
        "categoria": CAT_CHUNKING, "tipo": "str", "default": config.CHROMA_COLLECTION,
        "requires_reindex": True,
        "ayuda": "Nombre de la colección de ChromaDB. Cambiarlo exige reindexar.",
    },
    # --- LLM ---
    "REPLICATE_LLM_MODEL": {
        "categoria": CAT_LLM, "tipo": "str", "default": config.REPLICATE_LLM_MODEL,
        "ayuda": "Modelo de lenguaje (Replicate) que responde como el personaje.",
    },
    "LLM_MAX_TOKENS": {
        "categoria": CAT_LLM, "tipo": "int", "default": config.LLM_MAX_TOKENS,
        "min": 16, "max": 2000,
        "ayuda": "Longitud máxima de la respuesta del LLM (en tokens).",
    },
    # --- Voz ---
    "ELEVENLABS_STT_MODEL": {
        "categoria": CAT_VOZ, "tipo": "str", "default": config.ELEVENLABS_STT_MODEL,
        "ayuda": "Modelo de transcripción (voz→texto) de ElevenLabs.",
    },
    "ELEVENLABS_TTS_MODEL": {
        "categoria": CAT_VOZ, "tipo": "str", "default": config.ELEVENLABS_TTS_MODEL,
        "ayuda": "Modelo de síntesis (texto→voz) de ElevenLabs.",
    },
    "TTS_OUTPUT_FORMAT": {
        "categoria": CAT_VOZ, "tipo": "str", "default": config.TTS_OUTPUT_FORMAT,
        "ayuda": "Formato del audio de la respuesta (mp3).",
    },
    "STT_LANG": {
        "categoria": CAT_VOZ, "tipo": "str", "default": config.STT_LANG,
        "ayuda": "Idioma de la transcripción (la pregunta del niño).",
    },
}


# ---------------------------------------------------------------------------
# Caché en memoria (clave → valor tipado). Se carga de la BBDD la 1ª vez.
# ---------------------------------------------------------------------------
_cache: dict[str, Any] | None = None


def _coerce(tipo: str, raw: Any) -> Any:
    """Convierte un valor (normalmente texto de la BBDD) a su tipo Python."""
    if tipo == "int":
        return int(raw)
    if tipo == "float":
        return float(raw)
    if tipo == "bool":
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    return str(raw)


def _serialize(tipo: str, valor: Any) -> str:
    """Convierte un valor Python a texto para guardarlo en la BBDD."""
    if tipo == "bool":
        return "true" if valor else "false"
    return str(valor)


def _ensure_cache() -> dict[str, Any]:
    """Carga (la 1ª vez) los ajustes guardados en la BBDD a la caché en memoria."""
    global _cache
    if _cache is None:
        db.init_db()
        valores: dict[str, Any] = {}
        with db.get_session() as sesion:
            for fila in sesion.exec(select(Setting)).all():
                if fila.clave in _SPEC:  # ignora claves obsoletas que no estén en el spec
                    valores[fila.clave] = _coerce(_SPEC[fila.clave]["tipo"], fila.valor)
        _cache = valores
    return _cache


def get(clave: str) -> Any:
    """Devuelve el valor VIGENTE de un ajuste (BBDD si existe; si no, el default).

    Lanza KeyError si la clave no está en el registro `_SPEC`.
    """
    if clave not in _SPEC:
        raise KeyError(f"Ajuste desconocido: '{clave}'.")
    cache = _ensure_cache()
    if clave in cache:
        return cache[clave]
    return _SPEC[clave]["default"]


def _coerce_y_validar(clave: str, spec: dict[str, Any], valor: Any) -> Any:
    """Convierte al tipo del ajuste y valida rango/opciones. Lanza ValueError."""
    try:
        val = _coerce(spec["tipo"], valor)
    except (TypeError, ValueError):
        raise ValueError(f"'{clave}' debe ser de tipo {spec['tipo']} (recibido: {valor!r}).")

    if "opciones" in spec and val not in spec["opciones"]:
        raise ValueError(f"'{clave}' debe ser uno de {spec['opciones']} (recibido: {val!r}).")
    if "min" in spec and val < spec["min"]:
        raise ValueError(f"'{clave}' no puede ser menor que {spec['min']} (recibido: {val}).")
    if "max" in spec and val > spec["max"]:
        raise ValueError(f"'{clave}' no puede ser mayor que {spec['max']} (recibido: {val}).")
    return val


def _validar_coherencia_umbrales(limpios: dict[str, Any]) -> None:
    """Comprueba el invariante 0 ≤ BAJO ≤ ALTO ≤ 2 usando los valores resultantes.

    Toma el valor propuesto si viene en el cambio, o el vigente en caso contrario,
    para validar la combinación FINAL (no solo el campo que se toca).
    """
    bajo = limpios.get("EVALUATOR_UMBRAL_BAJO", get("EVALUATOR_UMBRAL_BAJO"))
    alto = limpios.get("EVALUATOR_UMBRAL_ALTO", get("EVALUATOR_UMBRAL_ALTO"))
    if bajo > alto:
        raise ValueError(
            f"El umbral BAJO ({bajo}) no puede ser mayor que el ALTO ({alto}): "
            "la distancia coseno va de 0 (idéntico) a 2 (opuesto), y BAJO ≤ ALTO."
        )


def set_many(cambios: dict[str, Any]) -> list[str]:
    """Valida y guarda varios ajustes; aplica en caliente (invalida la caché).

    Devuelve la lista de ajustes cambiados que REQUIEREN REINDEXAR ChromaDB (los de
    chunking): el llamador puede avisar al usuario. Lanza ValueError si algún valor
    es inválido (el router lo mapea a HTTP 400) y en ese caso NO guarda nada.
    """
    if not cambios:
        return []

    # 1) Validar TODO antes de tocar la BBDD (o se guarda todo, o nada).
    limpios: dict[str, Any] = {}
    for clave, valor in cambios.items():
        if clave not in _SPEC:
            raise ValueError(f"Ajuste desconocido: '{clave}'.")
        limpios[clave] = _coerce_y_validar(clave, _SPEC[clave], valor)
    _validar_coherencia_umbrales(limpios)

    # 2) Persistir (upsert) y recoger los que exigen reindexar.
    db.init_db()
    reindex: list[str] = []
    with db.get_session() as sesion:
        for clave, val in limpios.items():
            spec = _SPEC[clave]
            fila = sesion.get(Setting, clave)
            serial = _serialize(spec["tipo"], val)
            if fila is None:
                fila = Setting(clave=clave, valor=serial, tipo=spec["tipo"])
            else:
                fila.valor = serial
                fila.actualizado_en = datetime.utcnow()
            sesion.add(fila)
            if spec.get("requires_reindex"):
                reindex.append(clave)
        sesion.commit()

    # 3) Aplicar en caliente: refrescar la caché en memoria.
    cache = _ensure_cache()
    cache.update(limpios)
    return reindex


def seed() -> int:
    """Vuelca a la BBDD los ajustes que aún no existan (con su valor por defecto).

    Idempotente: solo inserta las claves ausentes, nunca pisa un valor ya guardado.
    Devuelve cuántas se insertaron. Se llama al arrancar (ver main.py). `get()` NO
    depende de esto (cae al default), pero el seeding deja la BBDD poblada para que
    la UI muestre y edite todos los ajustes.
    """
    global _cache
    db.init_db()
    insertados = 0
    with db.get_session() as sesion:
        for clave, spec in _SPEC.items():
            if sesion.get(Setting, clave) is None:
                sesion.add(
                    Setting(
                        clave=clave,
                        valor=_serialize(spec["tipo"], spec["default"]),
                        tipo=spec["tipo"],
                    )
                )
                insertados += 1
        sesion.commit()
    _cache = None  # invalidar: se recargará con lo recién sembrado
    return insertados


def exportar() -> list[dict[str, Any]]:
    """Devuelve todos los ajustes con su valor vigente y metadatos (para GET /api/config)."""
    salida: list[dict[str, Any]] = []
    for clave, spec in _SPEC.items():
        entrada: dict[str, Any] = {
            "clave": clave,
            "valor": get(clave),
            "tipo": spec["tipo"],
            "categoria": spec["categoria"],
            "requiere_reindex": bool(spec.get("requires_reindex", False)),
            "ayuda": spec.get("ayuda", ""),
        }
        for extra in ("min", "max", "paso", "opciones"):
            if extra in spec:
                entrada[extra] = spec[extra]
        salida.append(entrada)
    return salida
