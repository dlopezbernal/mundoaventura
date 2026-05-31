"""
backend/personajes.py — Prompts de los personajes
==================================================

Cada personaje aporta un fragmento de texto (en inglés, que es lo que mejor
entienden los modelos de difusión) que describe sus rasgos. El servicio de
generación combina ese fragmento con la UBICACIÓN elegida (ver ubicaciones.py)
y con el STYLE_SUFFIX común, y lo manda a Replicate como un único prompt.

Ya NO usamos IP-Adapter ni imágenes base: con texto-a-imagen en la nube basta
con describir bien al personaje y el estilo deseado.
"""

# Estilo visual común a TODAS las imágenes. Es lo que da coherencia entre
# personajes y ubicaciones: render 3D tipo Pixar/DreamWorks, colorido y amable.
# La seguridad para niños ("friendly, cute, safe for kids, not scary") va aquí,
# en POSITIVO, porque FLUX schnell no admite "negative prompt".
STYLE_SUFFIX = (
    "3D Pixar style render, colorful, warm cinematic lighting, "
    "friendly, cute, adorable, safe for kids, not scary, "
    "high quality, highly detailed"
)

# ENCUADRE (cómo de lejos/grande sale el personaje en la escena predefinida).
# FLUX schnell no tiene un parámetro numérico de "distancia": el encuadre se
# controla con PALABRAS. Sube/baja la sensación de lejanía editando este texto:
#   - más lejos / más fondo:  "wide shot", "small in the frame", "far away"
#   - más cerca / primer plano: "close-up", "the character fills the frame"
# Segunda palanca: IMG_ASPECT_RATIO en el .env (16:9 muestra más entorno que 1:1).
FRAMING = (
    "wide establishing shot, full body visible, "
    "the character is small in the frame and a bit far away, "
    "lots of background and environment visible around, plenty of empty space"
)

PROMPTS = {
    "triceratops": {
        "prompt": (
            "a cute triceratops dinosaur with chubby friendly proportions, "
            "big expressive eyes, smooth colorful skin, happy smiling, "
            "rounded horns"
        ),
    },
    "t-rex": {
        "prompt": (
            "a cute t-rex dinosaur with chubby friendly proportions, "
            "big expressive blue eyes, orange and brown skin, happy smiling, "
            "small arms"
        ),
    },
    "leonardo_da_vinci": {
        "prompt": (
            "Leonardo da Vinci as a kind wise old man, big expressive eyes, "
            "detailed renaissance tunic, holding a sketchbook, "
            "friendly rounded face"
        ),
    },
    "sherlock_holmes": {
        "prompt": (
            "Sherlock Holmes with a clever friendly expression, big expressive eyes, "
            "deerstalker hat, detailed victorian coat, holding a magnifying glass, "
            "rounded friendly face"
        ),
    },
    "peter_pan": {
        "prompt": (
            "Peter Pan as a joyful adventurous magical boy, big expressive eyes, "
            "wearing clothes made of green leaves, flying with glowing fairy dust, "
            "friendly rounded face"
        ),
    },
}


# Nombre con el que cada personaje se presenta al hablar en primera persona en el
# chat (sistema RAG). Las claves deben coincidir con las de PROMPTS y con el
# nombre de la carpeta en backend/documentos/<personaje_id>/.
NOMBRES = {
    "triceratops": "Triceratops",
    "t-rex": "Tiranosaurio Rex",
    "leonardo_da_vinci": "Leonardo da Vinci",
    "sherlock_holmes": "Sherlock Holmes",
    "peter_pan": "Peter Pan",
}
