"""
backend/ubicaciones.py — Prompts de las ubicaciones
====================================================

Equivalente a personajes.py pero para el LUGAR donde aparece el personaje.
Cada ubicación aporta un fragmento de texto (en inglés) que describe la escena
de fondo. El servicio de generación lo combina con el personaje y el estilo.

Cualquier personaje puede ir en cualquier ubicación (combinación libre): eso es
lo divertido (p. ej. un t-rex en un laboratorio).

Los `id` (las claves) deben coincidir con los de frontend/ubicaciones.py.
"""

UBICACIONES = {
    "laboratorio": {
        "prompt": (
            "inside a bright science laboratory full of bubbling colorful potions, "
            "glass beakers and friendly machines"
        ),
    },
    "bosque_jurasico": {
        "prompt": (
            "in a lush prehistoric jurassic jungle with giant ferns, "
            "distant volcanoes and waterfalls"
        ),
    },
    "renacimiento": {
        "prompt": (
            "in a Renaissance artist workshop with paintings, sketches "
            "and wooden inventions"
        ),
    },
    "epoca_victoriana": {
        "prompt": (
            "on a foggy Victorian London street at night with glowing gas lamps "
            "and cobblestones"
        ),
    },
    # Extensible: añade aquí más lugares (espacio, antiguo Egipto, fondo marino,
    # castillo medieval...) y su tarjeta en frontend/ubicaciones.py con el mismo id.
}


# Nombre y emoji de cada ubicación (antes solo vivían en el frontend, en
# frontend-react/src/data/ubicaciones.ts). Se incluyen aquí para que el "seeding"
# a la BBDD deje el catálogo COMPLETO: a partir del Hito 6 el catálogo se lee de
# la tabla `ubicaciones` (vía ubicaciones_service) y el frontend lo consume por API.
NOMBRES = {
    "laboratorio":      "Laboratorio",
    "bosque_jurasico":  "Bosque del Jurásico",
    "renacimiento":     "Renacimiento",
    "epoca_victoriana": "Época Victoriana",
}
EMOJIS = {
    "laboratorio":      "🧪",
    "bosque_jurasico":  "🌋",
    "renacimiento":     "🎨",
    "epoca_victoriana": "🎩",
}
