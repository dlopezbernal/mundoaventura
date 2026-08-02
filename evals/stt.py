"""
evals/stt.py — Evaluación comparativa de transcripción (STT) por WER (Hito 7)
=============================================================================

Mide qué proveedor de STT transcribe mejor la voz —idealmente INFANTIL, que es donde
todos los ASR flojean— con la métrica estándar **WER** (Word Error Rate): la fracción
de palabras que hay que insertar, borrar o sustituir para convertir la transcripción
automática en la de referencia (hecha a mano). 0 = perfecto; 1 = todo mal.

Dos capas, como en el resto de `evals/`:
  - NÚCLEO determinista y testeable sin audio: `normalizar()` y `wer()`.
  - ARNÉS que necesita los clips reales (máquina del usuario): transcribe cada clip
    con cada proveedor (vía `stt_service`, cambiando `STT_PROVIDER` y restaurándolo),
    mide WER y latencia, y saca la tabla del ADR-008.

El WER se calcula sobre texto NORMALIZADO (minúsculas, sin puntuación, espacios
colapsados): comparar la puntuación/mayúsculas que cada ASR inventa distinto sería
medir ruido, no acierto. Se conservan los acentos (el español los usa; quitarlos sería
demasiado indulgente).

Uso (en la máquina del usuario, con clips grabados):
  uv run python -m evals.stt --manifest evals/stt_clips/manifest.yaml \\
      --proveedores local,elevenlabs,groq
"""

import argparse
import re
import statistics
import time
from pathlib import Path

import yaml

_DIR = Path(__file__).resolve().parent

_RE_TOKEN = re.compile(r"\w+", re.UNICODE)


def normalizar(texto: str) -> list[str]:
    """Texto → lista de palabras normalizadas (minúsculas, sin puntuación).

    `\\w+` con UNICODE conserva letras acentuadas, ñ y dígitos; descarta signos y
    colapsa los espacios. Es la base justa para el WER: mide palabras, no puntuación.
    """
    return _RE_TOKEN.findall(texto.lower())


def _distancia_edicion(ref: list[str], hip: list[str]) -> int:
    """Distancia de Levenshtein a nivel de PALABRA (nº de inserciones+borrados+sustituciones).

    Programación dinámica clásica O(n·m). Cada palabra es un símbolo: una palabra mal
    transcrita cuenta 1, no importa cuántas letras falle (así funciona el WER).
    """
    n, m = len(ref), len(hip)
    if n == 0:
        return m
    if m == 0:
        return n
    # fila[j] = distancia entre ref[:i] y hip[:j]; se actualiza fila a fila.
    previa = list(range(m + 1))
    for i in range(1, n + 1):
        actual = [i] + [0] * m
        for j in range(1, m + 1):
            coste = 0 if ref[i - 1] == hip[j - 1] else 1
            actual[j] = min(
                previa[j] + 1,  # borrado
                actual[j - 1] + 1,  # inserción
                previa[j - 1] + coste,  # sustitución (o acierto)
            )
        previa = actual
    return previa[m]


def wer(referencia: str, hipotesis: str) -> float:
    """Word Error Rate entre la transcripción de referencia y la automática.

    WER = (S + D + I) / N, con N = nº de palabras de la referencia. Si la referencia
    está vacía: 0.0 si la hipótesis también lo está, 1.0 si no (todo son inserciones).
    """
    ref = normalizar(referencia)
    hip = normalizar(hipotesis)
    if not ref:
        return 0.0 if not hip else 1.0
    return round(_distancia_edicion(ref, hip) / len(ref), 4)


# ---------------------------------------------------------------------------
# Arnés de evaluación (necesita los clips reales: máquina del usuario)
# ---------------------------------------------------------------------------
def cargar_manifest(ruta: Path) -> list[dict]:
    """Lee el manifiesto de clips: lista de {audio: <ruta>, referencia: <texto a mano>}."""
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or []
    if not isinstance(datos, list):
        raise ValueError(f"{ruta.name} debe ser una lista de clips {{audio, referencia}}.")
    return datos


def evaluar_proveedor(proveedor: str, clips: list[dict], base: Path) -> dict:
    """Transcribe todos los clips con UN proveedor y agrega WER medio + latencia mediana.

    Cambia `STT_PROVIDER` al proveedor pedido (y lo restaura el llamador). Mide por clip
    el WER contra la referencia y la latencia de la transcripción.
    """
    from backend.services import settings_service, stt_service

    settings_service.set_many({"STT_PROVIDER": proveedor})
    stt_service.reiniciar()

    wers: list[float] = []
    latencias: list[float] = []
    for clip in clips:
        audio = (base / clip["audio"]).read_bytes()
        t0 = time.perf_counter()
        texto = stt_service.transcribir(audio)
        latencias.append((time.perf_counter() - t0) * 1000)
        wers.append(wer(clip["referencia"], texto))
    return {
        "proveedor": proveedor,
        "n_clips": len(clips),
        "wer_medio": round(statistics.mean(wers), 4) if wers else None,
        "wer_desv": round(statistics.pstdev(wers), 4) if len(wers) > 1 else 0.0,
        "lat_mediana_ms": round(statistics.median(latencias), 1) if latencias else None,
        "lat_max_ms": round(max(latencias), 1) if latencias else None,
    }


def evaluar(manifest_ruta: Path, proveedores: list[str]) -> list[dict]:
    """Evalúa varios proveedores sobre el mismo manifiesto. Restaura STT_PROVIDER al final."""
    from backend.services import settings_service, stt_service

    clips = cargar_manifest(manifest_ruta)
    base = manifest_ruta.resolve().parent
    original = settings_service.get("STT_PROVIDER")
    try:
        return [evaluar_proveedor(p, clips, base) for p in proveedores]
    finally:
        settings_service.set_many({"STT_PROVIDER": original})
        stt_service.reiniciar()


def _imprimir(filas: list[dict]) -> None:
    from evals import forzar_utf8_consola

    forzar_utf8_consola()
    print("\n=== Comparativa STT (WER + latencia) — H7 ===")
    print(
        f"{'proveedor':>12} {'clips':>6} {'WER medio':>10} {'σ':>7} {'lat med ms':>11} {'lat max ms':>11}"
    )
    for f in filas:
        print(
            f"{f['proveedor']:>12} {f['n_clips']:>6} "
            f"{f['wer_medio'] if f['wer_medio'] is not None else '-':>10} "
            f"{f['wer_desv']:>7} "
            f"{f['lat_mediana_ms'] if f['lat_mediana_ms'] is not None else '-':>11} "
            f"{f['lat_max_ms'] if f['lat_max_ms'] is not None else '-':>11}"
        )
    print(
        "\n(WER: menor es mejor. Con voces infantiles todos los ASR suben; por eso el "
        "paso de confirmación en la UI.)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara proveedores de STT por WER (H7).")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_DIR / "stt_clips" / "manifest.yaml",
        help="YAML con la lista de {audio, referencia}.",
    )
    parser.add_argument(
        "--proveedores",
        default="local,elevenlabs,groq",
        help="Lista separada por comas (por defecto: local,elevenlabs,groq).",
    )
    args = parser.parse_args()
    proveedores = [p.strip() for p in args.proveedores.split(",") if p.strip()]
    _imprimir(evaluar(args.manifest, proveedores))


if __name__ == "__main__":
    main()
