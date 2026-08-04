# ADR-011 — Arquitectura híbrida: percepción local, generación en la nube

- **Estado:** aceptada
- **Fecha:** 2026-08-01
- **Hito:** H0 (regla fundacional) / reafirmada en H4–H8
- **Rama:** transversal (gobierna todas las decisiones de IA)

## Contexto

El hardware de desarrollo y demo es un Windows 11 con **16 GB de RAM y una GPU de 6 GB de
VRAM**. Hay que decidir, para cada pieza de IA (embeddings, reranker, STT, LLM, TTS, imagen),
si corre **en local** o **en la nube**. La decisión gobierna el peso del despliegue, el coste,
la latencia y —esto es clave para la memoria— **qué datos del menor salen del PC**.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| **A. Todo en local** | Coste cero, sin dependencia de red, máxima privacidad | Un LLM/imagen decentes no caben en 6 GB; inferencia lenta e inestable; arrastra torch/CUDA |
| **B. Todo en la nube** | Simplicidad, calidad alta | Coste por uso; **la voz y las preguntas del menor viajan a terceros**; dependencia total de red |
| **C. Híbrida (elegida)** | Los modelos pequeños (percepción/recuperación) van en local sobre CPU/GPU modesta; los grandes (generativos) en la nube | Dos mundos que mantener; un fallback nube→local que gestionar |

## Medición

Reparto por tamaño de modelo y viabilidad en 6 GB (no es una medición de laboratorio, es un
criterio de capacidad, tabulado en `docs/PLAN.md §2`):

| Pieza | Dónde | Motivo |
|---|---|---|
| Embeddings | Local (CPU, ONNX) | 120M–570M par.; calidad equivalente a API; sin torch (ver [ADR-004](ADR-004-embeddings-multilingues.md)) |
| Reranker | Local (CPU, ONNX) | 568M par.; quita una llamada de red del camino crítico ([ADR-006](ADR-006-reranker.md)) |
| STT | Local (GPU ~1,5 GB) o nube | Gratis y **la voz del niño no sale del PC** ([ADR-008](ADR-008-stt-local.md)) |
| LLM | **Nube** | Un 4B cuantizado (lo que cabe en 6 GB) no da la calidad necesaria ([ADR-007](ADR-007-eleccion-llm.md)) |
| TTS | **Nube** (ElevenLabs) | Local en español es notablemente peor; es el producto ([ADR-013](ADR-013-tts-elevenlabs.md)) |
| Imagen | **Nube** (Replicate) | Generar en 6 GB es lento e inviable para una demo |

## Decisión

**Los modelos pequeños de percepción y recuperación van en local; los modelos generativos
grandes van en la nube.**

## Qué se descarta y por qué

- **Todo en local (A):** descartado por capacidad — el LLM y la generación de imagen que caben
  en 6 GB no alcanzan la calidad que pide el producto, y meter torch/CUDA reintroduce la
  complejidad de GPU que precisamente se quería evitar.
- **Todo en la nube (B):** descartado por privacidad. El efecto secundario clave de la opción C
  es que **toda la voz y todo el historial de preguntas del menor se procesan localmente**
  (embeddings, reranker y —si se activa— STT). Eso es el eje del capítulo de RGPD, no una nota
  al pie. Mandar la voz del niño a un tercero por defecto sería el camino contrario.

## Consecuencias

- El backend es **ligero**: no depende de torch ni CUDA para arrancar (`uv sync` funciona en
  cualquier máquina). Las piezas locales usan `fastembed`/CTranslate2 (ONNX/CPU).
- El STT local es una **dependencia opcional** con **fallback automático a la nube**: si no
  carga, la app nunca se queda muda.
- Se acepta la dependencia de red para las piezas generativas y su coste por uso (mitigado con
  free tiers y el blindaje del [ADR-001](ADR-001-candado-tunel.md)).
- **A revisar si:** cambia el hardware (una GPU de 16–24 GB haría viable un LLM local decente) o
  si la privacidad exigiera mover también el TTS a local (hoy revisado y descartado en el
  [ADR-013](ADR-013-tts-elevenlabs.md)).
