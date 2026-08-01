# Evaluación — metodología y línea base

Este documento describe **cómo se mide** la calidad del sistema y registra la
**línea base** contra la que se comparará todo cambio posterior (H4 en adelante).
Sin este instrumento, "creo que ha mejorado" no es defendible; con él, se responde
con una tabla.

> **Regla:** la línea base (`evals/resultados/BASELINE.csv`) es **inmutable**. No se
> regenera al cambiar el sistema; es el punto de referencia congelado. Cada mejora
> produce una corrida nueva que se compara contra ella.

## 1. El banco de pruebas

- **Set dorado** (`evals/set_dorado.yaml`): 100 preguntas, 20 por personaje activo,
  con distribución deliberada **6 literal / 5 inferencial / 4 fuera de dominio /
  3 sin respuesta / 2 ambigua**. Escritas en **español infantil real** (sin
  acentos, con faltas, frases cortas), porque es lo que teclea el usuario real.
- **Set de seguridad** (`evals/set_seguridad.yaml`): 18 preguntas adversariales
  (muerte, violencia, miedo, salir del papel, datos personales, inyección). El
  juicio de "tacto" es humano; no se puntúa automáticamente.
- **Fixture de retrieval congelado** (`evals/fixtures/retrieval_*.json`): los chunks
  recuperados una sola vez sobre el set dorado. Permite comparar **generadores**
  (H6) sin que cada corrida recupere chunks distintos (aísla retriever de generador).

## 2. El runner

`evals/runner.py` orquesta el pipeline por etapas **reutilizando `rag_service`**
(sin modificarlo): traducción (DeepL) → retrieval (ChromaDB) → Evaluator → generación
(LLM). Dos modos: `--modo completo` (mide el sistema entero) y
`--modo retrieval-congelado` (solo evaluator + generación, para H6). Cada pregunta se
genera **3 veces con `temperature=0`**: las métricas deterministas salen iguales y la
σ mide el ruido residual del LLM alojado. El TTS se omite (caro y ajeno al texto).

Salidas por corrida: `evals/resultados/<fecha>_<etiqueta>.csv` (una fila por
pregunta × repetición) + `.html` (informe legible) + resumen por consola.

## 3. Métricas (deterministas, sin juez LLM)

| Métrica | Qué mide |
|---|---|
| **Acierto de ruteo** | ¿el Evaluator acertó en fundamentar (RAG) o no (GENERAL/SIN_INFO)? Se mide RAG vs no-RAG, no el string exacto: el reparto GENERAL/SIN_INFO depende de un flag de config, y ambos significan "no fundamentado". |
| **Recall@3** | ¿está el fichero fuente esperado entre los 3 chunks recuperados? |
| **Distancia** | mejor distancia coseno (para calibrar los umbrales del Evaluator). |
| **Idioma** | ¿responde en español? (`lingua`, offline). |
| **Legibilidad INFLESZ** | índice de Szigriszt-Pazos (perspicuidad). Objetivo **≥ 80 "muy fácil"** (primaria). También se calcula Fernández Huerta. Sílabas con `pyphen`. |
| **Roto de personaje** | busca fugas ("como IA", "según el contexto", "no puedo"). |
| **Longitud / latencia / coste** | palabras y frases; ms por etapa; tokens × tarifa. |

**Reproducibilidad:** las métricas deterministas dan el mismo valor ante la misma
entrada (test en `tests/test_evals.py`); con `temperature=0` las columnas
deterministas son estables entre repeticiones.

## 4. Configuración del sistema evaluado (línea base)

La línea base mide el sistema **tal y como está hoy**. La config que condiciona el
resultado se archiva junto a la corrida:

| Ajuste | Valor |
|---|---|
| LLM | `meta/meta-llama-3-8b-instruct` |
| Embeddings | `all-MiniLM-L6-v2` (por defecto de ChromaDB, CPU) · sin reranker |
| Evaluator | modo `umbral` · umbral BAJO 0.75 · ALTO 0.95 |
| `PERMITIR_CONOCIMIENTO_GENERAL` | **false** (fuera de dominio → mensaje fijo `SIN_INFO`, sin LLM) |
| RAG top-k | 3 · LLM max_tokens 300 |
| Traducción | DeepL ES→EN |

## 5. Línea base — resultados

100 preguntas × 3 repeticiones = **300 filas, 0 errores**. Fecha: 2026-08-01.
Fichero: `evals/resultados/BASELINE.csv` (informe: `BASELINE.html`).

### Global

| Métrica | Valor |
|---|---|
| Acierto de ruteo (RAG vs no-RAG) | **66,7 %** |
| Recall@3 | 100 % |
| Responde en español | 99 % |
| Roto de personaje | 0 % |
| INFLESZ medio | 69,9 (σ 18,6) → banda *normal* |
| Respuestas "muy fácil" (INFLESZ ≥ 80) | 25 % |
| Palabras/respuesta (media) | 16 |
| Latencia de generación (media) | 373 ms |
| Coste total estimado (300 gen.) | ~0,005 USD |

### Por tipo de pregunta

| Tipo | Ruteo OK | Distancia media | INFLESZ medio |
|---|---|---|---|
| literal | 50,0 % | 0,736 | 74,6 |
| inferencial | 68,0 % | 0,628 | 74,5 |
| fuera de dominio | 80,0 % | 0,849 | 63,9 |
| sin respuesta | 80,0 % | 0,854 | 66,9 |
| ambigua | (no se puntúa) | 0,876 | 60,9 |

Distancia coseno media: **RAG 0,589 · no-RAG 0,879** — hay separación, pero las
literales promedian 0,736, pegadas al umbral BAJO (0,75).

## 6. Hallazgos (los que motivan H4–H5)

1. **La mitad de las literales no se fundamentan (ruteo 50 %).** Su distancia media
   (0,736) cae justo por encima del umbral BAJO (0,75): el retrieval encuentra el
   chunk correcto (recall@3 = 100 %) pero el Evaluator lo descarta por poco. Palanca
   clara: **recalibrar el umbral BAJO** o mejorar el retrieval (reranker) en H4.
2. **12 % de las de fuera de dominio se fundamentan por error** (falso RAG): riesgo
   de alucinación anclada. La otra cara del mismo umbral.
3. **Legibilidad por debajo del objetivo:** INFLESZ medio 69,9 (*normal*), solo el
   25 % llega a "muy fácil" (≥ 80). Las respuestas son entendibles pero no del nivel
   de primaria buscado. Palanca: **ajuste de prompt** en H5.
4. **Recall@3 = 100 % es poco discriminante:** cada personaje tiene 1–2 ficheros de
   contenido, así que casi cualquier consulta recupera "el fichero correcto". Mide
   grano grueso (fichero, no fragmento). Mejora futura: verdad de referencia a nivel
   de chunk.
5. **El español infantil con faltas fonéticas confunde a DeepL:** durante la
   construcción del set, "medias" → *socks*, "bibes/bibias" (vives) → *drink*. Se
   suavizaron esas preguntas; el fenómeno queda anotado como riesgo del pipeline de
   traducción (relevante para H4/H5).

## 7. Limitaciones declaradas

- Recall a nivel de fichero (no de fragmento), poco discriminante con pocos documentos.
- El juicio de seguridad/tacto (set adversarial) es humano; no hay métrica automática.
- La línea base refleja `PERMITIR_CONOCIMIENTO_GENERAL=false`: las de fuera de
  dominio se responden con el mensaje fijo, no con conocimiento general del LLM.
- Determinismo sujeto al LLM alojado: a `temperature=0` es casi determinista, no
  garantizado al 100 % (por eso se reporta σ).

## 9. H4 — Mejoras de retrieval (tabla acumulada)

Cada sub-hito de H4 se mide contra la línea base y se acumula aquí. Cambio por
sub-rama, con su ADR (`docs/decisiones/ADR-004…`).

| Métrica | Baseline | H4.1 +embeddings | H4.2 +chunking | H4.3 +reranker | H4.4 −DeepL |
|---|---|---|---|---|---|
| Config | minilm-en (0,75) | multi-minilm (0,80) | + estructura | — | — |
| **recall@3 chunk** | 78,2 % | 81,8 % | **83,6 %** | | |
| **lat. retrieval (ms)** | 191,7 | 27,3 | ~8 | | |
| Acierto de ruteo | 66,7 % | 70,0 % | 71,1 % | | |
| Español | 99 % | 100 % | 100 % | | |
| Roto de personaje | 0 % | 0 % | 0 % | | |

**H4.1 (embeddings multilingües, `multi-minilm`):** recall@3 a nivel de chunk sube
78,2 → 81,8 %, y la latencia de retrieval cae **7×** (191 → 27 ms: `fastembed` embebe
la consulta mucho más rápido que la embedding-function por defecto de Chroma). Al
mismo umbral que la baseline (0,75) el ruteo ya mejora (66,7 → 70 %), efecto puro del
embedding. El umbral se recalibra a 0,80 (equilibrado; ver ADR-004). Nota: el recall
de FICHERO sigue saturado al 100 % (poco discriminante) — por eso la métrica que
gobierna H4 es el recall de **chunk**.

**H4.2 (troceado por estructura, `estructura`):** trocear los `.md` por secciones de
Markdown sube el recall de chunk 81,8 → 83,6 %. Hallazgo medido (ADR-005):
**prefijar el texto** con la ruta de encabezados lo EMPEORA (80,0 %, el prefijo
repetido diluye el embedding), así que la ruta va al metadato `header_path` — que
además da **procedencia real** al desplegable "¿de dónde lo he sacado?" (flag propio
`MOSTRAR_FUENTES`, ya no atado a `DEBUG`). Aplica a `.md`; los `.txt` (libros) caen al
recursivo. Números de retrieval (deterministas); la corrida completa tuvo errores
transitorios de Replicate en la generación (429 del free tier), ajenos al chunking.

## 8. Cómo reproducir

```powershell
uv run python -m evals.runner --modo completo --etiqueta baseline   # regenera una corrida
uv run python -m evals.runner --volcar-fixture                      # regenera el fixture congelado
uv run python -m evals.runner --modo retrieval-congelado            # compara generadores (H6)
```
