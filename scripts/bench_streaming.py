"""scripts/bench_streaming.py — Latencia del chat en streaming (Hito 8)
=====================================================================

Mide la latencia PERCIBIDA del endpoint SSE `POST /api/ask/stream` contra un backend
real (con sus proveedores reales: DeepL + LLM + ElevenLabs). Reporta tres tiempos por
pregunta y sus percentiles p50/p95:

  - TTFT  (time-to-first-token): del envío al primer evento `token`. Es lo que percibe
          el niño: cuándo desaparece el "pensando…" y empieza a leer.
  - VOZ   (time-to-first-audio): al primer evento `audio_chunk` (la primera frase hablada).
  - TOTAL: hasta el evento `fin` (respuesta completa + toda su voz sintetizada).

Uso (con el backend ya arrancado en otra terminal):
    uv run python -m scripts.bench_streaming --n 12 --calentamiento 2

El backend debe apuntar al proveedor que se quiera medir (p. ej. groq, el default de H6).
Conviene arrancarlo con el rate limit alto para no degradar el bench:
    RATE_LIMIT_ASK=1000/minute uv run uvicorn backend.main:app
"""

import argparse
import statistics
import time

import httpx

# Preguntas realistas para un personaje CON documentos (vía RAG, el caso que se
# streamea token a token). Se rotan para no medir siempre la misma. Elegidas para que
# recuperen bien (respuesta larga, no la fija de SIN_INFO): el bench separa igualmente
# las respuestas fijas por si alguna cae a SIN_INFO.
PREGUNTAS = [
    ("t-rex", "¿por qué tienes los brazos tan pequeños?"),
    ("t-rex", "¿eras el dinosaurio más grande de todos?"),
    ("t-rex", "¿cómo cazabas a otros animales?"),
    ("t-rex", "¿cuántos dientes tenías en la boca?"),
    ("t-rex", "¿cómo de grande y pesado eras?"),
]


def _percentil(datos: list[float], q: float) -> float:
    """Percentil q (0-100) por interpolación lineal; datos sin ordenar."""
    if not datos:
        return float("nan")
    xs = sorted(datos)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * (q / 100.0)
    bajo = int(pos)
    frac = pos - bajo
    if bajo + 1 < len(xs):
        return xs[bajo] + (xs[bajo + 1] - xs[bajo]) * frac
    return xs[bajo]


def _una_corrida(cliente: httpx.Client, url: str, personaje: str, pregunta: str) -> dict:
    """Lanza una pregunta en streaming y cronometra TTFT, primera voz y total."""
    t0 = time.perf_counter()
    ttft = voz = total = None
    n_tokens = 0
    with cliente.stream(
        "POST",
        f"{url}/api/ask/stream",
        json={"personaje_id": personaje, "pregunta": pregunta},
        timeout=60.0,
    ) as r:
        r.raise_for_status()
        evento_actual = None
        for linea in r.iter_lines():
            if linea.startswith("event:"):
                evento_actual = linea[len("event:") :].strip()
                ahora = time.perf_counter() - t0
                if evento_actual == "token":
                    n_tokens += 1
                    if ttft is None:
                        ttft = ahora
                elif evento_actual == "audio_chunk" and voz is None:
                    voz = ahora
                elif evento_actual == "fin":
                    total = ahora
                elif evento_actual == "error":
                    raise RuntimeError("el backend devolvió un evento 'error'")
    return {"ttft": ttft, "voz": voz, "total": total, "n_tokens": n_tokens}


def main() -> None:
    ap = argparse.ArgumentParser(description="Bench de latencia del streaming (H8).")
    ap.add_argument("--url", default="http://127.0.0.1:8000", help="Base del backend.")
    ap.add_argument("--n", type=int, default=12, help="Corridas medidas.")
    ap.add_argument(
        "--calentamiento", type=int, default=2, help="Corridas de calentamiento (no cuentan)."
    )
    args = ap.parse_args()

    cliente = httpx.Client()
    print(
        f"Bench de streaming → {args.url}  ({args.n} corridas, {args.calentamiento} de calentamiento)\n"
    )

    # Calentamiento: la primera petición carga embeddings/reranker/cliente de Chroma.
    for i in range(args.calentamiento):
        p, q = PREGUNTAS[i % len(PREGUNTAS)]
        _una_corrida(cliente, args.url, p, q)
        print(f"  calentamiento {i + 1}/{args.calentamiento} ok")

    filas = []
    for i in range(args.n):
        p, q = PREGUNTAS[i % len(PREGUNTAS)]
        m = _una_corrida(cliente, args.url, p, q)
        filas.append(m)
        print(
            f"  {i + 1:2d}/{args.n}  TTFT={m['ttft']:.2f}s  "
            f"voz={m['voz'] if m['voz'] is None else round(m['voz'], 2)}  "
            f"total={m['total']:.2f}s  ({m['n_tokens']} tokens)"
        )

    # Separamos el caso STREAMING real (RAG: muchos tokens) del de respuesta FIJA
    # (SIN_INFO: 1 token), porque mezclarlos falsea los percentiles del streaming.
    streaming = [f for f in filas if f["n_tokens"] > 3]
    fijas = [f for f in filas if f["n_tokens"] <= 3]

    def _tabla(titulo: str, muestras: list[dict]) -> None:
        print("\n" + "=" * 56)
        print(f"{titulo}  (n={len(muestras)})")
        print(f"{'métrica':<10}{'p50':>10}{'p95':>10}{'media':>10}{'min':>8}{'max':>8}")
        print("-" * 56)
        for clave, etiqueta in (("ttft", "TTFT"), ("voz", "VOZ"), ("total", "TOTAL")):
            vals = [f[clave] for f in muestras if f[clave] is not None]
            if not vals:
                print(f"{etiqueta:<10}{'—':>42}  (sin datos)")
                continue
            print(
                f"{etiqueta:<10}"
                f"{_percentil(vals, 50):>9.2f}s"
                f"{_percentil(vals, 95):>9.2f}s"
                f"{statistics.mean(vals):>9.2f}s"
                f"{min(vals):>7.2f}s"
                f"{max(vals):>7.2f}s"
            )
        print("=" * 56)

    _tabla("STREAMING (vía RAG, token a token)", streaming)
    if fijas:
        _tabla("RESPUESTA FIJA (SIN_INFO, 1 token)", fijas)
    print(
        "\nTTFT = cuándo el niño empieza a leer · VOZ = primera frase hablada · TOTAL = respuesta+voz completas"
    )


if __name__ == "__main__":
    main()
