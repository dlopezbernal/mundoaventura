"""Tests de las funciones puras de secrets_service.

Cubren `_enmascarar` (nunca filtrar la clave completa) y `_aplicar_cambios_env`
(reescribir el .env preservando comentarios y respetando el salto final). Ambas son
puras: no tocan disco ni red, así que se prueban directamente.
"""

from backend.services import secrets_service


class TestEnmascarar:
    def test_vacio_devuelve_none(self):
        assert secrets_service._enmascarar("") is None

    def test_hasta_cuatro_caracteres_se_ocultan_enteros(self):
        # Con 4 o menos no se puede mostrar "los últimos 4" sin revelarlo entero:
        # se oculta por completo, con tantos puntos como caracteres.
        assert secrets_service._enmascarar("a") == "•"
        assert secrets_service._enmascarar("abcd") == "••••"

    def test_normal_muestra_solo_los_ultimos_cuatro(self):
        assert secrets_service._enmascarar("abcde") == "••••••bcde"
        assert secrets_service._enmascarar("sk-1234567890") == "••••••7890"


class TestAplicarCambiosEnv:
    def test_sustituye_una_variable_existente(self):
        salida = secrets_service._aplicar_cambios_env("A=1\nB=2\n", {"B": "9"})
        assert salida == "A=1\nB=9\n"

    def test_anade_variable_nueva_al_final(self):
        salida = secrets_service._aplicar_cambios_env("A=1\n", {"C": "3"})
        assert salida == "A=1\nC=3\n"

    def test_preserva_comentarios_y_lineas_no_tocadas(self):
        original = "# comentario\nA=1\n# otro=falso\nB=2\n"
        salida = secrets_service._aplicar_cambios_env(original, {"A": "9"})
        assert salida == "# comentario\nA=9\n# otro=falso\nB=2\n"

    def test_no_confunde_un_comentario_con_asignacion(self):
        # Una línea de comentario con '=' dentro NO debe tratarse como variable.
        salida = secrets_service._aplicar_cambios_env("# a=b\nA=1", {"A": "9"})
        assert salida.startswith("# a=b\n")

    def test_respeta_ausencia_de_salto_final(self):
        # Si el original no termina en salto de línea, la salida tampoco.
        salida = secrets_service._aplicar_cambios_env("A=1\nB=2", {"A": "9"})
        assert salida == "A=9\nB=2"

    def test_respeta_salto_final_presente(self):
        salida = secrets_service._aplicar_cambios_env("A=1\nB=2\n", {"A": "9"})
        assert salida.endswith("\n")

    def test_contenido_vacio_con_variable_nueva(self):
        salida = secrets_service._aplicar_cambios_env("", {"A": "1"})
        assert salida == "A=1\n"
