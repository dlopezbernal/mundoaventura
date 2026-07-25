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
from backend import personajes as personajes_cfg
from backend.models import Setting

# Categorías (para agrupar los ajustes en la UI del Hito 3).
CAT_IMAGEN = "imagen"
CAT_RAG = "rag"
CAT_CHUNKING = "chunking"
CAT_LLM = "llm"
CAT_VOZ = "voz"
CAT_PROMPTS = "prompts"
CAT_GENERAL = "general"
# Estilo visual COMÚN a personajes y ubicaciones (pestaña "General" de la UI):
# antes constantes fijas en personajes.py, ahora editables sin tocar código.
CAT_ESTILO_IMAGEN = "estilo_imagen"

# Modos válidos del Evaluator (mismo criterio que config.py).
_MODOS_EVALUATOR = ("umbral", "llm", "hibrido")

# ---------------------------------------------------------------------------
# Prompts de sistema por defecto (antes hardcodeados en rag_service.py)
# ---------------------------------------------------------------------------
# Se guardan como ajustes editables (categoría "prompts") para poder cambiar el
# "carácter" de los personajes (tono, edad, "responde en español", "no inventes")
# SIN tocar Python. Van EN INGLÉS a propósito (Llama 3 obedece mejor en inglés);
# solo la RESPUESTA se pide en español. Variables admitidas (se sustituyen en
# runtime): {nombre} (personaje), {fichas} (contexto recuperado), {pregunta}.
_PROMPT_RAG_SYSTEM = (
    "You are {nombre}, speaking in the first person to a child aged 8 to 12. "
    "ALWAYS reply in Spanish, in a short (2-4 sentences), cheerful and simple "
    "way. Use ONLY the information in the cards I give you. If the answer is not "
    "in the cards, kindly say that you do not know that, without making anything "
    "up. Never break character. "
    "Do NOT start your answer with a greeting or by introducing yourself "
    "(no 'Hola', no 'Como [name]'); answer directly as if continuing a conversation."
)
_PROMPT_RAG_USER = (
    "Cards with data about me:\n{fichas}\n\n"
    "Child's question: {pregunta}\n\n"
    "Your answer (in the first person, in Spanish):"
)
_PROMPT_GENERAL_SYSTEM = (
    "You are {nombre}, speaking in the first person to a child aged 8 to 12. "
    "ALWAYS reply in Spanish, in a short (2-4 sentences), cheerful and simple "
    "way, never breaking character. You have no data cards for this question: "
    "answer with your own general knowledge, and if you do not know, kindly say "
    "so without making anything up. "
    "Do NOT start your answer with a greeting or by introducing yourself "
    "(no 'Hola', no 'Como [name]'); answer directly as if continuing a conversation."
)
_PROMPT_GENERAL_USER = (
    "Child's question: {pregunta}\n\nYour answer (in the first person, in Spanish):"
)
_PROMPT_EVALUATOR_SYSTEM = (
    "You are a strict evaluator for a RAG system. Your only task is to decide "
    "whether the context cards contain information to answer the question. "
    "Reply with EXACTLY one word, no explanation: 'YES' if the cards are "
    "relevant and sufficient, or 'NO' if they are not."
)
_PROMPT_EVALUATOR_USER = (
    "Context cards:\n{fichas}\n\n"
    "Question: {pregunta}\n\n"
    "Are the cards relevant to answer it? Reply only YES or NO:"
)
# A diferencia de los PROMPT_* de arriba (instrucciones EN INGLÉS para el LLM), este
# es el texto FINAL que lee el niño: va directamente en español, sin pasar por
# ningún modelo. Solo se usa si PERMITIR_CONOCIMIENTO_GENERAL está desactivado.
_MENSAJE_SIN_INFORMACION = (
    "No tengo esa información entre mis documentos. ¡Pregúntame otra cosa, "
    "seguro que sé algo interesante!"
)


# ---------------------------------------------------------------------------
# Registro central de ajustes editables (default = valor actual de config.py)
# ---------------------------------------------------------------------------
_SPEC: dict[str, dict[str, Any]] = {
    # --- Imagen / generación ---
    "REPLICATE_MODEL": {
        "categoria": CAT_IMAGEN,
        "tipo": "str",
        "default": config.REPLICATE_MODEL,
        "ayuda": "Modelo de texto-a-imagen de Replicate para la escena.",
    },
    "REPLICATE_EDIT_MODEL": {
        "categoria": CAT_IMAGEN,
        "tipo": "str",
        "default": config.REPLICATE_EDIT_MODEL,
        "ayuda": "Modelo de edición para el modo 'Usar mi foto'.",
    },
    "IMG_ASPECT_RATIO": {
        "categoria": CAT_IMAGEN,
        "tipo": "str",
        "default": config.IMG_ASPECT_RATIO,
        "opciones": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "ayuda": "Proporción de la imagen generada.",
    },
    "IMG_OUTPUT_FORMAT": {
        "categoria": CAT_IMAGEN,
        "tipo": "str",
        "default": config.IMG_OUTPUT_FORMAT,
        "opciones": ["png", "jpg", "webp"],
        "ayuda": "Formato del archivo de imagen.",
    },
    "IMG_NUM_STEPS": {
        "categoria": CAT_IMAGEN,
        "tipo": "int",
        "default": config.IMG_NUM_STEPS,
        "min": 1,
        "max": 50,
        "ayuda": "Pasos de difusión. FLUX schnell rinde óptimo con 4 (su máximo).",
    },
    "CLIP_TOKEN_LIMIT": {
        "categoria": CAT_IMAGEN,
        "tipo": "int",
        "default": config.CLIP_TOKEN_LIMIT,
        "min": 1,
        "max": 512,
        "ayuda": "Límite de tokens de CLIP; si el prompt lo supera, solo se avisa.",
    },
    # --- Estilo de imagen (pestaña "General"): común a TODOS los personajes y
    # ubicaciones, para que la imagen final se vea coherente (ver generation_service).
    "STYLE_SUFFIX": {
        "categoria": CAT_ESTILO_IMAGEN,
        "tipo": "str",
        "default": personajes_cfg.STYLE_SUFFIX,
        "multilinea": True,
        "ayuda": "Estilo visual común a TODAS las imágenes (personaje + ubicación): "
        "render 3D Pixar, colores, seguridad para niños. Va en POSITIVO al final del "
        "prompt (FLUX schnell no admite negative prompt). Se usa en 'generar escena' "
        "y en 'usar mi foto'.",
    },
    "FRAMING": {
        "categoria": CAT_ESTILO_IMAGEN,
        "tipo": "str",
        "default": personajes_cfg.FRAMING,
        "multilinea": True,
        "ayuda": "Encuadre de la escena predefinida (qué tan cerca/lejos sale el "
        "personaje). Solo se usa en 'generar escena' (personaje + ubicación); el modo "
        "'usar mi foto' respeta el encuadre de la foto original.",
    },
    # --- RAG / Evaluator ---
    "EVALUATOR_MODE": {
        "categoria": CAT_RAG,
        "tipo": "str",
        "default": config.EVALUATOR_MODE,
        "opciones": list(_MODOS_EVALUATOR),
        "ayuda": "Cómo se decide RAG vs GENERAL: umbral (gratis), llm (juez) o hibrido.",
    },
    "PERMITIR_CONOCIMIENTO_GENERAL": {
        "categoria": CAT_RAG,
        "tipo": "bool",
        "default": config.PERMITIR_CONOCIMIENTO_GENERAL,
        "ayuda": "Si las fichas no sirven (origen GENERAL), ¿el personaje responde con "
        'su conocimiento propio (llamada extra al LLM) o con un mensaje fijo de "no lo '
        'sé" sin llamar a ningún modelo? Desactívalo para un chat anclado solo a tus '
        "documentos (MENSAJE_SIN_INFORMACION, más abajo).",
    },
    "EVALUATOR_UMBRAL_BAJO": {
        "categoria": CAT_RAG,
        "tipo": "float",
        "default": config.EVALUATOR_UMBRAL_BAJO,
        "min": 0.0,
        "max": 2.0,
        "paso": 0.01,
        "ayuda": "Distancia coseno (0=idéntico, 2=opuesto). ≤ BAJO ⇒ RAG seguro.",
    },
    "EVALUATOR_UMBRAL_ALTO": {
        "categoria": CAT_RAG,
        "tipo": "float",
        "default": config.EVALUATOR_UMBRAL_ALTO,
        "min": 0.0,
        "max": 2.0,
        "paso": 0.01,
        "ayuda": "Distancia coseno (0=idéntico, 2=opuesto). ≥ ALTO ⇒ GENERAL.",
    },
    "RAG_TOP_K": {
        "categoria": CAT_RAG,
        "tipo": "int",
        "default": config.RAG_TOP_K,
        "min": 1,
        "max": 20,
        "ayuda": "Cuántas fichas recupera ChromaDB por pregunta.",
    },
    # --- Chunking (cambiarlo obliga a REINDEXAR) ---
    "CHUNK_SIZE": {
        "categoria": CAT_CHUNKING,
        "tipo": "int",
        "default": config.CHUNK_SIZE,
        "min": 100,
        "max": 4000,
        "requires_reindex": True,
        "ayuda": "Tamaño de cada fragmento (caracteres). Cambiarlo exige reindexar.",
    },
    "CHUNK_OVERLAP": {
        "categoria": CAT_CHUNKING,
        "tipo": "int",
        "default": config.CHUNK_OVERLAP,
        "min": 0,
        "max": 1000,
        "requires_reindex": True,
        "ayuda": "Caracteres que se repiten entre fragmentos. Cambiarlo exige reindexar.",
    },
    "CHROMA_COLLECTION": {
        "categoria": CAT_CHUNKING,
        "tipo": "str",
        "default": config.CHROMA_COLLECTION,
        "requires_reindex": True,
        "ayuda": "Nombre de la colección de ChromaDB. Cambiarlo exige reindexar.",
    },
    # --- LLM ---
    "REPLICATE_LLM_MODEL": {
        "categoria": CAT_LLM,
        "tipo": "str",
        "default": config.REPLICATE_LLM_MODEL,
        "ayuda": "Modelo de lenguaje (Replicate) que responde como el personaje.",
    },
    "LLM_MAX_TOKENS": {
        "categoria": CAT_LLM,
        "tipo": "int",
        "default": config.LLM_MAX_TOKENS,
        "min": 16,
        "max": 2000,
        "ayuda": "Longitud máxima de la respuesta del LLM (en tokens).",
    },
    "LLM_TEMPERATURE": {
        "categoria": CAT_LLM,
        "tipo": "float",
        "default": 0.3,
        "min": 0.0,
        "max": 1.0,
        "paso": 0.05,
        "ayuda": "Creatividad de la respuesta (0=predecible, 1=creativa). El juez "
        "del Evaluator siempre usa 0.",
    },
    # --- Voz ---
    "ELEVENLABS_STT_MODEL": {
        "categoria": CAT_VOZ,
        "tipo": "str",
        "default": config.ELEVENLABS_STT_MODEL,
        "ayuda": "Modelo de transcripción (voz→texto) de ElevenLabs.",
    },
    "ELEVENLABS_TTS_MODEL": {
        "categoria": CAT_VOZ,
        "tipo": "str",
        "default": config.ELEVENLABS_TTS_MODEL,
        "ayuda": "Modelo de síntesis (texto→voz) de ElevenLabs.",
    },
    "TTS_OUTPUT_FORMAT": {
        "categoria": CAT_VOZ,
        "tipo": "str",
        "default": config.TTS_OUTPUT_FORMAT,
        "ayuda": "Formato del audio de la respuesta (mp3).",
    },
    "STT_LANG": {
        "categoria": CAT_VOZ,
        "tipo": "str",
        "default": config.STT_LANG,
        "ayuda": "Idioma de la transcripción (la pregunta del niño).",
    },
    # --- Prompts de sistema (editables sin tocar código) ---
    # Van en inglés (Llama 3 obedece mejor); la respuesta se pide en español dentro
    # del propio texto. Variables: {nombre}, {fichas}, {pregunta}. multilinea → la UI
    # los pinta como área de texto grande.
    "PROMPT_RAG_SYSTEM": {
        "categoria": CAT_PROMPTS,
        "tipo": "str",
        "default": _PROMPT_RAG_SYSTEM,
        "multilinea": True,
        "ayuda": "Reglas del personaje cuando responde CON documentos (RAG). Variable: {nombre}.",
    },
    "PROMPT_RAG_USER": {
        "categoria": CAT_PROMPTS,
        "tipo": "str",
        "default": _PROMPT_RAG_USER,
        "multilinea": True,
        "ayuda": "Mensaje con las fichas y la pregunta (RAG). Variables: {fichas}, {pregunta}.",
    },
    "PROMPT_GENERAL_SYSTEM": {
        "categoria": CAT_PROMPTS,
        "tipo": "str",
        "default": _PROMPT_GENERAL_SYSTEM,
        "multilinea": True,
        "ayuda": "Reglas del personaje cuando responde SIN documentos (conocimiento propio). Variable: {nombre}.",
    },
    "PROMPT_GENERAL_USER": {
        "categoria": CAT_PROMPTS,
        "tipo": "str",
        "default": _PROMPT_GENERAL_USER,
        "multilinea": True,
        "ayuda": "Mensaje con la pregunta (sin fichas). Variable: {pregunta}.",
    },
    "PROMPT_EVALUATOR_SYSTEM": {
        "categoria": CAT_PROMPTS,
        "tipo": "str",
        "default": _PROMPT_EVALUATOR_SYSTEM,
        "multilinea": True,
        "ayuda": "Reglas del juez que decide si las fichas sirven (responde YES/NO).",
    },
    "PROMPT_EVALUATOR_USER": {
        "categoria": CAT_PROMPTS,
        "tipo": "str",
        "default": _PROMPT_EVALUATOR_USER,
        "multilinea": True,
        "ayuda": "Mensaje del juez con fichas y pregunta. Variables: {fichas}, {pregunta}.",
    },
    "MENSAJE_SIN_INFORMACION": {
        "categoria": CAT_PROMPTS,
        "tipo": "str",
        "default": _MENSAJE_SIN_INFORMACION,
        "multilinea": True,
        "ayuda": "Mensaje FIJO en ESPAÑOL (no una instrucción al LLM) que dice el "
        "personaje cuando no tiene información y PERMITIR_CONOCIMIENTO_GENERAL está "
        "desactivado. No se llama a ningún modelo para generarlo. Variable opcional: "
        "{nombre}.",
    },
    # --- General ---
    "DEBUG": {
        "categoria": CAT_GENERAL,
        "tipo": "bool",
        "default": config.DEBUG,
        "ayuda": "Modo desarrollo: imprime trazas en la consola del backend "
        "(origen de la respuesta y prompts) Y, en el chat, muestra el desplegable "
        "'📚 ¿De dónde lo he sacado?' con las fichas cuando la respuesta es RAG. "
        "Déjalo desactivado para el niño.",
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
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"'{clave}' debe ser de tipo {spec['tipo']} (recibido: {valor!r})."
        ) from exc

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

    # Si cambió DEBUG, resincronizar el nivel del logger `backend` para que el
    # toggle en caliente encienda/apague también las trazas por consola sin
    # reiniciar (import perezoso para no crear un ciclo con logging_config).
    if "DEBUG" in limpios:
        from backend import logging_config

        logging_config.aplicar_nivel_debug()

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
        for extra in ("min", "max", "paso", "opciones", "multilinea"):
            if extra in spec:
                entrada[extra] = spec[extra]
        salida.append(entrada)
    return salida


def rellenar(plantilla: str, **variables: str) -> str:
    """Sustituye {clave} por su valor en una plantilla de prompt.

    Usa reemplazo literal (no str.format) para que un carácter suelto '{' o '}' en
    un prompt editado por el usuario no rompa nada. Las variables ausentes en la
    plantilla simplemente no se usan.
    """
    texto = plantilla
    for clave, valor in variables.items():
        texto = texto.replace("{" + clave + "}", valor)
    return texto
