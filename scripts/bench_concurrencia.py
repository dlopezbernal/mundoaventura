"""
scripts/bench_concurrencia.py — Mide si el event loop se bloquea (H2, tarea 1)
=============================================================================

Objetivo pedagógico
-------------------
Los endpoints del backend son `async def` pero por dentro llaman a SDKs SÍNCRONOS
que hacen I/O de red (`replicate.run`, DeepL, ElevenLabs, ChromaDB). En FastAPI,
un `async def` corre en el **event loop**: si dentro se ejecuta código bloqueante,
**congela el servidor entero** hasta que termina. Basta una pregunta lenta para
que un simple `GET /health` se quede esperando detrás.

La solución (commit 2 de H2) es declarar esos endpoints como `def` normal: FastAPI
los ejecuta en un **threadpool** y el event loop queda libre para atender otras
peticiones. Este script MIDE la diferencia — se corre ANTES del arreglo (endpoints
`async def`) y DESPUÉS (endpoints `def`), y las dos cifras van al informe.

Método (fiel al escenario real)
-------------------------------
- Se levanta un servidor **uvicorn de verdad** en un hilo, sobre un puerto real, y
  se le pega desde el hilo principal con un cliente HTTP independiente. Es la única
  forma honesta de medir "¿cuánto tarda /health MIENTRAS otra petición bloquea?":
  con un cliente ASGI in-process se comparte el mismo event loop y la medición miente.
- Se stubea `rag_service.responder` con un bloqueo determinista (`time.sleep`), que
  SIMULA la I/O de red lenta sin gastar crédito de las APIs ni depender del jitter
  de red. Así la medición refleja SOLO el modelo de concurrencia, no la latencia real.
- Se stubean también las sondas de estado de `/health` (DeepL/ElevenLabs) para que
  NO hagan red: queremos cronometrar el event loop, no una llamada a DeepL.
- Se lanzan 2 peticiones largas a `/api/ask` en paralelo (en hilos cliente) y, con
  ellas en vuelo, se cronometra una tanda de `GET /health` desde el hilo principal.

Uso:  uv run python scripts/bench_concurrencia.py            (bloqueo 3.0 s por defecto)
      uv run python scripts/bench_concurrencia.py --sleep 2  (bloqueo de 2 s)
"""

import argparse
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import uvicorn

# Permite ejecutar el script directamente (`python scripts/bench_concurrencia.py`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services import rag_service, translation_service, voice_service  # noqa: E402

_PUERTO = 8137  # puerto local dedicado al benchmark (evita chocar con el 8000 de dev)


def _instalar_stubs(segundos: float) -> None:
    """Sustituye el pipeline real por un bloqueo controlado y aísla /health de la red."""

    def _responder_lento(personaje_id: str, pregunta: str):
        # time.sleep BLOQUEA el hilo: es justo lo que hace un SDK síncrono de red.
        time.sleep(segundos)
        return {
            "success": True,
            "personaje_id": personaje_id,
            "pregunta": pregunta,
            "respuesta": "(respuesta simulada para el benchmark)",
            "origen": "RAG",
        }

    rag_service.responder = _responder_lento
    # /health no debe tocar la red durante la medición: la cronometramos a ella, no a DeepL.
    translation_service.estado = lambda: {"deepl_ok": True, "deepl_mensaje": "(stub)"}
    voice_service.estado = lambda: {"elevenlabs_ok": True, "elevenlabs_mensaje": "(stub)"}


def _arrancar_servidor() -> uvicorn.Server:
    """Levanta uvicorn en un hilo aparte y espera a que /health responda."""
    from backend.main import app  # importar DESPUÉS de instalar los stubs

    config = uvicorn.Config(app, host="127.0.0.1", port=_PUERTO, log_level="warning")
    servidor = uvicorn.Server(config)
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()

    base = f"http://127.0.0.1:{_PUERTO}"
    for _ in range(100):  # hasta ~10 s de margen para el arranque
        try:
            if httpx.get(f"{base}/health", timeout=0.5).status_code == 200:
                return servidor
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("El servidor de benchmark no arrancó a tiempo.")


def _medir(segundos: float) -> dict:
    _instalar_stubs(segundos)
    servidor = _arrancar_servidor()
    base = f"http://127.0.0.1:{_PUERTO}"
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            # Lanza 2 /api/ask largas EN PARALELO (en hilos cliente).
            futuros = [
                pool.submit(
                    httpx.post,
                    f"{base}/api/ask",
                    json={"personaje_id": "t-rex", "pregunta": "hola"},
                    timeout=segundos + 10,
                )
                for _ in range(2)
            ]
            time.sleep(0.3)  # deja que las 2 peticiones entren en el pipeline

            # Con las 2 asks EN VUELO, cronometra /health desde el hilo principal.
            latencias_ms = []
            for _ in range(5):
                t0 = time.perf_counter()
                r = httpx.get(f"{base}/health", timeout=segundos + 10)
                latencias_ms.append((time.perf_counter() - t0) * 1000)
                assert r.status_code == 200
                time.sleep(0.1)

            for f in futuros:
                f.result()
    finally:
        servidor.should_exit = True

    return {
        "sleep_s": segundos,
        "health_ms_mediana": statistics.median(latencias_ms),
        "health_ms_max": max(latencias_ms),
        "muestras_ms": [round(x, 1) for x in latencias_ms],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mide el bloqueo del event loop (H2).")
    parser.add_argument(
        "--sleep", type=float, default=3.0, help="Segundos que bloquea cada /api/ask."
    )
    args = parser.parse_args()

    res = _medir(args.sleep)

    print("\n=== Benchmark de concurrencia (H2, tarea 1) ===")
    print(f"Bloqueo simulado por peticion : {res['sleep_s']:.1f} s")
    print("/api/ask concurrentes en vuelo: 2")
    print(f"/health · mediana             : {res['health_ms_mediana']:.1f} ms")
    print(f"/health · maximo              : {res['health_ms_max']:.1f} ms")
    print(f"/health · muestras            : {res['muestras_ms']} ms")
    veredicto = "OK (loop libre)" if res["health_ms_max"] < 200 else "BLOQUEADO (loop congelado)"
    print(f"Veredicto                     : {veredicto}")


if __name__ == "__main__":
    main()
