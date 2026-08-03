# Medición H8 — Latencia del chat en streaming

Medición de la latencia **percibida** del endpoint SSE `POST /api/ask/stream` (Hito 8)
con el bench `scripts/bench_streaming.py`, contra un backend real y sus proveedores
reales. Complementa el [ADR-009](../decisiones/ADR-009-streaming.md): allí se justifica
*por qué* streaming; aquí se mide *cuánto* mejora la experiencia.

## Qué se mide

Tres tiempos por pregunta, y sus percentiles sobre 15 corridas:

- **TTFT** (*time-to-first-token*): del envío al primer token. Es cuándo desaparece el
  "pensando…" y el niño **empieza a leer**. La métrica que más importa.
- **VOZ** (*time-to-first-audio*): al primer `audio_chunk` (la **primera frase hablada**).
- **TOTAL**: hasta el evento `fin` (respuesta completa + toda su voz sintetizada).

## Configuración de la corrida

- **Fecha:** 2026-08-03 · máquina del usuario.
- **LLM:** Groq `llama-3.3-70b-versatile` (default de H6, streaming real de tokens).
- **Traducción:** DeepL · **Voz:** ElevenLabs Flash (TTS por frases, con caché en disco).
- **Retrieval:** embeddings `multi-minilm` + reranker `jina-v2` (config de H4).
- **Método:** 2 corridas de calentamiento (cargan embeddings/reranker/Chroma) + 15
  medidas, preguntas a `t-rex` que recuperan por RAG (respuesta larga, no la fija de
  SIN_INFO). Rate limit subido para no degradar el bench.

## Resultados — vía RAG (streaming token a token), n=15

| métrica | p50 | p95 | media | min | max |
|---|---|---|---|---|---|
| **TTFT** (empieza a leer) | **0,92 s** | **1,18 s** | 0,96 s | 0,80 s | 1,30 s |
| **VOZ** (primera frase hablada) | 2,30 s | 2,87 s | 1,88 s | 0,98 s | 3,26 s |
| **TOTAL** (texto + voz completos) | 3,88 s | 5,57 s | 4,02 s | 2,17 s | 5,74 s |

## Lectura

- **El niño empieza a leer en ~0,9 s (p95 1,2 s).** Ese es el gran efecto del streaming:
  antes de H8, con la respuesta "de una vez", el niño esperaba a que se generara la
  respuesta **completa** (≈ el TOTAL, ~4 s de media, p95 5,6 s) sin ver nada. El streaming
  baja el tiempo hasta el primer contenido **de ~4 s a <1 s** (≈4× en percepción).
- **La primera voz llega en ~2,3 s** porque el TTS se sintetiza **por frases**: no espera a
  la respuesta entera. El TTFT de voz es más variable (bimodal) según la longitud de la
  primera frase y si su audio estaba cacheado.
- **TOTAL** sigue siendo de varios segundos (es la respuesta entera + toda su voz), pero ya
  no bloquea la experiencia: para cuando termina, el niño lleva rato leyendo y escuchando.

## Reproducir

```powershell
# Arranca el backend (rate limit alto para no degradar la medición)
$env:RATE_LIMIT_ASK="1000/minute"; uv run uvicorn backend.main:app --port 8000
# En otra terminal
uv run python scripts/bench_streaming.py --n 15 --calentamiento 2
```
