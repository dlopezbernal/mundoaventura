# ADR-012 — Capa de proveedor de LLM compatible con OpenAI

- **Estado:** aceptada
- **Fecha:** 2026-08-02
- **Hito:** H5
- **Rama:** `feat/h5-capa-llm`

## Contexto

Hasta el Hito 5, toda llamada al LLM pasaba directamente por el SDK de Replicate, con su
`input` dict propio, esparcido por `rag_service`. El Hito 6 exige **comparar cinco proveedores
de LLM** con método defendible. Si cambiar de proveedor obligara a tocar código, cada candidato
del estudio introduciría una variable de confusión (¿la diferencia es del modelo o del código?)
y el experimento no sería limpio. Hace falta poder **cambiar de proveedor con configuración, no
con código**.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| **A. Seguir con Replicate a pelo** | Cero trabajo | Imposible comparar proveedores sin reescribir; fuga de capas (rag_service conoce el SDK) |
| **B. Un adaptador propio por proveedor** | Control total de cada API | N adaptadores que mantener; reinventar lo que ya está estandarizado |
| **C. Una sola capa openai-compatible (elegida)** | La mayoría de proveedores exponen un endpoint estilo OpenAI (Groq, Mistral, OpenRouter, Gemini-compat, Ollama local); un solo cliente los cubre todos | Replicate no es openai-compatible → convive como rama `replicate` legacy |

## Medición

No es una decisión que se mida con un número: es una **refactorización que habilita la
medición** del [ADR-007](ADR-007-eleccion-llm.md). Su criterio de corrección es un **test de
fijación** que comprueba que la rama `replicate` reproduce la línea base **byte a byte** (mismo
`input` dict que antes del refactor). Está en `tests/test_h6.py` y va al CI.

## Decisión

Toda llamada al LLM pasa por **`services/llm_service.py`** (`completar`,
`completar_streaming`, `info`), que despacha por el ajuste **`LLM_PROVIDER`**:

- `replicate` (por defecto, LEGACY) — envuelve `replicate_client.run` con el mismo `input` dict
  de siempre; reproduce la línea base.
- `openai` — SDK `openai` con `LLM_BASE_URL` configurable (Groq, Mistral, OpenRouter, Ollama…);
  clave en el secreto `LLM_API_KEY`.

`rag_service._llamar_llm` delega aquí y ya no conoce ningún SDK.

## Qué se descarta y por qué

- **Adaptador por proveedor (B):** descartado por coste de mantenimiento y porque el estándar
  de facto (endpoint openai-compatible) ya unifica a casi todos los proveedores relevantes. Un
  único cliente `openai` con `base_url` variable cubre Groq, Mistral, OpenRouter, Gemini-compat
  y Ollama local sin código específico.
- **Migrar del todo fuera de Replicate:** descartado. Replicate se conserva como default legacy
  para que un clon nuevo reproduzca la línea base exacta sin claves adicionales, y porque su SDK
  (no openai-compatible) sigue siendo el que genera la imagen.

## Consecuencias

- Comparar proveedores en H6 es cambiar `LLM_PROVIDER`/`LLM_MODEL`/`LLM_BASE_URL` + la clave en
  el `.env`, sin tocar código → experimento limpio.
- El streaming real de tokens (H8) se implementa una sola vez, en la capa: `completar_streaming`
  cede el iterador nativo de Replicate y los deltas de `stream=True` de openai.
- Se acepta una rama legacy (`replicate`) que hay que mantener viva junto a la genérica.
- **A revisar si:** aparece un proveedor importante sin endpoint openai-compatible (habría que
  volver a valorar un adaptador puntual para él).
