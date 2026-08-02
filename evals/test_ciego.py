"""
evals/test_ciego.py — Test ciego humano entre los dos finalistas (Hito 6, Nivel 3)
==================================================================================

La evidencia más fuerte del estudio (doc H6 §5): personas —a poder ser niños de
8–12— eligen, sin saber qué modelo es cuál, qué respuesta preferirían para un niño.

Dos operaciones, ninguna llama a un modelo:

  generar   : coge N preguntas del set dorado, toma la respuesta de CADA finalista
              (de su CSV del runner), y produce DOS ficheros:
                - papeleta (CSV para humanos): par_id, pregunta, opción_1, opción_2.
                  El orden opción_1/opción_2 se ALEATORIZA por par (semilla fija) para
                  que no se pueda inferir el modelo por la posición.
                - clave (JSON, NO se enseña a los evaluadores): par_id → qué modelo es
                  cada opción. Sirve para des-anonimizar al agregar.

  agregar   : lee los votos de los evaluadores (par_id, evaluador, voto∈{1,2}) + la
              clave, y calcula la preferencia agregada por modelo y el acuerdo entre
              evaluadores. Vuelca un resumen apto para pegar en resultados_h6.yaml.

Uso:
  uv run python -m evals.test_ciego generar --a evals/resultados/AAAA_h6-X.csv \\
      --b evals/resultados/AAAA_h6-Y.csv --n 20 --semilla 7
  uv run python -m evals.test_ciego agregar --votos evals/test_ciego/votos.csv
"""

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_SALIDA = _DIR / "test_ciego"


# ---------------------------------------------------------------------------
# Lectura de respuestas del CSV del runner
# ---------------------------------------------------------------------------
def respuestas_por_id(filas: list[dict]) -> dict[str, str]:
    """{id_pregunta: respuesta} tomando la PRIMERA repetición sin error de cada id."""
    out: dict[str, str] = {}
    for f in filas:
        pid = f.get("id")
        if pid and pid not in out and not f.get("error") and f.get("respuesta"):
            out[pid] = f["respuesta"]
    return out


def _leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Construcción de pares (función pura — testable sin ficheros)
# ---------------------------------------------------------------------------
def construir_pares(
    modelo_a: str,
    modelo_b: str,
    resp_a: dict[str, str],
    resp_b: dict[str, str],
    preguntas: dict[str, str],
    n: int,
    semilla: int,
) -> tuple[list[dict], dict[str, dict[str, str]]]:
    """Devuelve (papeleta, clave).

    - `preguntas` es {id: texto en español} del set dorado (para mostrar al evaluador).
    - Solo se usan los ids que tienen respuesta en AMBOS finalistas (comparación justa).
    - El orden opción_1/opción_2 se aleatoriza por par con `semilla` (reproducible).
    """
    comunes = sorted(set(resp_a) & set(resp_b) & set(preguntas))
    rng = random.Random(semilla)
    rng.shuffle(comunes)
    elegidos = comunes[:n]

    papeleta: list[dict] = []
    clave: dict[str, dict[str, str]] = {}
    for i, pid in enumerate(elegidos, 1):
        par_id = f"par{i:02d}"
        # Aleatoriza qué modelo cae en opción_1 (True = A primero).
        a_primero = rng.random() < 0.5
        if a_primero:
            op1, op2, m1, m2 = resp_a[pid], resp_b[pid], modelo_a, modelo_b
        else:
            op1, op2, m1, m2 = resp_b[pid], resp_a[pid], modelo_b, modelo_a
        papeleta.append(
            {"par_id": par_id, "pregunta": preguntas[pid], "opcion_1": op1, "opcion_2": op2}
        )
        clave[par_id] = {"id_pregunta": pid, "opcion_1": m1, "opcion_2": m2}
    return papeleta, clave


# ---------------------------------------------------------------------------
# Agregación de votos (función pura)
# ---------------------------------------------------------------------------
def agregar_votos(votos: list[dict], clave: dict[str, dict[str, str]]) -> dict:
    """Agrega votos {par_id, evaluador, voto∈'1'/'2'} usando la clave de des-anonimizado.

    Devuelve preferencia por modelo (nº y %), nº de juicios, nº de evaluadores y el
    acuerdo entre evaluadores (media, por par, de la fracción que votó la opción
    mayoritaria: 1,0 = unánime en cada par, 0,5 = división máxima).
    """
    preferencia: Counter = Counter()
    votos_por_par: dict[str, list[str]] = defaultdict(list)  # par_id → [modelos votados]
    evaluadores: set[str] = set()
    n_juicios = 0

    for v in votos:
        par_id, voto = v.get("par_id"), str(v.get("voto", "")).strip()
        if par_id not in clave or voto not in ("1", "2"):
            continue  # voto inválido o par desconocido: se ignora
        modelo = clave[par_id][f"opcion_{voto}"]
        preferencia[modelo] += 1
        votos_por_par[par_id].append(modelo)
        evaluadores.add(str(v.get("evaluador", "")))
        n_juicios += 1

    # Acuerdo inter-evaluador: por cada par con ≥2 votos, fracción del voto mayoritario.
    acuerdos = []
    for modelos in votos_por_par.values():
        if len(modelos) >= 2:
            top = Counter(modelos).most_common(1)[0][1]
            acuerdos.append(top / len(modelos))
    acuerdo = round(sum(acuerdos) / len(acuerdos), 2) if acuerdos else None

    total = sum(preferencia.values()) or 1
    ganador = preferencia.most_common(1)[0][0] if preferencia else None
    return {
        "preferencia": dict(preferencia),
        "preferencia_pct": {m: round(100 * c / total, 1) for m, c in preferencia.items()},
        "ganador": ganador,
        "n_juicios": n_juicios,
        "n_evaluadores": len({e for e in evaluadores if e}),
        "acuerdo_inter_evaluador": acuerdo,
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def _escribir_papeleta(papeleta: list[dict], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["par_id", "pregunta", "opcion_1", "opcion_2", "voto"])
        w.writeheader()
        for p in papeleta:
            w.writerow({**p, "voto": ""})  # columna 'voto' vacía para que el humano marque 1/2


def _cmd_generar(args: argparse.Namespace) -> None:
    from evals import esquema

    preguntas = {p.id: p.pregunta for p in esquema.cargar_set_dorado()}
    resp_a = respuestas_por_id(_leer_csv(args.a))
    resp_b = respuestas_por_id(_leer_csv(args.b))
    papeleta, clave = construir_pares(
        args.a.stem, args.b.stem, resp_a, resp_b, preguntas, args.n, args.semilla
    )
    _SALIDA.mkdir(parents=True, exist_ok=True)
    _escribir_papeleta(papeleta, _SALIDA / "papeleta.csv")
    (_SALIDA / "clave.json").write_text(
        json.dumps(clave, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Papeleta ({len(papeleta)} pares) → {_SALIDA / 'papeleta.csv'}")
    print(f"Clave (NO enseñar) → {_SALIDA / 'clave.json'}")
    print("Reparte copias de la papeleta; cada evaluador marca 1 o 2 en la columna 'voto'.")


def _cmd_agregar(args: argparse.Namespace) -> None:
    clave = json.loads((_SALIDA / "clave.json").read_text(encoding="utf-8"))
    votos = _leer_csv(args.votos)
    resumen = agregar_votos(votos, clave)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


def main() -> None:
    from evals import forzar_utf8_consola

    forzar_utf8_consola()
    parser = argparse.ArgumentParser(description="Test ciego humano entre finalistas (H6).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generar", help="Genera papeleta anonimizada + clave.")
    g.add_argument("--a", type=Path, required=True, help="CSV del finalista A.")
    g.add_argument("--b", type=Path, required=True, help="CSV del finalista B.")
    g.add_argument("--n", type=int, default=20, help="Nº de pares (preguntas).")
    g.add_argument("--semilla", type=int, default=7, help="Semilla de aleatorización.")
    g.set_defaults(func=_cmd_generar)

    a = sub.add_parser("agregar", help="Agrega los votos de los evaluadores.")
    a.add_argument("--votos", type=Path, required=True, help="CSV: par_id,evaluador,voto.")
    a.set_defaults(func=_cmd_agregar)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
