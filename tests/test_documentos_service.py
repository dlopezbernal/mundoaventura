"""Tests de `_nombre_con_idioma` (documentos_service).

El nombre de fichero guardado indica el idioma de origen: si el documento ya estaba
en inglés conserva su extensión (`_en<ext>`); si se tradujo, queda como texto plano
`_<idioma>.en.md`.
"""

from backend.services import documentos_service


class TestNombreConIdioma:
    def test_ya_en_ingles_conserva_extension(self):
        assert documentos_service._nombre_con_idioma("t-rex", ".md", "en", False) == "t-rex_en.md"
        assert documentos_service._nombre_con_idioma("doc", ".pdf", "en", False) == "doc_en.pdf"
        assert documentos_service._nombre_con_idioma("doc", ".txt", "en", False) == "doc_en.txt"

    def test_traducido_marca_idioma_origen_y_es_markdown(self):
        assert documentos_service._nombre_con_idioma("doc", ".txt", "es", True) == "doc_es.en.md"
        assert documentos_service._nombre_con_idioma("art", ".pdf", "fr", True) == "art_fr.en.md"

    def test_traducido_ignora_la_extension_original(self):
        # Traducido siempre acaba en .en.md, sea cual sea la extensión de entrada.
        assert documentos_service._nombre_con_idioma("x", ".pdf", "de", True).endswith(".en.md")
