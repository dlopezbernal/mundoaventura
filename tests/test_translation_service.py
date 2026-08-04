"""Tests de `_trocear_para_traducir` (translation_service).

Parte un texto largo en lotes por debajo del máximo de DeepL, respetando los
párrafos siempre que puede y partiendo "a lo bruto" los párrafos gigantes. Se
monkeypatchea el máximo a un valor pequeño para no manejar cadenas enormes.
"""

from backend.services import translation_service


def _con_max(monkeypatch, valor):
    monkeypatch.setattr(translation_service, "_MAX_CHARS_LOTE", valor)


def test_texto_corto_en_un_solo_lote(monkeypatch):
    _con_max(monkeypatch, 100)
    assert translation_service._trocear_para_traducir("hola") == ["hola"]


def test_respeta_limites_de_parrafo(monkeypatch):
    # Dos párrafos que juntos superan el máximo → un lote por párrafo.
    _con_max(monkeypatch, 10)
    lotes = translation_service._trocear_para_traducir("aaaaa\n\nbbbbb")
    assert lotes == ["aaaaa", "bbbbb"]


def test_agrupa_parrafos_que_caben_juntos(monkeypatch):
    _con_max(monkeypatch, 100)
    lotes = translation_service._trocear_para_traducir("aaa\n\nbbb")
    assert lotes == ["aaa\n\nbbb"]


def test_parte_un_parrafo_gigante_por_tamano(monkeypatch):
    _con_max(monkeypatch, 10)
    lotes = translation_service._trocear_para_traducir("abcdefghijkl")  # 12 > 10
    assert lotes == ["abcdefghij", "kl"]
    # No se pierde texto: al ser un único párrafo, la concatenación reconstruye.
    assert "".join(lotes) == "abcdefghijkl"


def test_ningun_lote_supera_el_maximo(monkeypatch):
    _con_max(monkeypatch, 10)
    texto = "abcdefghijklmnop\n\nqrst\n\nuvwxyzabcdefghij"
    lotes = translation_service._trocear_para_traducir(texto)
    assert all(len(lote) <= 10 for lote in lotes)


def test_no_pierde_caracteres_de_un_parrafo_sin_saltos(monkeypatch):
    _con_max(monkeypatch, 7)
    texto = "x" * 20
    lotes = translation_service._trocear_para_traducir(texto)
    assert "".join(lotes) == texto
