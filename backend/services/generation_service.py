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
estilo van en el prompt POSITIVO (ver STYLE_SUFFIX/FRAMING en personajes.py) y se
deja activo el safety checker de Replicate.

Salida de replicate.run: FLUX schnell devuelve una LISTA de FileOutput; Kontext
devuelve un único FileOutput. _salida_a_base64 maneja ambos casos.
"""

import base64

import replicate

from backend import config
from backend import personajes as personajes_cfg
from backend import ubicaciones as ubicaciones_cfg


def _salida_a_base64(output) -> str:
    """Lee la imagen devuelta por Replicate (lista o único FileOutput) a base64."""
    primera = output[0] if isinstance(output, (list, tuple)) else output
    return base64.b64encode(primera.read()).decode("utf-8")


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
    if personaje_id not in personajes_cfg.PROMPTS:
        raise ValueError(f"Personaje desconocido: '{personaje_id}'.")
    if ubicacion_id not in ubicaciones_cfg.UBICACIONES:
        raise ValueError(f"Ubicación desconocida: '{ubicacion_id}'.")
    _exigir_token()

    # Prompt final = personaje + ubicación + encuadre + estilo común.
    personaje = personajes_cfg.PROMPTS[personaje_id]["prompt"]
    ubicacion = ubicaciones_cfg.UBICACIONES[ubicacion_id]["prompt"]
    prompt = (
        f"{personaje}, {ubicacion}, "
        f"{personajes_cfg.FRAMING}, {personajes_cfg.STYLE_SUFFIX}"
    )

    output = replicate.run(
        config.REPLICATE_MODEL,
        input={
            "prompt": prompt,
            "aspect_ratio": config.IMG_ASPECT_RATIO,
            "output_format": config.IMG_OUTPUT_FORMAT,
            "num_outputs": 1,
            # FLUX schnell está destilado para 4 pasos: óptimo y ultra rápido.
            "num_inference_steps": config.IMG_NUM_STEPS,
        },
    )

    return {
        "success": True,
        "personaje_id": personaje_id,
        "ubicacion_id": ubicacion_id,
        "result_png_base64": _salida_a_base64(output),
    }


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

    Lanza ValueError (→ 400) si el personaje no existe o falta el token.
    """
    if personaje_id not in personajes_cfg.PROMPTS:
        raise ValueError(f"Personaje desconocido: '{personaje_id}'.")
    _exigir_token()

    personaje = personajes_cfg.PROMPTS[personaje_id]["prompt"]
    # Instrucción de edición: estilizar + añadir, manteniendo el sitio reconocible
    # y dejando ver el fondo (mismo criterio de encuadre que el modo predefinido).
    instruccion = (
        "Transform this photo into a 3D Pixar style animated movie scene. "
        f"Add {personaje} standing in the scene, placed naturally and a bit in the "
        "background so the surroundings stay clearly visible. "
        "Keep the room layout and main objects recognizable. "
        f"{personajes_cfg.STYLE_SUFFIX}"
    )

    # Pasamos la imagen como data URI (forma fiable de mandar bytes a Replicate).
    data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('utf-8')}"

    output = replicate.run(
        config.REPLICATE_EDIT_MODEL,
        input={
            "prompt": instruccion,
            "input_image": data_uri,
            "output_format": config.IMG_OUTPUT_FORMAT,
            # aspect_ratio por defecto "match_input_image": respeta la foto original.
        },
    )

    return {
        "success": True,
        "personaje_id": personaje_id,
        "ubicacion_id": "mi_foto",
        "result_png_base64": _salida_a_base64(output),
    }
