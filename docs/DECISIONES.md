# Decisiones de arquitectura (ADRs)

Índice de las decisiones técnicas relevantes del proyecto. Cada una tiene su **ADR** (Architecture
Decision Record) en [`decisiones/`](decisiones/): media página, con **contexto → opciones →
medición → decisión → qué se descarta → consecuencias**. La plantilla está en
[ADR-000](decisiones/ADR-000-plantilla.md).

> **Un ADR sin alternativas descartadas es una descripción, no una decisión.** La sección "qué se
> descarta y por qué" es la parte que se defiende ante el tribunal.

## Índice

| # | Decisión | Hito | Estado |
|---|---|---|---|
| [001](decisiones/ADR-001-candado-tunel.md) | Candado del túnel: código de acceso + rate limit + cupo (no autenticación fuerte) | H2 | ✅ aceptada |
| [002](decisiones/ADR-002-concurrencia.md) | Endpoints síncronos (`def`) para no bloquear el event loop | H2 | ✅ aceptada |
| [003](decisiones/ADR-003-metodologia-evaluacion.md) | Metodología de evaluación: métricas deterministas + retrieval congelado | H3 | ✅ aceptada |
| [004](decisiones/ADR-004-embeddings-multilingues.md) | Embeddings multilingües locales (fastembed) + recalibración de umbrales | H4.1 | ✅ aceptada |
| [005](decisiones/ADR-005-troceado-estructural.md) | Troceado por estructura de Markdown (sección sí, prefijo no) | H4.2 | ✅ aceptada |
| [006](decisiones/ADR-006-reranker.md) | Reranker (cross-encoder) + ruteo por puntuación (jubila el LLM-juez) | H4.3 | ✅ aceptada |
| [007](decisiones/ADR-007-eleccion-llm.md) | Elección del LLM generador (estudio comparativo) → **groq-llama70b** | H6 | ✅ aceptada |
| [008](decisiones/ADR-008-stt-local.md) | Transcripción local (STT) con faster-whisper + proveedor seleccionable | H7 | 🟡 propuesta¹ |
| [009](decisiones/ADR-009-streaming.md) | Streaming de la respuesta (SSE) + TTS por frases + caché de audio | H8 | 🟡 propuesta¹ |
| [010](decisiones/ADR-010-seguridad-infantil.md) | Seguridad infantil: anti-inyección, filtro de salida y consentimiento | H9 | ✅ aceptada |
| [011](decisiones/ADR-011-arquitectura-hibrida.md) | Arquitectura híbrida: percepción local, generación en la nube | H0/H4 | ✅ aceptada |
| [012](decisiones/ADR-012-capa-proveedor-openai.md) | Capa de proveedor de LLM compatible con OpenAI | H5 | ✅ aceptada |
| [013](decisiones/ADR-013-tts-elevenlabs.md) | Mantener ElevenLabs (nube) para el TTS | H7/H8 | ✅ aceptada |
| [014](decisiones/ADR-014-retirada-deepl.md) | Retirar DeepL del camino crítico | H4.4 | ❌ **descartada²** |

¹ **propuesta:** mecanismo implementado, con tests verdes en CI; la verificación final en la
máquina del usuario (GPU/WER para el 008; latencia p50/p95 para el 009) queda pendiente porque el
sandbox de desarrollo no tiene GPU/CUDA ni claves para cronometrar el flujo real. No es deuda de
diseño, es una medición que exige el hardware del usuario.

² **descartada con datos:** la hipótesis de quitar DeepL se **midió** y se rechazó (empeoraba el
retrieval); el ADR documenta el experimento. Se conserva porque "qué probamos y por qué no salió"
es tan valioso como lo que sí se adoptó.

## Trazabilidad con el plan del Hito 10

El H10 (`plan/H10-congelacion.md`) lista unos **ADRs mínimos esperados**. Todos están cubiertos;
la numeración real difiere porque el conjunto escrito es más amplio (incluye decisiones de
blindaje, concurrencia, metodología y seguridad que el listado mínimo no enumeraba):

| Esperado en H10 | ADR real |
|---|---|
| Arquitectura híbrida (percepción local, generación nube) | **011** |
| Embeddings multilingües con fastembed | **004** |
| Troceado por encabezados de Markdown | **005** |
| Reranker en lugar del Evaluator LLM | **006** |
| Retirada de DeepL del camino crítico | **014** (descartada) |
| Capa de proveedor compatible con OpenAI | **012** |
| Elección del LLM | **007** |
| STT local con faster-whisper | **008** |
| Mantener ElevenLabs para TTS | **013** |
| Streaming SSE frase a frase | **009** |

## Material relacionado

- La **teoría** detrás de estas decisiones (qué es RAG, chunking, CLIP/T5) →
  [`ANEXO-DIDACTICO.md`](ANEXO-DIDACTICO.md).
- Las **mediciones** que sostienen los ADRs → [`EVALUACION.md`](EVALUACION.md) y
  [`mediciones/`](mediciones/).
- El **diseño del sistema** → [`ARQUITECTURA.md`](ARQUITECTURA.md).
