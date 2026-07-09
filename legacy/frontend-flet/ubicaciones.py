"""
frontend/ubicaciones.py — Catálogo de ubicaciones
==================================================

QUÉ lugares puede elegir el niño y cómo se muestran. Cada uno tiene:
  - label : nombre que se muestra en pantalla.
  - emoji : miniatura provisional.

Los `id` (las claves) deben coincidir con los de backend/ubicaciones.py, que es
quien tiene el prompt real para la generación.
"""

UBICACIONES = {
    "laboratorio": {
        "label": "Laboratorio",
        "emoji": "🧪",
    },
    "bosque_jurasico": {
        "label": "Bosque del Jurásico",
        "emoji": "🌋",
    },
    "renacimiento": {
        "label": "Renacimiento",
        "emoji": "🎨",
    },
    "epoca_victoriana": {
        "label": "Época Victoriana",
        "emoji": "🎩",
    },
}
