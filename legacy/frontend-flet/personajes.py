"""
frontend/personajes.py — Catálogo de personajes
=================================================

Aquí definimos QUÉ personajes puede elegir el niño y cómo se muestran en el
catálogo. Cada uno tiene:
  - label     : nombre que se muestra en pantalla.
  - categoria : para agrupar en la interfaz (prehistórico / histórico / ficticio).
  - emoji     : miniatura provisional (sin necesidad de archivos de imagen).

Los `id` (las claves) deben coincidir con los de backend/personajes.py, que es
quien tiene el prompt real para la generación.
"""

PERSONAJES = {
    # --- Prehistóricos ---
    "triceratops": {
        "label": "Triceratops",
        "categoria": "prehistorico",
        "emoji": "🦕",
    },
    "t-rex": {
        "label": "T-Rex",
        "categoria": "prehistorico",
        "emoji": "🦖",
    },

    # --- Personajes Históricos 
    "leonardo_da_vinci": {
        "label": "Leonardo da Vinci",
        "categoria": "historico",
        "emoji": "🎨",
    },
    # --- Personajes Ficticios
    "sherlock_holmes": {
        "label": "Sherlock Holmes",
        "categoria": "ficticio",
        "emoji": "🕵️",
    },
    "peter_pan": {
        "label": "Peter Pan",
        "categoria": "ficticio",
        "emoji": "👦",
    }
}

# Cómo agrupar el catálogo en la interfaz: título de sección -> categorías que incluye.
GRUPOS = {
    "Prehistóricos": ["prehistorico"],
    "Históricos": ["historico"],
    "Ficticios": ["ficticio"]
}


def personajes_de_grupo(categorias: list[str]) -> list[tuple[str, dict]]:
    """Devuelve [(id, datos), ...] de los personajes cuyas categorías están en la lista."""
    return [
        (pid, datos)
        for pid, datos in PERSONAJES.items()
        if datos["categoria"] in categorias
    ]
