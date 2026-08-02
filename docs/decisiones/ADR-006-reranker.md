# ADR-006 — Reranker (cross-encoder) + ruteo por puntuación (jubila el LLM-juez)

- **Estado:** aceptada
- **Fecha:** 2026-08-02
- **Hito:** H4.3 (`feat/h4-retrieval-reranker`)
- **Rama madre:** `feat/h4-retrieval`

## Contexto

Tras H4.1 (embeddings multilingües) y H4.2 (troceado por estructura), el retrieval es
un **bi-encoder**: embebe pregunta y ficha por separado y compara vectores (distancia
coseno). Es barato pero nunca "lee" pregunta y ficha juntas, así que pierde matiz — y
el ADR-004 dejó abierto el trade-off **fundamentar (literal) vs rechazar
(fuera-de-dominio)**: ningún umbral coseno equilibraba ambos.

Un **cross-encoder** (reranker) sí lee el par junto ("¿responde este texto a esta
pregunta?") y puntúa la relevancia con mucho más criterio. El patrón estándar de un RAG
bueno es un **embudo**: el bi-encoder recupera N candidatos baratos, el cross-encoder
los reordena y nos quedamos con el top-K. Objetivo de H4.3: medir si el reranker mejora
recall y ruteo, y si su puntuación puede **sustituir al LLM-juez** del Evaluator.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| A. `jinaai/jina-reranker-v2-base-multilingual` (fastembed/ONMX, 278M) | Multilingüe (puntúa ES contra EN, medido); habilita H4.4 (quitar DeepL); sin torch | Cross-encoder pesado: ~650 ms en CPU |
| B. Reranker inglés ligero (`ms-marco-MiniLM-L6`) | ~4× más rápido | Monolingüe inglés → callejón sin salida para H4.4 |
| C. Sin reranker (statu quo H4.2) | Latencia mínima (~8 ms) | Se queda el trade-off no resuelto del ADR-004 |

`fastembed` ya estaba (embeddings): `TextCrossEncoder` **no añade dependencia nueva**
ni torch, coherente con el "backend ligero" del proyecto.

## Medición (retrieval-only, sin LLM → esquiva el rate-limit de Replicate)

Reranker activo sobre la colección de H4.2 (`documentos_ml_minilm`, estructura) — **no
exige reindexar** (el reranking es en consulta). Reutiliza las traducciones del fixture
de H3 (no gasta DeepL). Métricas de retrieval sobre el set dorado.

### Recall y latencia por nº de candidatos

| Candidatos | recall@3 chunk | latencia retrieval+rerank (mediana) |
|---|---|---|
| 10 | 92,7 % | 1212 ms |
| **5** | **90,9 %** | **665 ms** |

Con **5 candidatos** el recall casi iguala a 10 (−1,8) a **mitad de latencia**: es el
punto elegido.

### Ruteo por puntuación del reranker (candidatos=5)

Las distribuciones de score separan mucho mejor que el coseno (RAG-esperado mediana
−1,87; no-RAG mediana −3,15). Explorando el umbral:

| UMBRAL | Global | literal | inferencial | fuera_dominio | sin_respuesta |
|---|---|---|---|---|---|
| −2,25 | 76,7 | 60 | 76 | 90 | 93 |
| −2,50 | 76,7 | 67 | 80 | 85 | 80 |
| **−2,75** | **82,2** | **77** | **92** | **80** | **80** |
| −3,00 | 82,2 | 90 | 96 | 65 | 67 |

Se elige **−2,75**: el punto **equilibrado** de mayor global — por primera vez en todo
H4 los cuatro tipos quedan altos a la vez (77/92/80/80). Bajar a −3,00 sube literal a
costa de **colapsar** el rechazo de fuera-de-dominio (80→65), el mismo mal negocio que
descartó el umbral max-accuracy en el ADR-004.

### Comparativa acumulada

| Métrica | Baseline | H4.1 | H4.2 | **H4.3 (reranker)** | Δ vs H4.2 |
|---|---|---|---|---|---|
| **recall@3 chunk** | 78,2 % | 81,8 % | 83,6 % | **90,9 %** | **+7,3** |
| **Acierto de ruteo** | 66,7 % | 70,0 % | 71,1 % | **82,2 %** | **+11,1** |
| ruteo equilibrado (4 tipos) | no | no | no | **sí** | — |
| lat. retrieval (mediana) | 191 ms | 27 ms | ~8 ms | **~665 ms** | **+657** |
| LLM-juez (llamada extra) | híbrido | híbrido | híbrido | **jubilado** | −1 llamada |

## Decisión

**Opción A.** Reranker `jina-v2` (`jinaai/jina-reranker-v2-base-multilingual`, fastembed/
ONNX, sin torch), **candidatos=5**, **umbral=−2,75**. Con reranker activo, el Evaluator
**decide el ruteo por la puntuación del cross-encoder** (`score ≥ UMBRAL ⇒ RAG`), lo que
**sustituye al LLM-juez**: el reranker ya hace lo que hacía el juez (leer pregunta+ficha
juntas), mejor y sin una llamada de red.

- **Adoptado como config recomendada de H4** (activado en el DB local + defaults
  calibrados en `config.py`). El **default de código de `RERANKER` sigue `off`**, así que
  un clon limpio reproduce la línea base; adoptar el reranker es un ajuste en caliente.

## Qué se descarta y por qué

- **Ruteo por distancia coseno del top-3 reordenado (en vez de por score):** medido —
  nunca equilibra (máx global 73 % con literal/fd enfrentados). El score del
  cross-encoder es una señal de relevancia estrictamente mejor.
- **Reranker inglés ligero (B):** más rápido pero monolingüe; rompería H4.4 (consultar en
  español sin DeepL). La palanca multilingüe pesa más que la latencia aquí.
- **Candidatos=10:** +1,8 de recall por **el doble** de latencia. No compensa.

## Consecuencias

- **Código:** `services/reranker.py` (cross-encoder perezoso, patrón calcado de
  `embeddings.py`). `rag_service._recuperar_contexto` recupera ancho, reordena por score
  y trunca a top-K, devolviendo también los scores; `_decidir_origen` ramifica al camino
  "rerank" (sin LLM-juez) cuando hay scores. El runner reutiliza `_recuperar_contexto`
  (única fuente del retrieval), añade columna `rerank_score` y archiva la config del
  reranker. **Sin dependencia nueva** (fastembed ya estaba).
- **Configuración:** ajustes `RERANKER` (`off`|`jina-v2`), `RERANK_CANDIDATOS`,
  `RERANK_UMBRAL`, categoría `rag`, **sin `requires_reindex`** (se activa en caliente).
- **Latencia (coste asumido):** el retrieval pasa de ~8 ms a ~650 ms en CPU. El total de
  respuesta sube de ~0,7 s a ~1,3–1,7 s. Aceptable para esta app (no es tiempo real; ya
  hay TTS/imagen de segundos) y es la contrapartida del salto de calidad. Medido en el
  sandbox de desarrollo; **vigilar en el despliegue real** (CPU del túnel/Colab). Es
  revertible al instante (`RERANKER=off`).
- **Evaluator:** con reranker, `EVALUATOR_MODE` y los umbrales coseno quedan **inactivos**
  (solo gobiernan el camino sin reranker). El LLM-juez ya no se llama.
- **Revisar en:** H4.4 — el reranker multilingüe es justo lo que permite recuperar y
  rutear en español sin traducir la pregunta; se espera que la ganancia crezca.
