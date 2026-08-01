"""
evals/runner.py — Ejecuta el banco de pruebas y produce CSV + HTML (Hito 3)
===========================================================================

Orquesta el pipeline por ETAPAS reutilizando las funciones de rag_service (sin
tocarlas): traducción → retrieval → evaluator → generación. Así puede medir la
latencia de cada etapa, inyectar chunks congelados y SALTARSE el TTS (caro y ajeno
a las métricas de texto).

Dos modos:
  - completo          : traduce y recupera de verdad (mide el sistema entero).
  - retrieval-congelado: lee la pregunta traducida y los chunks de un fixture, y
                         solo ejecuta evaluator + generación (aísla el generador;
                         lo usa H6 para comparar LLMs sin ruido del retriever).

Cada pregunta se genera N veces (por defecto 3) con temperature=0: las métricas
deterministas salen iguales y la σ mide el ruido residual del LLM alojado.

Uso:
  uv run python -m evals.runner --modo completo --etiqueta baseline
  uv run python -m evals.runner --volcar-fixture           # crea el fixture congelado
  uv run python -m evals.runner --modo retrieval-congelado --fixture evals/fixtures/retrieval_XXXX.json
"""

import argparse
import csv
import html
import json
import statistics
import time
from datetime import date
from pathlib import Path

from backend.services import (
    personajes_service,
    rag_service,
    settings_service,
    translation_service,
)
from evals import esquema, metricas

_DIR = Path(__file__).resolve().parent
_RESULTADOS = _DIR / "resultados"
_FIXTURES = _DIR / "fixtures"

# Tarifa ORIENTATIVA (USD por millón de tokens) para el coste estimado. Llama 3 8B
# en Replicate es baratísimo; se puede ajustar. tokens ≈ caracteres/4 (aproximación).
PRECIO_ENTRADA_USD_M = 0.05
PRECIO_SALIDA_USD_M = 0.25


# ---------------------------------------------------------------------------
# Etapas (reutilizan rag_service en solo-lectura)
# ---------------------------------------------------------------------------
def _retrieval(personaje_id: str, pregunta_en: str, k: int) -> tuple[list[str], list[float], list]:
    """Recupera top-k de ChromaDB pidiendo también las fuentes (para recall@3)."""
    col = rag_service._get_collection()
    res = col.query(
        query_texts=[pregunta_en],
        n_results=k,
        where={"personaje_id": personaje_id},
        include=["documents", "distances", "metadatas"],
    )
    docs = (res.get("documents") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    fuentes = [(m or {}).get("source") for m in metas]
    return docs, dists, fuentes


def _generar(
    nombre: str, es_rag: bool, chunks: list[str], pregunta_en: str
) -> tuple[str, str, str]:
    """Genera la respuesta (temperature=0). Devuelve (respuesta, system, user)."""
    if es_rag:
        system, user = rag_service._construir_prompt(nombre, chunks, pregunta_en)
        return (
            rag_service._llamar_llm(system, user, temperature=0.0, etiqueta="RAG-eval"),
            system,
            user,
        )
    if settings_service.get("PERMITIR_CONOCIMIENTO_GENERAL"):
        system, user = rag_service._construir_prompt_general(nombre, pregunta_en)
        return (
            rag_service._llamar_llm(system, user, temperature=0.0, etiqueta="GEN-eval"),
            system,
            user,
        )
    # SIN_INFO: mensaje fijo, sin LLM.
    respuesta = settings_service.rellenar(
        settings_service.get("MENSAJE_SIN_INFORMACION"), nombre=nombre
    )
    return respuesta, "", ""


def _origen_de(es_rag: bool) -> str:
    if es_rag:
        return "RAG"
    return "GENERAL" if settings_service.get("PERMITIR_CONOCIMIENTO_GENERAL") else "SIN_INFO"


def config_evaluacion() -> dict:
    """Config vigente que condiciona el resultado (para archivar junto a la corrida)."""
    return {
        "evaluator_mode": settings_service.get("EVALUATOR_MODE"),
        "umbral_bajo": settings_service.get("EVALUATOR_UMBRAL_BAJO"),
        "umbral_alto": settings_service.get("EVALUATOR_UMBRAL_ALTO"),
        "permitir_conocimiento_general": settings_service.get("PERMITIR_CONOCIMIENTO_GENERAL"),
        "rag_top_k": settings_service.get("RAG_TOP_K"),
        "llm_model": settings_service.get("REPLICATE_LLM_MODEL"),
        "llm_max_tokens": settings_service.get("LLM_MAX_TOKENS"),
    }


def _coste_estimado(system: str, user: str, respuesta: str) -> tuple[int, float]:
    """Estima (tokens_totales, coste_usd) con tokens ≈ caracteres/4."""
    tokens_in = (len(system) + len(user)) // 4
    tokens_out = len(respuesta) // 4
    coste = tokens_in / 1e6 * PRECIO_ENTRADA_USD_M + tokens_out / 1e6 * PRECIO_SALIDA_USD_M
    return tokens_in + tokens_out, round(coste, 6)


# ---------------------------------------------------------------------------
# Evaluación de una pregunta (traducción + retrieval una vez; generación N veces)
# ---------------------------------------------------------------------------
def evaluar_pregunta(
    preg: esquema.PreguntaDorada,
    modo: str,
    fixture: dict | None,
    reps: int,
) -> list[dict]:
    """Devuelve una fila por repetición con todas las métricas."""
    ficha = personajes_service.obtener(preg.personaje_id)
    nombre = ficha["nombre"] if ficha else preg.personaje_id
    k = settings_service.get("RAG_TOP_K")

    # 1) Traducción + 2) Retrieval — una sola vez (deterministas).
    if modo == "completo":
        t0 = time.perf_counter()
        pregunta_en = translation_service.traducir_es_en(preg.pregunta)
        t_trad = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        chunks, dists, fuentes = _retrieval(preg.personaje_id, pregunta_en, k)
        t_ret = (time.perf_counter() - t0) * 1000
    else:  # retrieval-congelado: todo viene del fixture (ni DeepL ni Chroma)
        fila_fix = (fixture or {}).get("retrieval", {}).get(preg.id)
        if fila_fix is None:
            raise ValueError(f"El fixture no tiene la pregunta '{preg.id}'. ¿Está actualizado?")
        pregunta_en = fila_fix["pregunta_en"]
        chunks = fila_fix["chunks"]
        dists = fila_fix["distances"]
        fuentes = fila_fix["fuentes"]
        t_trad = 0.0
        t_ret = 0.0

    recall = metricas.recall_at_k(preg.chunk_esperado, fuentes)
    dist_min = round(min(dists), 4) if dists else None

    filas: list[dict] = []
    for rep in range(1, reps + 1):
        base = {
            "id": preg.id,
            "personaje_id": preg.personaje_id,
            "tipo": preg.tipo.value,
            "origen_esperado": preg.origen_esperado.value,
            "rep": rep,
            "recall_at3": recall,
            "distancia": dist_min,
            "lat_traduccion_ms": round(t_trad, 1),
            "lat_retrieval_ms": round(t_ret, 1),
        }
        try:
            t0 = time.perf_counter()
            es_rag, metodo, _ = rag_service._decidir_origen(chunks, dists, pregunta_en)
            t_eval = (time.perf_counter() - t0) * 1000
            origen = _origen_de(es_rag)

            t0 = time.perf_counter()
            respuesta, sys_p, usr_p = _generar(nombre, es_rag, chunks, pregunta_en)
            t_gen = (time.perf_counter() - t0) * 1000

            infl = metricas.inflesz(respuesta)
            tokens, coste = _coste_estimado(sys_p, usr_p, respuesta)
            roto = metricas.roto_de_personaje(respuesta)
            # Acierto de RUTEO (RAG vs no-RAG), no del string exacto: el reparto
            # GENERAL/SIN_INFO depende de PERMITIR_CONOCIMIENTO_GENERAL (config), y
            # ambos significan "no fundamentado en el RAG". Lo que se mide es si el
            # Evaluator acertó en fundamentar (RAG) o no. Las ambiguas no se puntúan.
            acierto = (
                None
                if preg.origen_esperado.value == "cualquiera"
                else (origen == "RAG") == (preg.origen_esperado.value == "RAG")
            )
            base.update(
                {
                    "origen_obtenido": origen,
                    "acierto_origen": acierto,
                    "metodo": metodo,
                    "idioma": metricas.idioma(respuesta),
                    "es_espanol": metricas.es_espanol(respuesta),
                    "palabras": metricas.contar_palabras(respuesta),
                    "frases": metricas.contar_frases(respuesta),
                    "inflesz": infl,
                    "banda_inflesz": metricas.banda_inflesz(infl),
                    "fernandez_huerta": metricas.fernandez_huerta(respuesta),
                    "roto_personaje": " | ".join(roto),
                    "n_roto": len(roto),
                    "lat_evaluator_ms": round(t_eval, 1),
                    "lat_generacion_ms": round(t_gen, 1),
                    "tokens_est": tokens,
                    "coste_est_usd": coste,
                    "respuesta": respuesta,
                    "error": "",
                }
            )
        except Exception as exc:  # noqa: BLE001 — best-effort: un fallo no aborta la corrida
            base.update(
                {"origen_obtenido": "", "respuesta": "", "error": f"{type(exc).__name__}: {exc}"}
            )
        filas.append(base)
    return filas


# ---------------------------------------------------------------------------
# Agregados para el resumen
# ---------------------------------------------------------------------------
def _media_desv(valores: list[float]) -> tuple[float | None, float | None]:
    vals = [v for v in valores if v is not None]
    if not vals:
        return None, None
    media = round(statistics.mean(vals), 1)
    desv = round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0
    return media, desv


def resumir(filas: list[dict]) -> dict:
    """Calcula los agregados clave (para consola y HTML)."""
    ok = [f for f in filas if not f["error"]]
    con_acierto = [f for f in ok if f["acierto_origen"] is not None]
    con_recall = [f for f in ok if f["recall_at3"] is not None]
    infl_media, infl_desv = _media_desv([f["inflesz"] for f in ok])
    return {
        "n_filas": len(filas),
        "n_error": len(filas) - len(ok),
        "acierto_origen_pct": _pct([f["acierto_origen"] for f in con_acierto]),
        "recall_at3_pct": _pct([f["recall_at3"] for f in con_recall]),
        "es_espanol_pct": _pct([f["es_espanol"] for f in ok]),
        "roto_pct": _pct([f["n_roto"] > 0 for f in ok]),
        "inflesz_media": infl_media,
        "inflesz_desv": infl_desv,
        "muy_facil_pct": _pct([f["banda_inflesz"] == "muy_facil" for f in ok]),
        "palabras_media": _media_desv([f["palabras"] for f in ok])[0],
        "lat_generacion_media_ms": _media_desv([f["lat_generacion_ms"] for f in ok])[0],
        "coste_total_usd": round(sum(f.get("coste_est_usd") or 0 for f in ok), 4),
    }


def _pct(bools: list[bool]) -> float | None:
    if not bools:
        return None
    return round(100 * sum(1 for b in bools if b) / len(bools), 1)


# ---------------------------------------------------------------------------
# Salidas: CSV + HTML
# ---------------------------------------------------------------------------
_COLUMNAS = [
    "id",
    "personaje_id",
    "tipo",
    "origen_esperado",
    "rep",
    "origen_obtenido",
    "acierto_origen",
    "metodo",
    "distancia",
    "recall_at3",
    "idioma",
    "es_espanol",
    "palabras",
    "frases",
    "inflesz",
    "banda_inflesz",
    "fernandez_huerta",
    "roto_personaje",
    "n_roto",
    "lat_traduccion_ms",
    "lat_retrieval_ms",
    "lat_evaluator_ms",
    "lat_generacion_ms",
    "tokens_est",
    "coste_est_usd",
    "respuesta",
    "error",
]


def escribir_csv(filas: list[dict], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNAS, extrasaction="ignore")
        writer.writeheader()
        for fila in filas:
            writer.writerow(fila)


def _tabla_html(titulo: str, datos: dict) -> str:
    filas = "".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
        for k, v in datos.items()
    )
    return f"<h3>{html.escape(titulo)}</h3><table class='resumen'>{filas}</table>"


def escribir_html(filas: list[dict], resumen: dict, meta: dict, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # Resumen por personaje.
    por_pers = {}
    for pid in sorted({f["personaje_id"] for f in filas}):
        por_pers[pid] = resumir([f for f in filas if f["personaje_id"] == pid])
    bloques_pers = "".join(_tabla_html(pid, r) for pid, r in por_pers.items())

    # Tabla detalle (una fila por pregunta×rep).
    cabecera = "".join(f"<th>{html.escape(c)}</th>" for c in _COLUMNAS if c != "respuesta")
    filas_html = ""
    for f in filas:
        celdas = "".join(
            f"<td>{html.escape(str(f.get(c, '')))}</td>" for c in _COLUMNAS if c != "respuesta"
        )
        resp = html.escape((f.get("respuesta") or "")[:400])
        filas_html += (
            f"<tr>{celdas}</tr><tr class='resp'><td colspan='{len(_COLUMNAS) - 1}'>{resp}</td></tr>"
        )

    doc = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Evaluación — {html.escape(meta.get("etiqueta", ""))}</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:2rem;color:#222;}}
 table{{border-collapse:collapse;margin:.5rem 0 1.5rem;font-size:.85rem;}}
 td,th{{border:1px solid #ccc;padding:.25rem .5rem;text-align:left;}}
 table.resumen{{max-width:32rem;}} table.resumen th{{width:16rem;background:#f4f4f4;}}
 .detalle td,.detalle th{{font-size:.75rem;}} tr.resp td{{background:#fafafa;color:#555;font-style:italic;}}
 h1,h2,h3{{margin:.6rem 0;}} .meta{{color:#666;}}
</style></head><body>
<h1>Informe de evaluación — {html.escape(meta.get("etiqueta", ""))}</h1>
<p class="meta">Modo: {html.escape(meta.get("modo", ""))} · Fecha: {html.escape(meta.get("fecha", ""))} ·
 Repeticiones: {meta.get("reps", "")} · Preguntas: {meta.get("n_preguntas", "")}</p>
{_tabla_html("Configuración del sistema evaluado", meta.get("config", {}))}
{_tabla_html("Resumen global", resumen)}
<h2>Resumen por personaje</h2>
{bloques_pers}
<h2>Detalle (una fila por pregunta × repetición)</h2>
<table class="detalle"><tr>{cabecera}</tr>{filas_html}</table>
</body></html>"""
    ruta.write_text(doc, encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixture de retrieval congelado
# ---------------------------------------------------------------------------
def volcar_fixture(ruta: Path | None = None) -> Path:
    """Ejecuta el retrieval UNA vez sobre el set dorado y lo vuelca a JSON."""
    preguntas = esquema.cargar_set_dorado()
    k = settings_service.get("RAG_TOP_K")
    retrieval = {}
    for preg in preguntas:
        pregunta_en = translation_service.traducir_es_en(preg.pregunta)
        chunks, dists, fuentes = _retrieval(preg.personaje_id, pregunta_en, k)
        retrieval[preg.id] = {
            "pregunta_en": pregunta_en,
            "chunks": chunks,
            "distances": dists,
            "fuentes": fuentes,
        }
    ruta = ruta or (_FIXTURES / f"retrieval_{date.today().isoformat()}.json")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(
            {
                "generado_en": date.today().isoformat(),
                "rag_top_k": k,
                "chroma_collection": settings_service.get("CHROMA_COLLECTION"),
                "retrieval": retrieval,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return ruta


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------
def run(modo: str, etiqueta: str, reps: int, limite: int | None, fixture_path: Path | None) -> Path:
    preguntas = esquema.cargar_set_dorado()
    if limite:
        preguntas = preguntas[:limite]
    fixture = None
    if modo == "retrieval-congelado":
        if fixture_path is None:
            fixture_path = _ultimo_fixture()
        fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))

    filas: list[dict] = []
    for i, preg in enumerate(preguntas, 1):
        print(f"  [{i}/{len(preguntas)}] {preg.id} ({preg.personaje_id})")
        filas.extend(evaluar_pregunta(preg, modo, fixture, reps))

    resumen = resumir(filas)
    fecha = date.today().isoformat()
    config = config_evaluacion()
    meta = {
        "etiqueta": etiqueta,
        "modo": modo,
        "fecha": fecha,
        "reps": reps,
        "n_preguntas": len(preguntas),
        "config": config,
    }
    base = _RESULTADOS / f"{fecha}_{etiqueta}"
    escribir_csv(filas, base.with_suffix(".csv"))
    escribir_html(filas, resumen, meta, base.with_suffix(".html"))

    print("\n=== Config del sistema evaluado ===")
    for k, v in config.items():
        print(f"  {k:30}: {v}")
    print("\n=== Resumen ===")
    for k, v in resumen.items():
        print(f"  {k:26}: {v}")
    print(f"\nCSV : {base.with_suffix('.csv')}")
    print(f"HTML: {base.with_suffix('.html')}")
    return base.with_suffix(".csv")


def _ultimo_fixture() -> Path:
    fixtures = sorted(_FIXTURES.glob("retrieval_*.json"))
    if not fixtures:
        raise FileNotFoundError("No hay ningún fixture. Genera uno con --volcar-fixture.")
    return fixtures[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Runner de evaluación del RAG (Hito 3).")
    parser.add_argument("--modo", choices=["completo", "retrieval-congelado"], default="completo")
    parser.add_argument("--etiqueta", default="corrida", help="Sufijo de los ficheros de salida.")
    parser.add_argument("--repeticiones", type=int, default=3)
    parser.add_argument("--limite", type=int, default=None, help="Solo las N primeras (pruebas).")
    parser.add_argument("--fixture", type=Path, default=None, help="Ruta del fixture congelado.")
    parser.add_argument(
        "--volcar-fixture", action="store_true", help="Solo genera el fixture de retrieval y sale."
    )
    args = parser.parse_args()

    if args.volcar_fixture:
        ruta = volcar_fixture()
        print(f"Fixture de retrieval congelado escrito en: {ruta}")
        return

    run(args.modo, args.etiqueta, args.repeticiones, args.limite, args.fixture)


if __name__ == "__main__":
    main()
