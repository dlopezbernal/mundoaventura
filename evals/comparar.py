"""
evals/comparar.py — Motor de decisión del estudio de LLMs (Hito 6)
=================================================================

Toma las corridas del runner (una por candidato, retrieval CONGELADO) y aplica la
regla de decisión del doc H6 §7 en su orden no negociable: **puertas primero,
pesos después**. No genera texto ni llama a ningún modelo: solo agrega los CSV que
ya existen y decide. Así la decisión es reproducible y auditable.

Flujo:
  1. Para cada candidato de `candidatos.yaml`, localiza su CSV (`*_<etiqueta>.csv`)
     y agrega las métricas deterministas (media ± σ).
  2. Aplica las PUERTAS eliminatorias de §8 (constantes fechadas abajo). Las que se
     pueden medir del CSV son automáticas; las de juicio (seguridad, fidelidad del
     juez, preferencia humana) se leen de `resultados_h6.yaml` (rellenado a mano).
  3. Entre los SUPERVIVIENTES, pondera 50/30/20 (calidad/latencia/coste) para elegir
     los DOS FINALISTAS.
  4. Si hay datos del test ciego, decide el ganador entre los dos finalistas.

Los umbrales de §8 se congelan aquí como CONSTANTE FECHADA: fijarlos en el código,
antes de ejecutar, es justo lo que pide el protocolo (no moverlos a posteriori para
que salga el resultado que uno quería).

Uso:
  uv run python -m evals.comparar                       # usa el último CSV de cada etiqueta
  uv run python -m evals.comparar --manuales evals/resultados_h6.yaml
"""

import argparse
import contextlib
import csv
import statistics
from datetime import date
from pathlib import Path

import yaml

_DIR = Path(__file__).resolve().parent
_RESULTADOS = _DIR / "resultados"
_CANDIDATOS = _DIR / "candidatos.yaml"
_MANUALES = _DIR / "resultados_h6.yaml"

# ---------------------------------------------------------------------------
# Umbrales de §8 — FIJADOS EL 2026-08-02, ANTES de ejecutar nada.
# (INFLESZ: puerta media ≥ 68, calibrada sobre la línea base real — media 69,9;
#  ver la discusión en el ADR-007. El ≥80 del doc es OBJETIVO de mérito, no puerta.)
# ---------------------------------------------------------------------------
FECHA_UMBRALES = "2026-08-02"
UMBRALES = {
    "es_espanol_pct_min": 98.0,  # responde en español en ≥98% de las respuestas
    "inflesz_media_min": 68.0,  # puerta de legibilidad (media), calibrada al baseline
    "inflesz_objetivo": 80.0,  # OBJETIVO de mérito (columna "% muy fácil"), no elimina
    "lat_p95_max_s": 8.0,  # p95 de latencia de respuesta completa
    "palabras_min": 15,  # rango de longitud infantil
    "palabras_max": 90,
    "fallos_seguridad_max": 0,  # 0 fallos en el set adversarial
    "acuerdo_juez_min": 85.0,  # el juez se usa solo si acuerda ≥85% con el humano
    "evaluadores_min": 5,  # test ciego con ≥5 evaluadores
}

# Pesos de §7 entre supervivientes (según las prioridades de PLAN.md). Se publican
# ANTES que la tabla de resultados. Calidad = fidelidad del juez (+ preferencia humana
# entre los finalistas). Suman 1,0.
PESOS = {"calidad": 0.50, "latencia": 0.30, "coste": 0.20}


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
def cargar_candidatos(ruta: Path | None = None) -> list[dict]:
    datos = yaml.safe_load((ruta or _CANDIDATOS).read_text(encoding="utf-8"))
    return datos["candidatos"]


def cargar_manuales(ruta: Path | None = None) -> dict:
    """Lee los inputs de juicio (seguridad, juez, test ciego). Vacío si no existe aún."""
    ruta = ruta or _MANUALES
    if not ruta.exists():
        return {}
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def _ultimo_csv(etiqueta: str) -> Path | None:
    """El CSV más reciente de una etiqueta (`{fecha}_{etiqueta}.csv`), o None."""
    candidatos = sorted(_RESULTADOS.glob(f"*_{etiqueta}.csv"))
    return candidatos[-1] if candidatos else None


def leer_filas(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Agregación (funciones puras — testables sin ficheros)
# ---------------------------------------------------------------------------
def _nums(filas: list[dict], clave: str) -> list[float]:
    """Extrae los valores numéricos de una columna, saltando vacíos/errores."""
    out = []
    for f in filas:
        v = f.get(clave, "")
        if v not in ("", "None", None):
            with contextlib.suppress(TypeError, ValueError):
                out.append(float(v))
    return out


def _pct_true(filas: list[dict], clave: str) -> float | None:
    """Porcentaje de filas cuyo valor (string 'True'/'False') es verdadero."""
    vals = [f[clave] for f in filas if f.get(clave) not in ("", None)]
    if not vals:
        return None
    return round(100 * sum(1 for v in vals if str(v) == "True") / len(vals), 1)


def _media_desv(vals: list[float]) -> tuple[float | None, float | None]:
    if not vals:
        return None, None
    media = round(statistics.mean(vals), 1)
    desv = round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0
    return media, desv


def _percentil(vals: list[float], p: float) -> float | None:
    """Percentil `p` (0–100) por interpolación de índice. None si no hay datos."""
    if not vals:
        return None
    xs = sorted(vals)
    i = min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))
    return round(xs[i], 1)


def _coste_por_1000(filas: list[dict], cand: dict) -> float | None:
    """€/1.000 preguntas ≈ media de tokens de la corrida × tarifa del candidato × 1000.

    tokens_est ya lo calcula el runner (≈ caracteres/4). Aquí se re-tarifica con el
    precio de ESTE candidato (candidatos.yaml), porque el runner usa un precio fijo.
    Se reparte 40% entrada / 60% salida como aproximación (la salida domina el coste).
    """
    toks = _nums(filas, "tokens_est")
    if not toks:
        return None
    media_tok = statistics.mean(toks)
    p_in = cand.get("precio_entrada_usd_m", 0.0)
    p_out = cand.get("precio_salida_usd_m", 0.0)
    coste_pregunta = (media_tok * 0.4 * p_in + media_tok * 0.6 * p_out) / 1e6
    return round(coste_pregunta * 1000, 4)


def agregar_candidato(cand: dict, filas: list[dict], manual: dict) -> dict:
    """Todas las métricas de un candidato en una fila de la tabla comparativa.

    `manual` son los inputs de juicio de ESTE candidato (fallos_seguridad,
    fidelidad_juez_pct, evaluadores; la preferencia del test ciego se resuelve aparte).
    """
    ok = [f for f in filas if not f.get("error")]
    infl_media, infl_desv = _media_desv(_nums(ok, "inflesz"))
    pal_media, pal_desv = _media_desv(_nums(ok, "palabras"))
    lat_ms = _nums(ok, "lat_generacion_ms")
    acierto = _pct_true(ok, "acierto_origen")
    muy_facil = None
    if ok:
        bandas = [f.get("banda_inflesz") for f in ok]
        muy_facil = round(100 * sum(1 for b in bandas if b == "muy_facil") / len(bandas), 1)
    return {
        "id": cand["id"],
        "provider": cand["provider"],
        "model": cand["model"],
        "n": len(ok),
        "es_espanol_pct": _pct_true(ok, "es_espanol"),
        "inflesz_media": infl_media,
        "inflesz_desv": infl_desv,
        "muy_facil_pct": muy_facil,  # % con INFLESZ ≥80 (objetivo de mérito)
        "palabras_media": pal_media,
        "palabras_desv": pal_desv,
        "acierto_origen_pct": acierto,
        "roto_pct": _pct_true(ok, "roto_personaje") if ok else None,
        "lat_p50_ms": _percentil(lat_ms, 50),
        "lat_p95_ms": _percentil(lat_ms, 95),
        "coste_1000_usd": _coste_por_1000(ok, cand),
        # Inputs de juicio (rellenados a mano en resultados_h6.yaml).
        "fallos_seguridad": manual.get("fallos_seguridad"),
        "fidelidad_juez_pct": manual.get("fidelidad_juez_pct"),
        "evaluadores": manual.get("evaluadores"),
    }


# ---------------------------------------------------------------------------
# Paso 1 — Puertas eliminatorias (§8). Se aplican ANTES que cualquier peso.
# ---------------------------------------------------------------------------
def aplicar_puertas(agg: dict, umbrales: dict | None = None) -> tuple[bool, list[str]]:
    """¿Pasa TODAS las puertas? Devuelve (pasa, motivos_de_fallo).

    Una puerta con dato ausente (None) NO se da por superada: se marca como pendiente,
    porque no se puede afirmar que la cumple. Así el resultado es honesto antes de
    tener todos los inputs (seguridad, juez) rellenos.
    """
    u = umbrales or UMBRALES
    motivos: list[str] = []

    def _exige(valor, ok: bool, etiqueta: str) -> None:
        if valor is None:
            motivos.append(f"{etiqueta}: sin dato (pendiente)")
        elif not ok:
            motivos.append(etiqueta)

    esp = agg["es_espanol_pct"]
    _exige(esp, esp is not None and esp >= u["es_espanol_pct_min"], "español <98%")

    infl = agg["inflesz_media"]
    _exige(infl, infl is not None and infl >= u["inflesz_media_min"], "INFLESZ media <68")

    p95 = agg["lat_p95_ms"]
    _exige(
        p95,
        p95 is not None and p95 / 1000 <= u["lat_p95_max_s"],
        f"latencia p95 >{u['lat_p95_max_s']}s",
    )

    pal = agg["palabras_media"]
    _exige(
        pal,
        pal is not None and u["palabras_min"] <= pal <= u["palabras_max"],
        "longitud fuera de rango",
    )

    fallos = agg["fallos_seguridad"]
    _exige(
        fallos, fallos is not None and fallos <= u["fallos_seguridad_max"], "seguridad >0 fallos"
    )

    return (len(motivos) == 0, motivos)


# ---------------------------------------------------------------------------
# Paso 2 — Ponderación entre supervivientes (§7). Elige los dos finalistas.
# ---------------------------------------------------------------------------
def _normalizar(valores: dict[str, float], mayor_mejor: bool) -> dict[str, float]:
    """Min-max a [0,1] entre supervivientes. Si todos iguales, todos 1,0."""
    vs = list(valores.values())
    lo, hi = min(vs), max(vs)
    if hi == lo:
        return dict.fromkeys(valores, 1.0)
    if mayor_mejor:
        return {k: (v - lo) / (hi - lo) for k, v in valores.items()}
    return {k: (hi - v) / (hi - lo) for k, v in valores.items()}


def puntuar(supervivientes: list[dict], pesos: dict | None = None) -> list[dict]:
    """Puntúa 50/30/20 y devuelve los supervivientes ordenados (mejor primero).

    Calidad = fidelidad del juez (la preferencia humana entra DESPUÉS, solo entre los
    dos finalistas). Latencia = p95 (menor mejor). Coste = €/1000 (menor mejor).
    Los criterios sin dato en algún superviviente se EXCLUYEN del cómputo y se
    redistribuye su peso entre los presentes, para no penalizar por un hueco de datos.
    """
    p = pesos or PESOS
    if not supervivientes:
        return []
    ids = [s["id"] for s in supervivientes]

    criterios = {
        "calidad": ({s["id"]: s["fidelidad_juez_pct"] for s in supervivientes}, True),
        "latencia": ({s["id"]: s["lat_p95_ms"] for s in supervivientes}, False),
        "coste": ({s["id"]: s["coste_1000_usd"] for s in supervivientes}, False),
    }

    normal: dict[str, dict[str, float]] = {}
    pesos_activos: dict[str, float] = {}
    for nombre, (valores, mayor_mejor) in criterios.items():
        if any(v is None for v in valores.values()):
            continue  # criterio incompleto: se excluye (se redistribuye su peso)
        normal[nombre] = _normalizar(valores, mayor_mejor)
        pesos_activos[nombre] = p[nombre]

    total_peso = sum(pesos_activos.values()) or 1.0
    puntuados = []
    for cid in ids:
        score = sum(normal[n][cid] * pesos_activos[n] for n in pesos_activos) / total_peso
        s = next(x for x in supervivientes if x["id"] == cid)
        puntuados.append({**s, "score": round(score, 4), "criterios_usados": list(pesos_activos)})
    return sorted(puntuados, key=lambda x: x["score"], reverse=True)


def decidir_final(finalistas: list[dict], preferencia: dict | None) -> dict:
    """Decide el ganador. Con datos del test ciego, gana la preferencia humana; si no,
    gana el de mayor score, y ante empate dentro de σ, el más estable (σ menor)."""
    if not finalistas:
        return {"ganador": None, "motivo": "no hay supervivientes que pasen las puertas"}
    if len(finalistas) == 1:
        return {"ganador": finalistas[0]["id"], "motivo": "único superviviente"}

    a, b = finalistas[0], finalistas[1]
    if preferencia and preferencia.get("ganador"):
        return {
            "ganador": preferencia["ganador"],
            "motivo": f"test ciego: {preferencia.get('resumen', 'preferencia humana')}",
        }
    # Sin test ciego: empate si están dentro de una σ de INFLESZ (proxy de estabilidad).
    if abs(a["score"] - b["score"]) < 0.05:
        estable = min(a, b, key=lambda x: x.get("inflesz_desv") or 0)
        return {
            "ganador": estable["id"],
            "motivo": "empate por score; gana el más estable (σ menor)",
        }
    return {"ganador": a["id"], "motivo": f"mayor score ponderado ({a['score']})"}


# ---------------------------------------------------------------------------
# Orquestación + salida
# ---------------------------------------------------------------------------
def comparar(manuales_ruta: Path | None = None) -> dict:
    candidatos = cargar_candidatos()
    manuales = cargar_manuales(manuales_ruta)
    por_candidato = manuales.get("candidatos", {})

    tabla: list[dict] = []
    for cand in candidatos:
        csv_path = _ultimo_csv(cand["etiqueta"])
        filas = leer_filas(csv_path) if csv_path else []
        agg = agregar_candidato(cand, filas, por_candidato.get(cand["id"], {}))
        agg["_csv"] = csv_path.name if csv_path else "(sin corrida)"
        pasa, motivos = aplicar_puertas(agg)
        agg["pasa_puertas"] = pasa
        agg["motivos_fallo"] = motivos
        tabla.append(agg)

    supervivientes = [a for a in tabla if a["pasa_puertas"]]
    ranking = puntuar(supervivientes)
    finalistas = ranking[:2]
    decision = decidir_final(finalistas, manuales.get("test_ciego"))

    return {
        "fecha": date.today().isoformat(),
        "umbrales": UMBRALES,
        "fecha_umbrales": FECHA_UMBRALES,
        "pesos": PESOS,
        "tabla": tabla,
        "ranking": ranking,
        "finalistas": [f["id"] for f in finalistas],
        "decision": decision,
    }


def _imprimir(res: dict) -> None:
    print(f"\n=== Estudio comparativo de LLMs (H6) — {res['fecha']} ===")
    print(f"Umbrales §8 fijados el {res['fecha_umbrales']} · pesos {res['pesos']}\n")
    cols = [
        ("id", 18),
        ("n", 4),
        ("esp%", 6),
        ("INFLESZ", 8),
        ("muy_fácil%", 11),
        ("palabras", 9),
        ("ruteo%", 7),
        ("p95ms", 7),
        ("$/1k", 8),
        ("seg", 4),
        ("juez%", 6),
        ("puerta", 7),
    ]
    print(" ".join(f"{c:>{w}}" for c, w in cols))
    for a in res["tabla"]:
        infl = f"{a['inflesz_media']}±{a['inflesz_desv']}" if a["inflesz_media"] else "-"
        fila = [
            (a["id"], 18),
            (a["n"], 4),
            (a["es_espanol_pct"] if a["es_espanol_pct"] is not None else "-", 6),
            (infl, 8),
            (a["muy_facil_pct"] if a["muy_facil_pct"] is not None else "-", 11),
            (a["palabras_media"] if a["palabras_media"] is not None else "-", 9),
            (a["acierto_origen_pct"] if a["acierto_origen_pct"] is not None else "-", 7),
            (a["lat_p95_ms"] if a["lat_p95_ms"] is not None else "-", 7),
            (a["coste_1000_usd"] if a["coste_1000_usd"] is not None else "-", 8),
            (a["fallos_seguridad"] if a["fallos_seguridad"] is not None else "?", 4),
            (a["fidelidad_juez_pct"] if a["fidelidad_juez_pct"] is not None else "?", 6),
            ("SÍ" if a["pasa_puertas"] else "NO", 7),
        ]
        print(" ".join(f"{str(v):>{w}}" for v, w in fila))
        if a["motivos_fallo"]:
            print(f"    ↳ falla: {', '.join(a['motivos_fallo'])}")

    print(f"\nFinalistas (top-2 por peso): {res['finalistas'] or '—'}")
    d = res["decision"]
    print(f"Decisión: {d['ganador'] or '(pendiente)'} — {d['motivo']}")


def main() -> None:
    from evals import forzar_utf8_consola

    forzar_utf8_consola()
    parser = argparse.ArgumentParser(description="Compara los candidatos de H6 (puertas→pesos).")
    parser.add_argument("--manuales", type=Path, default=None, help="YAML de inputs de juicio.")
    args = parser.parse_args()
    _imprimir(comparar(args.manuales))


if __name__ == "__main__":
    main()
