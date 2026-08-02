"""
evals/juez.py — Juez LLM de fidelidad al contexto (Hito 6, Nivel 2)
===================================================================

Comprueba si CADA afirmación de una respuesta está respaldada por las notas (chunks)
recuperadas. Es la única dimensión que sí necesita un juez LLM (el resto de métricas
son deterministas, en `metricas.py`).

Dos reglas no negociables del doc H6 §4:
  1. El juez debe ser un modelo DISTINTO y MÁS POTENTE que los candidatos (nada de
     autoevaluación). Se configura en `candidatos.yaml` (bloque `juez:`).
  2. El juez se VALIDA antes de usarlo: se puntúan 20 respuestas a mano y se compara
     con su veredicto. Acuerdo ≥85% ⇒ es un instrumento y se usa; <85% ⇒ es ruido con
     aspecto de dato, se descarta y se declara como limitación.

CÓMO SE EJECUTA (máquina del usuario): el juez pasa por `llm_service`, así que ANTES
de correrlo hay que fijar el LLM al modelo juez (LLM_PROVIDER/LLM_MODEL/LLM_BASE_URL +
su clave), no a un candidato. El prompt va en INGLÉS, como el resto de prompts al LLM
del proyecto (invariante "entra en inglés, sale en español").

Uso:
  # 1) Validar el juez contra las 20 respuestas puntuadas a mano:
  uv run python -m evals.juez validar --muestras evals/juez_validacion.yaml
  # 2) Puntuar la fidelidad de un candidato (une fixture[chunks] + CSV[respuesta]):
  uv run python -m evals.juez fidelidad --fixture evals/fixtures/retrieval_XXXX.json \\
      --csv evals/resultados/AAAA_h6-gemini-flash.csv
"""

import argparse
import json
import re
from pathlib import Path

import yaml

from backend.services import llm_service

_DIR = Path(__file__).resolve().parent

_SYSTEM_JUEZ = (
    "You are a strict fact-checker. You are given NOTES (retrieved source snippets) and "
    "a RESPONSE written for a child. Decide whether every claim in the RESPONSE is "
    "supported by the NOTES. A claim that is not in the NOTES is unsupported, even if it "
    "is true in general. Reply with ONLY a JSON object, no prose, no code fences:\n"
    '{"fundamentada": true|false, "afirmaciones_sin_respaldo": ["..."], '
    '"justificacion": "..."}'
)


def construir_prompt(notas: list[str], respuesta: str) -> tuple[str, str]:
    """(system, user) para el juez. Las notas van numeradas; la respuesta, literal."""
    bloque_notas = "\n".join(f"[{i}] {n}" for i, n in enumerate(notas, 1)) or "(no notes)"
    user = f"NOTES:\n{bloque_notas}\n\nRESPONSE:\n{respuesta}"
    return _SYSTEM_JUEZ, user


def parsear_veredicto(texto: str) -> dict:
    """Extrae el JSON del veredicto de forma robusta (tolera fences y texto alrededor).

    Devuelve siempre un dict con las tres claves; si no se puede parsear, marca
    fundamentada=None y guarda el texto crudo en 'justificacion' (para inspección).
    """
    crudo = texto.strip()
    # Quita fences ```json ... ``` si los hubiera.
    crudo = re.sub(r"^```(?:json)?|```$", "", crudo, flags=re.MULTILINE).strip()
    # Se queda con el primer objeto {...} balanceado que aparezca.
    m = re.search(r"\{.*\}", crudo, flags=re.DOTALL)
    if m:
        try:
            datos = json.loads(m.group(0))
            return {
                "fundamentada": datos.get("fundamentada"),
                "afirmaciones_sin_respaldo": datos.get("afirmaciones_sin_respaldo", []),
                "justificacion": datos.get("justificacion", ""),
            }
        except json.JSONDecodeError:
            pass
    return {
        "fundamentada": None,
        "afirmaciones_sin_respaldo": [],
        "justificacion": f"(no parseable) {texto[:200]}",
    }


def juzgar(notas: list[str], respuesta: str) -> dict:
    """Llama al juez (temperature=0) y devuelve el veredicto parseado."""
    system, user = construir_prompt(notas, respuesta)
    salida = llm_service.completar(
        system, user, max_tokens=300, temperature=0.0, etiqueta="Juez-fidelidad"
    )
    return parsear_veredicto(salida)


def acuerdo(humanos: list[bool], jueces: list[bool | None]) -> dict:
    """% de acuerdo entre el veredicto humano y el del juez (solo pares comparables).

    Los veredictos del juez que no se pudieron parsear (None) se excluyen del cómputo
    y se cuentan aparte, para no inflar ni hundir el acuerdo con un fallo de formato.
    """
    comparables = [(h, j) for h, j in zip(humanos, jueces, strict=True) if j is not None]
    no_parseables = sum(1 for j in jueces if j is None)
    if not comparables:
        return {"acuerdo_pct": None, "n": 0, "no_parseables": no_parseables}
    aciertos = sum(1 for h, j in comparables if h == j)
    return {
        "acuerdo_pct": round(100 * aciertos / len(comparables), 1),
        "n": len(comparables),
        "no_parseables": no_parseables,
        "usar": round(100 * aciertos / len(comparables), 1) >= 85.0,
    }


# ---------------------------------------------------------------------------
# Preparación de muestras para puntuar la fidelidad de un candidato
# ---------------------------------------------------------------------------
def preparar_muestras(fixture: dict, filas_csv: list[dict]) -> list[dict]:
    """Une notas (fixture[chunks] por id) con la respuesta del candidato (CSV, 1ª rep).

    Solo prepara las preguntas que en el CSV salieron por RAG: la fidelidad al contexto
    solo tiene sentido cuando la respuesta debía fundamentarse en las notas.
    """
    retrieval = fixture.get("retrieval", {})
    muestras: list[dict] = []
    vistos: set[str] = set()
    for f in filas_csv:
        pid = f.get("id")
        if not pid or pid in vistos or f.get("error") or f.get("origen_obtenido") != "RAG":
            continue
        chunks = retrieval.get(pid, {}).get("chunks")
        if not chunks or not f.get("respuesta"):
            continue
        muestras.append({"id": pid, "notas": chunks, "respuesta": f["respuesta"]})
        vistos.add(pid)
    return muestras


def fidelidad_pct(veredictos: list[dict]) -> dict:
    """% de respuestas FUNDAMENTADAS (excluye las no parseables del denominador)."""
    validos = [v for v in veredictos if v["fundamentada"] is not None]
    if not validos:
        return {"fidelidad_pct": None, "n": 0}
    fund = sum(1 for v in validos if v["fundamentada"])
    return {"fidelidad_pct": round(100 * fund / len(validos), 1), "n": len(validos)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cmd_validar(args: argparse.Namespace) -> None:
    """Valida el juez contra respuestas puntuadas a mano.

    El YAML de muestras es una lista de: {notas: [...], respuesta: "...",
    veredicto_humano: true|false}.
    """
    muestras = yaml.safe_load(args.muestras.read_text(encoding="utf-8")) or []
    humanos = [bool(m["veredicto_humano"]) for m in muestras]
    jueces = [juzgar(m["notas"], m["respuesta"])["fundamentada"] for m in muestras]
    res = acuerdo(humanos, jueces)
    print(json.dumps({"info_llm": llm_service.info(), **res}, ensure_ascii=False, indent=2))
    if res.get("acuerdo_pct") is not None:
        veredicto = "SE USA" if res["usar"] else "SE DESCARTA (documentar como limitación)"
        print(f"\nAcuerdo {res['acuerdo_pct']}% (n={res['n']}) → el juez {veredicto}.")


def _cmd_fidelidad(args: argparse.Namespace) -> None:
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    with args.csv.open(encoding="utf-8") as f:
        import csv as _csv

        filas = list(_csv.DictReader(f))
    muestras = preparar_muestras(fixture, filas)
    veredictos = [juzgar(m["notas"], m["respuesta"]) for m in muestras]
    print(json.dumps({"info_llm": llm_service.info(), **fidelidad_pct(veredictos)}, indent=2))


def main() -> None:
    from evals import forzar_utf8_consola

    forzar_utf8_consola()
    parser = argparse.ArgumentParser(description="Juez LLM de fidelidad al contexto (H6).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validar", help="Valida el juez contra respuestas puntuadas a mano.")
    v.add_argument("--muestras", type=Path, required=True)
    v.set_defaults(func=_cmd_validar)

    fi = sub.add_parser("fidelidad", help="Puntúa la fidelidad de un candidato.")
    fi.add_argument("--fixture", type=Path, required=True)
    fi.add_argument("--csv", type=Path, required=True)
    fi.set_defaults(func=_cmd_fidelidad)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
