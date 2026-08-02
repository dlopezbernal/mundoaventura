"""Tests de las piezas DETERMINISTAS del estudio de LLMs (Hito 6).

Cubren la lógica que decide (comparar), el parseo/acuerdo del juez y el armado/agregado
del test ciego. NADA aquí llama a un LLM: las funciones puras se prueban con datos
sintéticos, así el CI las valida en cada commit sin gastar en APIs.
"""

from evals import comparar, juez, test_ciego


# ---------------------------------------------------------------------------
# comparar.py — agregación, puertas y pesos
# ---------------------------------------------------------------------------
def _filas(n, inflesz, palabras, es_es="True", lat=500, roto="", tokens=200):
    """n filas OK con las columnas que lee agregar_candidato."""
    return [
        {
            "error": "",
            "inflesz": str(inflesz),
            "banda_inflesz": "muy_facil" if inflesz >= 80 else "bastante_facil",
            "palabras": str(palabras),
            "es_espanol": es_es,
            "acierto_origen": "True",
            "roto_personaje": roto,
            "lat_generacion_ms": str(lat),
            "tokens_est": str(tokens),
        }
        for _ in range(n)
    ]


_CAND = {
    "id": "x",
    "provider": "openai",
    "model": "m",
    "precio_entrada_usd_m": 0.1,
    "precio_salida_usd_m": 0.4,
}


def test_agregar_candidato_calcula_medias_y_porcentajes():
    agg = comparar.agregar_candidato(_CAND, _filas(3, 70, 20), {})
    assert agg["n"] == 3
    assert agg["inflesz_media"] == 70.0
    assert agg["es_espanol_pct"] == 100.0
    assert agg["palabras_media"] == 20.0
    assert agg["muy_facil_pct"] == 0.0  # 70 < 80


def test_agregar_ignora_filas_con_error():
    filas = _filas(2, 75, 20) + [{"error": "Boom", "inflesz": "10"}]
    agg = comparar.agregar_candidato(_CAND, filas, {})
    assert agg["n"] == 2


def test_puertas_pasan_con_buenos_valores():
    agg = comparar.agregar_candidato(_CAND, _filas(5, 72, 30), {"fallos_seguridad": 0})
    pasa, motivos = comparar.aplicar_puertas(agg)
    assert pasa is True
    assert motivos == []


def test_puerta_inflesz_elimina_por_debajo_de_68():
    agg = comparar.agregar_candidato(_CAND, _filas(5, 60, 30), {"fallos_seguridad": 0})
    pasa, motivos = comparar.aplicar_puertas(agg)
    assert pasa is False
    assert any("INFLESZ" in m for m in motivos)


def test_puerta_seguridad_pendiente_si_falta_dato():
    """Sin fallos_seguridad, la puerta queda PENDIENTE (no se da por superada)."""
    agg = comparar.agregar_candidato(_CAND, _filas(5, 72, 30), {})
    pasa, motivos = comparar.aplicar_puertas(agg)
    assert pasa is False
    assert any("seguridad" in m and "pendiente" in m for m in motivos)


def test_puerta_espanol_elimina_por_debajo_de_98():
    agg = comparar.agregar_candidato(
        _CAND, _filas(5, 72, 30, es_es="False"), {"fallos_seguridad": 0}
    )
    pasa, motivos = comparar.aplicar_puertas(agg)
    assert pasa is False
    assert any("español" in m for m in motivos)


def test_puerta_longitud_fuera_de_rango():
    agg = comparar.agregar_candidato(_CAND, _filas(5, 72, 5), {"fallos_seguridad": 0})  # 5 < 15
    pasa, motivos = comparar.aplicar_puertas(agg)
    assert pasa is False
    assert any("longitud" in m for m in motivos)


def test_normalizar_mayor_mejor_y_menor_mejor():
    vals = {"a": 10.0, "b": 20.0}
    assert comparar._normalizar(vals, mayor_mejor=True) == {"a": 0.0, "b": 1.0}
    assert comparar._normalizar(vals, mayor_mejor=False) == {"a": 1.0, "b": 0.0}


def test_normalizar_todos_iguales_da_uno():
    assert comparar._normalizar({"a": 5.0, "b": 5.0}, mayor_mejor=True) == {"a": 1.0, "b": 1.0}


def _superviviente(cid, juez, lat, coste, infl_desv=1.0):
    return {
        "id": cid,
        "fidelidad_juez_pct": juez,
        "lat_p95_ms": lat,
        "coste_1000_usd": coste,
        "inflesz_desv": infl_desv,
    }


def test_puntuar_ordena_por_score_ponderado():
    # A: mejor calidad y coste; B: mejor latencia. Con 50/30/20, A debe ganar.
    sup = [_superviviente("A", 90, 800, 1.0), _superviviente("B", 70, 400, 5.0)]
    ranking = comparar.puntuar(sup)
    assert ranking[0]["id"] == "A"
    assert ranking[0]["score"] >= ranking[1]["score"]


def test_puntuar_redistribuye_peso_si_falta_un_criterio():
    """Si la calidad (juez) no está en ningún superviviente, se puntúa solo con los
    criterios presentes (latencia+coste), sin romper."""
    sup = [_superviviente("A", None, 800, 5.0), _superviviente("B", None, 400, 1.0)]
    ranking = comparar.puntuar(sup)
    assert ranking[0]["id"] == "B"  # mejor latencia y coste
    assert "calidad" not in ranking[0]["criterios_usados"]


def test_decidir_final_gana_preferencia_humana():
    finalistas = [_superviviente("A", 90, 800, 1.0), _superviviente("B", 70, 400, 5.0)]
    for f in finalistas:
        f["score"] = 0.9 if f["id"] == "A" else 0.1
    d = comparar.decidir_final(finalistas, {"ganador": "B", "resumen": "58% de 160"})
    assert d["ganador"] == "B"  # el test ciego manda sobre el score


def test_decidir_final_unico_superviviente():
    d = comparar.decidir_final([_superviviente("A", 90, 800, 1.0)], None)
    assert d["ganador"] == "A"


def test_decidir_final_empate_gana_el_mas_estable():
    a = {**_superviviente("A", 90, 800, 5.0, infl_desv=5.0), "score": 0.80}
    b = {
        **_superviviente("B", 88, 810, 1.0, infl_desv=1.0),
        "score": 0.78,
    }  # dentro de 0,05 → empate
    d = comparar.decidir_final([a, b], None)
    assert d["ganador"] == "B"  # menor inflesz_desv


# ---------------------------------------------------------------------------
# juez.py — parseo y acuerdo
# ---------------------------------------------------------------------------
def test_parsear_json_limpio():
    v = juez.parsear_veredicto(
        '{"fundamentada": true, "afirmaciones_sin_respaldo": [], "justificacion": "ok"}'
    )
    assert v["fundamentada"] is True


def test_parsear_con_fences_y_texto_alrededor():
    txt = 'Claro:\n```json\n{"fundamentada": false, "afirmaciones_sin_respaldo": ["x"], "justificacion": "y"}\n```'
    v = juez.parsear_veredicto(txt)
    assert v["fundamentada"] is False
    assert v["afirmaciones_sin_respaldo"] == ["x"]


def test_parsear_basura_devuelve_none():
    v = juez.parsear_veredicto("no hay json aquí")
    assert v["fundamentada"] is None


def test_acuerdo_calcula_porcentaje():
    res = juez.acuerdo([True, True, False, False], [True, True, False, True])
    assert res["acuerdo_pct"] == 75.0
    assert res["n"] == 4
    assert res["usar"] is False  # 75 < 85


def test_acuerdo_excluye_no_parseables():
    res = juez.acuerdo([True, False, True], [True, False, None])
    assert res["n"] == 2  # el None se excluye
    assert res["acuerdo_pct"] == 100.0
    assert res["no_parseables"] == 1


def test_construir_prompt_numera_notas():
    system, user = juez.construir_prompt(["nota A", "nota B"], "respuesta")
    assert "[1] nota A" in user and "[2] nota B" in user
    assert "JSON" in system


def test_preparar_muestras_solo_rag_y_sin_duplicar():
    fixture = {"retrieval": {"q1": {"chunks": ["c1"]}, "q2": {"chunks": ["c2"]}}}
    filas = [
        {"id": "q1", "origen_obtenido": "RAG", "respuesta": "r1", "error": ""},
        {"id": "q1", "origen_obtenido": "RAG", "respuesta": "r1b", "error": ""},  # duplicado
        {"id": "q2", "origen_obtenido": "GENERAL", "respuesta": "r2", "error": ""},  # no RAG
    ]
    muestras = juez.preparar_muestras(fixture, filas)
    assert len(muestras) == 1
    assert muestras[0]["id"] == "q1"
    assert muestras[0]["notas"] == ["c1"]


def test_fidelidad_pct_excluye_no_parseables():
    veredictos = [{"fundamentada": True}, {"fundamentada": False}, {"fundamentada": None}]
    assert juez.fidelidad_pct(veredictos) == {"fidelidad_pct": 50.0, "n": 2}


# ---------------------------------------------------------------------------
# test_ciego.py — pares y agregación
# ---------------------------------------------------------------------------
def test_respuestas_por_id_toma_primera_rep_ok():
    filas = [
        {"id": "q1", "rep": "1", "respuesta": "buena", "error": ""},
        {"id": "q1", "rep": "2", "respuesta": "otra", "error": ""},
        {"id": "q2", "rep": "1", "respuesta": "", "error": "Boom"},
    ]
    r = test_ciego.respuestas_por_id(filas)
    assert r == {"q1": "buena"}  # q2 solo tenía error


def test_construir_pares_solo_ids_comunes_y_clave_coherente():
    resp_a = {"q1": "A1", "q2": "A2", "q3": "A3"}
    resp_b = {"q1": "B1", "q2": "B2"}  # q3 no está en B
    preguntas = {"q1": "¿uno?", "q2": "¿dos?", "q3": "¿tres?"}
    papeleta, clave = test_ciego.construir_pares(
        "mA", "mB", resp_a, resp_b, preguntas, n=5, semilla=1
    )
    assert len(papeleta) == 2  # solo q1 y q2 son comunes
    # Cada opción de la papeleta corresponde al modelo que dice la clave.
    for fila in papeleta:
        c = clave[fila["par_id"]]
        pid = c["id_pregunta"]
        esperado = {"mA": resp_a[pid], "mB": resp_b[pid]}
        assert fila["opcion_1"] == esperado[c["opcion_1"]]
        assert fila["opcion_2"] == esperado[c["opcion_2"]]


def test_construir_pares_es_reproducible_con_semilla():
    resp_a = {"q1": "A1", "q2": "A2"}
    resp_b = {"q1": "B1", "q2": "B2"}
    preguntas = {"q1": "u", "q2": "d"}
    p1, c1 = test_ciego.construir_pares("mA", "mB", resp_a, resp_b, preguntas, 5, semilla=42)
    p2, c2 = test_ciego.construir_pares("mA", "mB", resp_a, resp_b, preguntas, 5, semilla=42)
    assert p1 == p2 and c1 == c2


def test_agregar_votos_desanonimiza_y_cuenta():
    clave = {
        "par01": {"id_pregunta": "q1", "opcion_1": "mA", "opcion_2": "mB"},
        "par02": {"id_pregunta": "q2", "opcion_1": "mB", "opcion_2": "mA"},
    }
    votos = [
        {"par_id": "par01", "evaluador": "e1", "voto": "1"},  # → mA
        {"par_id": "par01", "evaluador": "e2", "voto": "1"},  # → mA
        {"par_id": "par02", "evaluador": "e1", "voto": "1"},  # → mB
        {"par_id": "par02", "evaluador": "e2", "voto": "2"},  # → mA
        {"par_id": "par01", "evaluador": "e3", "voto": "9"},  # inválido: se ignora
    ]
    res = test_ciego.agregar_votos(votos, clave)
    assert res["preferencia"] == {"mA": 3, "mB": 1}
    assert res["ganador"] == "mA"
    assert res["n_juicios"] == 4
    assert res["n_evaluadores"] == 2
    # par01: unánime (mA,mA)=1,0 ; par02 dividido (mB,mA)=0,5 → media 0,75.
    assert res["acuerdo_inter_evaluador"] == 0.75
