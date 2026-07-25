"""Tests de `_estimar_tokens` (generation_service).

Estima (al alza) los tokens de un prompt contando palabras y signos de puntuación
por separado (cada signo suele ser un token aparte para CLIP). No pretende ser
exacto: solo decidir si avisar de que CLIP truncará.
"""

import pytest

from backend.services import generation_service


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("", 0),
        ("hola", 1),
        ("hola mundo", 2),
        ("hola, mundo!", 4),  # hola · , · mundo · !
        ("a.b", 3),  # a · . · b
        ("3D render", 2),  # los dígitos cuentan como parte de la palabra
    ],
)
def test_estima_palabras_y_puntuacion(texto, esperado):
    assert generation_service._estimar_tokens(texto) == esperado


def test_los_espacios_no_cuentan():
    assert generation_service._estimar_tokens("   hola   mundo   ") == 2
