"""Tests de saldo_service (botón "Consultar saldo" de la pestaña APIs).

NINGUNO llama a un proveedor real: se prueban las piezas puras (formateo, parseo
de cabeceras, cálculo de porcentaje) y el despacho de los proveedores que NO
exponen saldo, que se resuelve sin red. La consulta de DeepL/ElevenLabs/LLM sí
hace peticiones, así que aquí se deja fuera a propósito — en el caso del LLM
además **cuesta una llamada de inferencia**, y un test no debe gastar dinero.
"""

import pytest

from backend.services import saldo_service, secrets_service


class TestMil:
    def test_separa_millares_al_estilo_espanol(self):
        assert saldo_service._mil(1_000_000) == "1.000.000"
        assert saldo_service._mil(71_340) == "71.340"

    def test_numeros_cortos_se_dejan_igual(self):
        assert saldo_service._mil(0) == "0"
        assert saldo_service._mil(37) == "37"


class TestEntero:
    def test_convierte_texto_numerico(self):
        assert saldo_service._entero("11963") == 11963
        assert saldo_service._entero(" 42 ") == 42

    @pytest.mark.parametrize("valor", [None, "", "  ", "muchos", "12.5"])
    def test_lo_que_no_es_entero_da_none(self, valor):
        # Las cabeceras son texto libre del proveedor: nunca deben reventar la consulta.
        assert saldo_service._entero(valor) is None


class TestMedida:
    def test_calcula_el_porcentaje(self):
        m = saldo_service._medida("Caracteres", 71_340, 1_000_000)
        assert m["porcentaje"] == 7.1

    def test_sin_limite_no_hay_porcentaje(self):
        # Plan sin tope declarado: pintar una barra sería inventarse el total.
        assert saldo_service._medida("Tokens", 500, None)["porcentaje"] is None

    def test_limite_cero_no_divide_por_cero(self):
        assert saldo_service._medida("Tokens", 0, 0)["porcentaje"] is None

    def test_sin_usado_no_hay_porcentaje(self):
        assert saldo_service._medida("Tokens", None, 1000)["porcentaje"] is None


class TestMedidasDesdeCabeceras:
    CABECERAS = {
        "x-ratelimit-limit-tokens": "12000",
        "x-ratelimit-remaining-tokens": "11963",
        "x-ratelimit-reset-tokens": "185ms",
        "x-ratelimit-limit-requests": "1000",
        "x-ratelimit-remaining-requests": "999",
        "x-ratelimit-reset-requests": "2m52.8s",
    }

    def test_traduce_las_dos_dimensiones(self):
        medidas = saldo_service._medidas_desde_cabeceras(self.CABECERAS)
        assert [m["etiqueta"] for m in medidas] == ["Tokens", "Peticiones"]

    def test_usado_es_limite_menos_restante(self):
        tokens = saldo_service._medidas_desde_cabeceras(self.CABECERAS)[0]
        assert tokens["usado"] == 37
        assert tokens["limite"] == 12000

    def test_renueva_llega_como_frase_montada(self):
        # El frontend no debe adivinar si es una fecha o un tiempo restante.
        medidas = saldo_service._medidas_desde_cabeceras(self.CABECERAS)
        assert medidas[0]["renueva"] == "se reinicia en 185ms"

    def test_no_distingue_mayusculas_en_las_cabeceras(self):
        medidas = saldo_service._medidas_desde_cabeceras(
            {"X-RateLimit-Limit-Tokens": "100", "X-RateLimit-Remaining-Tokens": "40"}
        )
        assert medidas[0]["usado"] == 60

    def test_omite_la_dimension_que_no_viene(self):
        medidas = saldo_service._medidas_desde_cabeceras(
            {"x-ratelimit-limit-tokens": "100", "x-ratelimit-remaining-tokens": "40"}
        )
        assert [m["etiqueta"] for m in medidas] == ["Tokens"]

    def test_sin_cabeceras_de_cuota_no_hay_medidas(self):
        assert saldo_service._medidas_desde_cabeceras({"content-type": "application/json"}) == []


class TestResumen:
    def test_une_las_medidas_con_separador(self):
        medidas = [
            saldo_service._medida("Tokens", 37, 12_000),
            saldo_service._medida("Peticiones", 2, 1_000),
        ]
        texto = saldo_service._resumen(medidas)
        assert "Tokens: 37 de 12.000" in texto
        assert " · " in texto

    def test_usa_la_coma_decimal(self):
        assert "0,3 %" in saldo_service._resumen([saldo_service._medida("Tokens", 37, 12_000)])

    def test_sin_medidas_devuelve_cadena_vacia(self):
        assert saldo_service._resumen([]) == ""


class TestFechaUnix:
    def test_formatea_una_marca_valida(self):
        # 1786147200 == 2026-08-08T00:00:00Z. Se fija en UTC en el propio servicio,
        # así que el resultado NO depende del huso de la máquina que corra el test.
        assert saldo_service._fecha_unix(1786147200) == "08/08/2026"

    @pytest.mark.parametrize("valor", [None, 0])
    def test_sin_marca_devuelve_none(self, valor):
        assert saldo_service._fecha_unix(valor) is None


class TestProveedoresSinSaldoPorApi:
    """Los que no lo publican: se dicen en claro, sin red."""

    @pytest.mark.parametrize("proveedor", ["replicate", "smtp"])
    def test_no_disponible_y_sin_medidas(self, proveedor):
        res = saldo_service.consultar(proveedor)
        assert res["disponible"] is False
        assert res["ok"] is False
        assert res["medidas"] == []

    def test_replicate_ofrece_su_panel(self):
        # Sin botón, el panel es la ÚNICA salida: si falta, el adulto se queda sin nada.
        res = saldo_service.consultar("replicate")
        assert res["panel_url"]
        assert "no publica el crédito" in res["mensaje"]

    def test_smtp_no_ofrece_panel(self):
        # Mandar a buscar los créditos de Brevo con la clave SMTP es ruido, no ayuda.
        assert saldo_service.consultar("smtp")["panel_url"] is None

    def test_proveedor_desconocido_no_revienta(self):
        # `consultar` nunca lanza; la validación del nombre la hace secrets_service.
        res = saldo_service.consultar("inventado")
        assert res["disponible"] is False


class TestPolitica:
    """`_CONSULTABLES` gobierna la interfaz: es la que decide botón / enlace / nada."""

    @pytest.mark.parametrize("proveedor", ["deepl", "elevenlabs", "llm", "groq"])
    def test_consultables(self, proveedor):
        assert saldo_service.consultable(proveedor) is True

    @pytest.mark.parametrize("proveedor", ["replicate", "smtp", "inventado"])
    def test_no_consultables(self, proveedor):
        assert saldo_service.consultable(proveedor) is False

    def test_replicate_no_consultable_pero_con_panel(self):
        # Es justo el caso que pinta un enlace en vez de un botón.
        assert saldo_service.consultable("replicate") is False
        assert saldo_service.panel("replicate")

    def test_smtp_ni_boton_ni_enlace(self):
        assert saldo_service.consultable("smtp") is False
        assert saldo_service.panel("smtp") is None

    def test_estado_publica_la_politica(self):
        # El frontend NO debe repetir la lista de proveedores: la lee de aquí.
        por_nombre = {p["proveedor"]: p for p in secrets_service.estado()}
        assert por_nombre["groq"]["saldo_consultable"] is True
        assert por_nombre["replicate"]["saldo_consultable"] is False
        assert por_nombre["replicate"]["panel_url"]
        assert por_nombre["smtp"]["saldo_consultable"] is False
        assert por_nombre["smtp"]["panel_url"] is None


class TestWavSilencio:
    """El audio mínimo con el que se consulta la cuota de Groq (1 s, generado al vuelo)."""

    def test_es_un_wav_valido_de_un_segundo(self):
        import io
        import wave

        with wave.open(io.BytesIO(saldo_service._wav_silencio())) as w:
            assert w.getnchannels() == 1
            assert w.getframerate() == 16_000
            assert w.getnframes() == 16_000  # exactamente 1 segundo: el mínimo facturable

    def test_no_depende_de_un_binario_del_repositorio(self):
        # Se genera con la stdlib: no hay fichero de audio versionado que pueda faltar.
        assert len(saldo_service._wav_silencio()) > 32_000


class TestPuertaPublica:
    def test_proveedor_desconocido_es_valueerror(self):
        # ValueError → el router lo mapea a HTTP 400.
        with pytest.raises(ValueError, match="Proveedor desconocido"):
            secrets_service.saldo("inventado")

    def test_delega_en_saldo_service(self, monkeypatch):
        llamado = {}

        def falso(proveedor: str) -> dict:
            llamado["proveedor"] = proveedor
            return {
                "proveedor": proveedor,
                "disponible": False,
                "ok": False,
                "mensaje": "",
                "medidas": [],
            }

        monkeypatch.setattr(saldo_service, "consultar", falso)
        secrets_service.saldo("deepl")
        assert llamado["proveedor"] == "deepl"
