"""Tests del banco de pruebas (H3): métricas deterministas + validación de los sets.

Sin red ni LLM: cubren las funciones de medida (que deben ser deterministas y
reproducibles, criterio de la puerta) y la carga/validación de los YAML.
"""

import pytest

from evals import esquema, metricas

# Los 5 personajes activos (para detectar personaje_id mal escritos sin tocar la BBDD).
_PERSONAJES = {"t-rex", "triceratops", "sherlock_holmes", "leonardo_da_vinci", "peter_pan"}


# --------------------------- Métricas ---------------------------
def test_inflesz_texto_infantil_es_muy_facil():
    texto = "Yo comia carne. Tenia dientes grandes. Era un dinosaurio muy fuerte."
    score = metricas.inflesz(texto)
    assert score is not None
    assert metricas.banda_inflesz(score) == "muy_facil"  # frases cortas y simples


def test_inflesz_texto_complejo_baja_de_banda():
    facil = "El gato duerme. El sol brilla. Yo juego."
    dificil = (
        "La constitucionalidad de las disposiciones administrativas presupone una "
        "interpretación sistemática de innumerables preceptos jurisdiccionales heterogéneos."
    )
    assert metricas.inflesz(facil) > metricas.inflesz(dificil)


def test_metricas_deterministas():
    # Criterio de la puerta: mismas entradas → mismas métricas (reproducible).
    texto = "Yo vivia en el bosque y comia plantas verdes muy ricas."
    assert metricas.inflesz(texto) == metricas.inflesz(texto)
    assert metricas.fernandez_huerta(texto) == metricas.fernandez_huerta(texto)
    assert metricas.idioma(texto) == metricas.idioma(texto)


def test_inflesz_texto_vacio_es_none():
    assert metricas.inflesz("") is None
    assert metricas.banda_inflesz(None) == "sin_texto"


def test_idioma_es_en():
    assert metricas.idioma("Hola, yo soy un dinosaurio muy simpatico") == "es"
    assert metricas.idioma("Hello, I am a friendly dinosaur") == "en"
    assert metricas.es_espanol("Vivo en el bosque")


def test_roto_de_personaje():
    assert metricas.roto_de_personaje("Rooar! Soy un T-Rex y comia carne.") == []
    roto = metricas.roto_de_personaje("Como IA no puedo responder segun el contexto.")
    assert "Como IA" in roto
    assert len(roto) >= 2  # "como IA" + "no puedo responder" + "segun el contexto"


@pytest.mark.parametrize(
    ("esperado", "fuentes", "resultado"),
    [
        ("a.md", ["b.md", "a.md"], True),
        ("a.md", ["b.md", "c.md"], False),
        (["a.md", "x.md"], ["c.md", "x.md"], True),  # lista: acierta cualquiera
        (["a.md", "x.md"], ["c.md", "d.md"], False),
        (None, ["a.md"], None),  # sin chunk_esperado → no aplica
    ],
)
def test_recall_at_k(esperado, fuentes, resultado):
    assert metricas.recall_at_k(esperado, fuentes) is resultado


@pytest.mark.parametrize(
    ("contiene", "chunks", "resultado"),
    [
        ("Baker Street", ["He lives at 221B Baker Street"], True),
        ("scaveng", ["hunting or scavenging behaviour"], True),  # coincide por raíz
        ("Neverland", ["He lives in London"], False),
        (["Tinker Bell", "Tink"], ["his fairy Tink flew away"], True),  # lista: cualquiera
        (None, ["texto"], None),  # sin respuesta_contiene → no aplica
    ],
)
def test_recall_chunk(contiene, chunks, resultado):
    assert metricas.recall_chunk(contiene, chunks) is resultado


def test_contar_basico():
    assert metricas.contar_palabras("hola mundo cruel") == 3
    assert metricas.contar_frases("Uno. Dos! Tres?") == 3
    assert metricas.contar_silabas("sol") == 1  # monosílabo


# --------------------------- Sets (YAML) ---------------------------
def test_set_dorado_carga_y_distribucion():
    preg = esquema.cargar_set_dorado()
    assert len(preg) == 100  # 20 × 5 personajes
    resumen = esquema.resumen_distribucion(preg)
    esperada = {
        "literal": 6,
        "inferencial": 5,
        "fuera_dominio": 4,
        "sin_respuesta": 3,
        "ambigua": 2,
        "total": 20,
    }
    for pid, dist in resumen.items():
        assert pid in _PERSONAJES, f"personaje_id desconocido: {pid}"
        for tipo, n in esperada.items():
            assert dist.get(tipo, 0) == n, f"{pid}: {tipo} = {dist.get(tipo, 0)} (esperado {n})"


def test_set_dorado_literales_tienen_chunk_esperado():
    for p in esquema.cargar_set_dorado():
        if p.tipo.value in ("literal", "inferencial"):
            assert p.chunk_esperado, f"{p.id}: literal/inferencial sin chunk_esperado"
            assert p.respuesta_contiene, f"{p.id}: literal/inferencial sin respuesta_contiene"
        else:
            assert p.chunk_esperado is None, (
                f"{p.id}: {p.tipo.value} no debería tener chunk_esperado"
            )


def test_set_seguridad_carga():
    seg = esquema.cargar_set_seguridad()
    assert len(seg) >= 15
    assert all(s.personaje_id in _PERSONAJES for s in seg)


def test_ids_duplicados_se_rechazan(tmp_path):
    yaml_malo = tmp_path / "dup.yaml"
    yaml_malo.write_text(
        "- {id: x, personaje_id: t-rex, pregunta: a, tipo: literal, origen_esperado: RAG}\n"
        "- {id: x, personaje_id: t-rex, pregunta: b, tipo: literal, origen_esperado: RAG}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="id repetido"):
        esquema.cargar_set_dorado(yaml_malo)


def test_tipo_invalido_se_rechaza(tmp_path):
    yaml_malo = tmp_path / "bad.yaml"
    yaml_malo.write_text(
        "- {id: x, personaje_id: t-rex, pregunta: a, tipo: INVENTADO, origen_esperado: RAG}\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        esquema.cargar_set_dorado(yaml_malo)
