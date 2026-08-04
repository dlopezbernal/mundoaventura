"""
services/generation_service.py — Generación con Replicate
==========================================================

Dos modos, ambos delegan la GPU a Replicate.com (no se genera nada en local):

  1) generar_escena(personaje, ubicacion)  — TEXTO → IMAGEN
     El niño elige una ubicación predefinida y un personaje. Construimos un único
     prompt (personaje + ubicación + encuadre + estilo) y lo manda a un modelo
     txt2img (por defecto FLUX schnell, rápido y barato).

  2) generar_en_foto(foto, personaje)       — IMAGEN → IMAGEN (edición)
     El niño sube una foto de su habitación. Un modelo de edición (FLUX Kontext)
     en UNA sola llamada: (a) estiliza la foto a Pixar 3D y (b) añade el personaje
     de forma coherente. Así el conjunto comparte estilo (no choca cartoon sobre
     foto real) y el modelo "intuye" dónde colocarlo.

Nota FLUX schnell: NO admite "negative prompt" ni "guidance"; la seguridad y el
estilo van en el prompt POSITIVO (ver STYLE_SUFFIX/FRAMING, ajustes editables desde
la pestaña "General" de configuración) y se deja activo el safety checker de Replicate.

Salida de replicate.run: FLUX schnell devuelve una LISTA de FileOutput; Kontext
devuelve un único FileOutput. _salida_a_base64 maneja ambos casos.

Orden del prompt (CLIP vs T5)
-----------------------------
FLUX codifica el prompt con DOS codificadores a la vez: CLIP (corto, trunca a ~77
tokens) y T5 (largo). Para que nada importante se pierda si CLIP recorta, montamos
el prompt de MÁS a MENOS importante: primero el SUJETO (personaje + ubicación), que
es lo que no puede faltar y entra dentro de CLIP, y al final el ENCUADRE y el ESTILO,
que si caen fuera de CLIP los sigue leyendo T5 y apenas afectan al resultado. Si el
prompt supera el límite de CLIP, _avisar_si_prompt_largo emite un warning (no es un
error: la imagen se genera igual).
"""

import base64
import logging
import re

from replicate.exceptions import ReplicateError

from backend import config, debug_log
from backend.services import (
    personajes_service,
    replicate_client,
    settings_service,
    ubicaciones_service,
)

logger = logging.getLogger(__name__)


def _primer_fichero(output):
    """FLUX schnell devuelve una LISTA de FileOutput; Kontext/recorte, uno único."""
    return output[0] if isinstance(output, (list, tuple)) else output


def _salida_a_base64(output) -> str:
    """Lee la imagen devuelta por Replicate (lista o único FileOutput) a base64."""
    return base64.b64encode(_primer_fichero(output).read()).decode("utf-8")


def _estimar_tokens(texto: str) -> int:
    """Estima (al alza) cuántos tokens ocupa el prompt.

    No tenemos el tokenizador exacto de CLIP a mano, así que aproximamos contando
    palabras y signos de puntuación (cada signo suele ser un token aparte). Es una
    estimación conservadora, suficiente para decidir si avisar de que CLIP truncará.
    """
    return len(re.findall(r"\w+|[^\w\s]", texto))


def _avisar_si_prompt_largo(prompt: str) -> None:
    """Avisa (warning, no error) si el prompt supera el límite de tokens de CLIP.

    FLUX seguirá generando la imagen: T5 lee el prompt completo. El aviso solo
    recuerda que el final del prompt (encuadre/estilo) puede quedar fuera de CLIP,
    razón por la que colocamos ahí lo MENOS crítico (ver docstring del módulo).
    """
    tokens = _estimar_tokens(prompt)
    limite = settings_service.get("CLIP_TOKEN_LIMIT")
    if tokens > limite:
        logger.warning(
            "El prompt (~%s tokens) supera el límite de CLIP (%s). CLIP truncará el "
            "final, pero T5 lo leerá completo. Lo importante va al principio, así que "
            "la imagen no debería verse afectada.",
            tokens,
            limite,
        )


def _exigir_token() -> None:
    if not config.REPLICATE_API_TOKEN:
        raise ValueError(
            "Falta REPLICATE_API_TOKEN en el .env. Crea un token en "
            "https://replicate.com/account/api-tokens y añádelo al .env."
        )


def generar_escena(personaje_id: str, ubicacion_id: str) -> dict:
    """Genera una imagen de `personaje_id` en `ubicacion_id` (ubicación predefinida).

    Lanza ValueError (→ 400 en el router) si el personaje/ubicación no existen o
    si falta el token de Replicate.
    """
    ficha_personaje = personajes_service.obtener(personaje_id)
    if ficha_personaje is None:
        raise ValueError(f"Personaje desconocido: '{personaje_id}'.")
    ficha_ubicacion = ubicaciones_service.obtener(ubicacion_id)
    if ficha_ubicacion is None:
        raise ValueError(f"Ubicación desconocida: '{ubicacion_id}'.")
    _exigir_token()

    # Prompt final, de MÁS a MENOS importante (ver docstring del módulo: CLIP vs T5):
    #   1) SUJETO     → personaje + ubicación (lo esencial, entra en CLIP).
    #   2) ENCUADRE   → FRAMING (cómo de lejos/grande sale el personaje).
    #   3) ESTILO     → STYLE_SUFFIX (look común; si CLIP lo recorta, T5 lo lee).
    personaje = ficha_personaje["prompt_imagen"]
    ubicacion = ficha_ubicacion["prompt_imagen"]
    prompt = (
        f"{personaje}, {ubicacion}, "
        f"{settings_service.get('FRAMING')}, {settings_service.get('STYLE_SUFFIX')}"
    )
    _avisar_si_prompt_largo(prompt)
    modelo = settings_service.get("REPLICATE_MODEL")
    debug_log.trazar_prompt(f"Replicate · escena ({modelo})", prompt=prompt)

    output = replicate_client.run(
        modelo,
        input={
            "prompt": prompt,
            "aspect_ratio": settings_service.get("IMG_ASPECT_RATIO"),
            "output_format": settings_service.get("IMG_OUTPUT_FORMAT"),
            "num_outputs": 1,
            # FLUX schnell está destilado para 4 pasos: óptimo y ultra rápido.
            "num_inference_steps": settings_service.get("IMG_NUM_STEPS"),
        },
        etiqueta="Replicate · escena",
    )

    return {
        "success": True,
        "personaje_id": personaje_id,
        "ubicacion_id": ubicacion_id,
        "result_png_base64": _salida_a_base64(output),
    }


def _generar_png_recorte(descripcion: str, ajuste_prompt: str, etiqueta: str) -> bytes:
    """Pipeline A1 compartido: FLUX sobre fondo liso + recorte → PNG TRANSPARENTE.

    `descripcion` es el prompt del sujeto (personaje o ubicación); `ajuste_prompt` es
    el nombre del ajuste con el encuadre (AVATAR_PROMPT / UBICACION_IMG_PROMPT). Dos
    pasos en Replicate: (1) FLUX dibuja sobre fondo plano; (2) el modelo de recorte
    (AVATAR_REMOVE_BG_MODEL) quita el fondo. Devuelve los bytes del PNG.
    """
    _exigir_token()

    # Paso 1: imagen sobre fondo plano. PNG (sin pérdidas antes de recortar).
    prompt = (
        f"{descripcion}, {settings_service.get(ajuste_prompt)}, "
        f"{settings_service.get('STYLE_SUFFIX')}"
    )
    _avisar_si_prompt_largo(prompt)
    modelo = settings_service.get("REPLICATE_MODEL")
    debug_log.trazar_prompt(f"Replicate · {etiqueta} ({modelo})", prompt=prompt)
    salida = replicate_client.run(
        modelo,
        input={
            "prompt": prompt,
            "aspect_ratio": settings_service.get("AVATAR_ASPECT_RATIO"),
            "output_format": "png",
            "num_outputs": 1,
            "num_inference_steps": settings_service.get("IMG_NUM_STEPS"),
        },
        etiqueta=f"Replicate · {etiqueta}",
    )
    base_bytes = _primer_fichero(salida).read()

    # Paso 2: quitar el fondo → PNG transparente. La imagen va como data URI en 'image'.
    modelo_bg = settings_service.get("AVATAR_REMOVE_BG_MODEL")
    data_uri = f"data:image/png;base64,{base64.b64encode(base_bytes).decode('utf-8')}"
    try:
        salida_bg = replicate_client.run(
            modelo_bg,
            input={"image": data_uri},
            etiqueta=f"Replicate · {etiqueta} recorte",
        )
    except ReplicateError as exc:
        # Causa típica: un modelo de la comunidad indicado SIN versión → Replicate
        # usa el endpoint de modelos oficiales y responde 404. Mensaje accionable
        # (→ 400 en el router) en vez del 500 genérico.
        raise ValueError(
            f"El modelo de recorte de fondo '{modelo_bg}' falló ({exc}). Si es un modelo "
            "de la comunidad, indícalo CON versión ('owner/model:hash'). Se ajusta en "
            "Admin → Imagen → AVATAR_REMOVE_BG_MODEL."
        ) from exc
    return _primer_fichero(salida_bg).read()


def generar_avatar(personaje_id: str) -> bytes:
    """Genera el AVATAR del carrusel de un personaje: un PNG TRANSPARENTE.

    FLUX dibuja un retrato del personaje (su `prompt_imagen` + AVATAR_PROMPT + estilo)
    sobre fondo liso y un modelo de recorte lo deja con transparencia. Lanza ValueError
    (→ 400) si el personaje no existe o falta el token de Replicate.
    """
    ficha = personajes_service.obtener(personaje_id)
    if ficha is None:
        raise ValueError(f"Personaje desconocido: '{personaje_id}'.")
    return _generar_png_recorte(ficha["prompt_imagen"], "AVATAR_PROMPT", "avatar retrato")


def generar_avatar_ubicacion(ubicacion_id: str) -> bytes:
    """Genera la IMAGEN del carrusel de una ubicación: un PNG TRANSPARENTE.

    Igual que el avatar del personaje pero con el encuadre propio de un lugar
    (UBICACION_IMG_PROMPT). Lanza ValueError (→ 400) si la ubicación no existe o
    falta el token de Replicate.
    """
    ficha = ubicaciones_service.obtener(ubicacion_id)
    if ficha is None:
        raise ValueError(f"Ubicación desconocida: '{ubicacion_id}'.")
    return _generar_png_recorte(ficha["prompt_imagen"], "UBICACION_IMG_PROMPT", "imagen ubicación")


def generar_en_foto(
    image_bytes: bytes,
    personaje_id: str,
    mime: str = "image/png",
) -> dict:
    """Estiliza la foto subida a Pixar 3D y añade el personaje, en una sola llamada.

    Parámetros
    ----------
    image_bytes : bytes  contenido de la foto subida por el niño.
    personaje_id : str   personaje a añadir (debe existir en PROMPTS).
    mime : str           tipo MIME de la foto (image/jpeg, image/png...).

    PRIVACIDAD (Hito 9): la foto se procesa SOLO EN MEMORIA. `image_bytes` llega del
    endpoint (leído con tope de tamaño, sin tocar disco), se convierte a data URI y se
    envía a Replicate; NUNCA se escribe en disco ni se guarda en la BBDD. Al terminar la
    función, los bytes quedan fuera de alcance y se recolectan. Ver docs/PRIVACIDAD.md.

    Lanza ValueError (→ 400) si el personaje no existe o falta el token.
    """
    ficha_personaje = personajes_service.obtener(personaje_id)
    if ficha_personaje is None:
        raise ValueError(f"Personaje desconocido: '{personaje_id}'.")
    _exigir_token()

    personaje = ficha_personaje["prompt_imagen"]
    # Instrucción de edición, también de MÁS a MENOS importante (CLIP vs T5):
    # primero QUÉ hacer y a QUIÉN añadir, y al final el estilo común (STYLE_SUFFIX),
    # que es lo que mejor tolera caer fuera de CLIP.
    instruccion = (
        "Transform this photo into a 3D Pixar style animated movie scene. "
        f"Add {personaje} standing in the scene, placed naturally and a bit in the "
        "background so the surroundings stay clearly visible. "
        "Keep the room layout and main objects recognizable. "
        f"{settings_service.get('STYLE_SUFFIX')}"
    )
    _avisar_si_prompt_largo(instruccion)
    modelo_edicion = settings_service.get("REPLICATE_EDIT_MODEL")
    debug_log.trazar_prompt(
        f"Replicate · edición foto ({modelo_edicion})",
        prompt=instruccion,
    )

    # Pasamos la imagen como data URI (forma fiable de mandar bytes a Replicate).
    data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('utf-8')}"

    output = replicate_client.run(
        modelo_edicion,
        input={
            "prompt": instruccion,
            "input_image": data_uri,
            "output_format": settings_service.get("IMG_OUTPUT_FORMAT"),
            # aspect_ratio por defecto "match_input_image": respeta la foto original.
        },
        etiqueta="Replicate · edición foto",
    )

    return {
        "success": True,
        "personaje_id": personaje_id,
        "ubicacion_id": "mi_foto",
        "result_png_base64": _salida_a_base64(output),
    }
