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
| [001](decisiones/ADR-001-candado-tunel.md) | Candado del túnel: código de acceso + rate limit + cupo (no autenticación fuerte) | H2 | ✅ aceptada³ |
| [002](decisiones/ADR-002-concurrencia.md) | Endpoints síncronos (`def`) para no bloquear el event loop | H2 | ✅ aceptada |
| [003](decisiones/ADR-003-metodologia-evaluacion.md) | Metodología de evaluación: métricas deterministas + retrieval congelado | H3 | ✅ aceptada |
| [004](decisiones/ADR-004-embeddings-multilingues.md) | Embeddings multilingües locales (fastembed) + recalibración de umbrales | H4.1 | ✅ aceptada |
| [005](decisiones/ADR-005-troceado-estructural.md) | Troceado por estructura de Markdown (sección sí, prefijo no) | H4.2 | ✅ aceptada |
| [006](decisiones/ADR-006-reranker.md) | Reranker (cross-encoder) + ruteo por puntuación (jubila el LLM-juez) | H4.3 | ✅ aceptada |
| [007](decisiones/ADR-007-eleccion-llm.md) | Elección del LLM generador (estudio comparativo) → **groq-llama70b** | H6 | ✅ aceptada |
| [008](decisiones/ADR-008-stt-local.md) | Transcripción local (STT) con faster-whisper + proveedor seleccionable | H7 | ✅ aceptada¹ |
| [009](decisiones/ADR-009-streaming.md) | Streaming de la respuesta (SSE) + TTS por frases + caché de audio | H8 | ✅ aceptada¹ |
| [010](decisiones/ADR-010-seguridad-infantil.md) | Seguridad infantil: anti-inyección, filtro de salida y consentimiento | H9 | ✅ aceptada |
| [011](decisiones/ADR-011-arquitectura-hibrida.md) | Arquitectura híbrida: percepción local, generación en la nube | H0/H4 | ✅ aceptada |
| [012](decisiones/ADR-012-capa-proveedor-openai.md) | Capa de proveedor de LLM compatible con OpenAI | H5 | ✅ aceptada |
| [013](decisiones/ADR-013-tts-elevenlabs.md) | Mantener ElevenLabs (nube) para el TTS | H7/H8 | ✅ aceptada |
| [014](decisiones/ADR-014-retirada-deepl.md) | Retirar DeepL del camino crítico | H4.4 | ❌ **descartada²** |
| [015](decisiones/ADR-015-despliegue-nativo-vps.md) | Despliegue nativo en VPS (uv + systemd + Caddy), no Docker ni PaaS | F2 | ✅ aceptada |
| [016](decisiones/ADR-016-sesion-familia-endpoints-caros.md) | Sesión de familia obligatoria en los endpoints que cuestan dinero | H9.2/F2 | ✅ aceptada³ |
| [017](decisiones/ADR-017-pwa-twa.md) | App de Android como PWA + TWA, no Capacitor ni React Native | F2 | ✅ aceptada⁴ |

¹ **medido en la máquina del usuario, no en CI.** Ambos mecanismos van verdes en CI, y sus
verificaciones con hardware y proveedores reales están hechas: la **latencia del streaming**
(009) el 2026-08-03 → [`mediciones/H8-latencia-streaming.md`](mediciones/H8-latencia-streaming.md)
(TTFT p50 **0,92 s**, p95 1,18 s, n=15); la **ruta de STT local en GPU** (008) el 2026-08-03 →
[`mediciones/H7-stt-gpu.md`](mediciones/H7-stt-gpu.md) (falta `cublas64_12.dll` en Windows y el
**fallback a la nube se verificó en vivo**). Lo único que sigue sin tabla es el **WER por
proveedor** del 008, y es **mejora futura fuera del alcance de entrega**: exige grabar ~20 clips
con voces infantiles que no existen en el repositorio, no una GPU. La decisión del 008 no depende
de esa tabla.

² **descartada con datos:** la hipótesis de quitar DeepL se **midió** y se rechazó (empeoraba el
retrieval); el ADR documenta el experimento. Se conserva porque "qué probamos y por qué no salió"
es tan valioso como lo que sí se adoptó.

³ **par 001 + 016.** El 001 sigue vigente en lo suyo (rate limit, cupo, degradación amable), pero
se escribió para el modelo de amenaza del **túnel efímero**. Con el despliegue permanente
(2026-08-05) el **016 lo extiende y lo sustituye parcialmente**: `ACCESS_CODE` viaja dentro del
bundle de la SPA, así que es público de facto, y los endpoints caros exigen además **sesión de
familia**. El 001 lleva un addendum fechado que remite al 016.

⁴ **parcialmente ejecutada:** la **PWA instalable está en producción**; el **APK (TWA) no está
generado**, porque falta exactamente el tramo que depende del *keystore* de firma (huella SHA-256
en `assetlinks.json`). Procedimiento completo en [`APK-ANDROID.md`](APK-ANDROID.md); pendiente
anotado en [`TRABAJO-FUTURO.md`](TRABAJO-FUTURO.md). La app instalada desde el navegador se ve y
se comporta igual que el APK.

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

Los ADR **015–017** son **posteriores al H10**: nacen de la **Fase 2** (llevar la app a un
servidor permanente y a un móvil), no del plan de hitos. Ver
[`TRABAJO-FUTURO.md §Fase 2`](TRABAJO-FUTURO.md).

## Material relacionado

- La **teoría** detrás de estas decisiones (qué es RAG, chunking, CLIP/T5) →
  [`ANEXO-DIDACTICO.md`](ANEXO-DIDACTICO.md).
- Las **mediciones** que sostienen los ADRs → [`EVALUACION.md`](EVALUACION.md) y
  [`mediciones/`](mediciones/).
- El **diseño del sistema** → [`ARQUITECTURA.md`](ARQUITECTURA.md).
