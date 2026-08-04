"""Tests del núcleo determinista de la evaluación STT (Hito 7): normalización + WER.

El arnés que transcribe audio real vive en `evals/stt.py` y se corre en la máquina
del usuario con clips grabados; aquí se fija la métrica (WER) con texto, que es lo
que debe ser reproducible y no gastar nada.
"""

from evals import stt


def test_normalizar_minusculas_sin_puntuacion_con_acentos():
    assert stt.normalizar("¡Hola, T-Rex! ¿Cómo estás?") == ["hola", "t", "rex", "cómo", "estás"]


def test_wer_transcripcion_perfecta_es_cero():
    assert stt.wer("hola tirano rex", "hola tirano rex") == 0.0


def test_wer_ignora_puntuacion_y_mayusculas():
    # Solo cambian signos y capitalización → WER 0 (se mide sobre texto normalizado).
    assert stt.wer("hola tirano rex", "Hola, Tirano Rex.") == 0.0


def test_wer_una_sustitucion_sobre_tres_palabras():
    # "rex" → "wex": 1 error sobre 3 palabras de referencia = 0,3333.
    assert stt.wer("hola tirano rex", "hola tirano wex") == round(1 / 3, 4)


def test_wer_insercion_y_borrado():
    # ref 3 palabras; hip añade una (inserción) = 1/3.
    assert stt.wer("hola tirano rex", "hola tirano rex enorme") == round(1 / 3, 4)
    # hip quita una (borrado) = 1/3.
    assert stt.wer("hola tirano rex", "hola tirano") == round(1 / 3, 4)


def test_wer_referencia_vacia():
    assert stt.wer("", "") == 0.0
    assert stt.wer("", "algo dijo") == 1.0


def test_distancia_edicion_a_nivel_de_palabra():
    assert stt._distancia_edicion(["a", "b", "c"], ["a", "x", "c"]) == 1  # 1 sustitución
    assert stt._distancia_edicion(["a", "b"], []) == 2  # 2 borrados
    assert stt._distancia_edicion([], ["a", "b", "c"]) == 3  # 3 inserciones


def test_wer_todo_distinto_es_uno():
    assert stt.wer("uno dos tres", "cuatro cinco seis") == 1.0
