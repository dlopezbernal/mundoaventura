# ADR-004 — Embeddings multilingües locales (fastembed) + recalibración de umbrales

- **Estado:** aceptada
- **Fecha:** 2026-08-02
- **Hito:** H4.1 (`feat/h4-retrieval-embeddings`)
- **Rama madre:** `feat/h4-retrieval`

## Contexto

ChromaDB usaba su embedding_function por defecto, `all-MiniLM-L6-v2`, **monolingüe
inglés**. De ahí venía toda la dependencia de DeepL: traducir los documentos al
subirlos y la pregunta en cada consulta. En un RAG, la calidad del retrieval domina
sobre el LLM. Objetivo de H4.1: embeddings **multilingües locales** (paso previo a
quitar DeepL en H4.4), midiendo la mejora contra `BASELINE.csv`.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| A. `sentence-transformers` (e5-small/BGE-M3) | Modelos fuertes | Arrastra **torch (~2 GB)**; rompe la promesa "sin torch" del proyecto |
| B. `fastembed` + `paraphrase-multilingual-MiniLM-L12-v2` (118M, 384-dim) | ONNX/CPU sin torch; rápido; multilingüe; sin prefijos | Algo menos fuerte que e5-large |
| C. `fastembed` + `multilingual-e5-large` (560M, 1024-dim) | El más fuerte cross-lingual | 2.24 GB de descarga y **más lento en CPU** → arriesga el gate de latencia; exige prefijos query/passage |

**Nota:** `multilingual-e5-small` (el que sugería el plan) **no está** en el catálogo
de `fastembed` 0.8; el análogo pequeño disponible es `paraphrase-multilingual-MiniLM-L12-v2`.

## Medición

Backend seleccionable (ajuste `EMBEDDING_BACKEND`): `minilm-en` reproduce la línea
base; `multi-minilm` es el nuevo. Corrida completa del runner (100×3), comparada con
`BASELINE.csv`. Colección versionada propia (`documentos_ml_minilm`), reindexada.

| Métrica | Baseline (minilm-en, BAJO 0,75) | H4.1 (multi-minilm, BAJO 0,80) | Δ |
|---|---|---|---|
| **recall@3 chunk** (retrieval real) | 78,2 % | **81,8 %** | **+3,6** |
| **latencia de retrieval** (media) | 191,7 ms | **27,3 ms** | **7× más rápido** |
| Acierto de ruteo (RAG vs no-RAG) | 66,7 % | **70,0 %** | +3,3 |
| recall@3 fichero | 100 % | 100 % | = (saturado) |
| Responde en español | 99 % | 100 % | + |
| Roto de personaje | 0 % | 0 % | = |

> **recall@3 a nivel de CHUNK, nuevo en H4.1:** el recall de fichero estaba saturado
> al 100 % (cada personaje tiene 1–2 ficheros), así que no discriminaba. Se añadió un
> `respuesta_contiene` (palabra clave en inglés) a las 55 preguntas literal/inferencial
> y se mide si algún chunk recuperado la contiene. Esa es la métrica de retrieval que
> gobierna todo H4.

## Decisión

**Opción B.** `fastembed` (ONNX/CPU, sin torch) con
`paraphrase-multilingual-MiniLM-L12-v2` como backend `multi-minilm`. Umbral BAJO del
Evaluator recalibrado **0,75 → 0,80** con los datos del runner.

### Recalibración del umbral (con datos, no a ojo)

Las distancias del nuevo modelo cambian de escala (RAG-esperado mediana 0,676 vs
no-RAG 0,829). Explorando umbrales sobre las distancias medidas:

| BAJO | Global | literal | inferencial | fuera_dominio | sin_respuesta |
|---|---|---|---|---|---|
| 0,75 | 70 % | 67 | 68 | 75 | 73 |
| **0,80** | **70 %** | **70** | **80** | **65** | **60** |
| 0,85 | 66 % | 73 | 88 | 45 | 40 |
| 0,917 (max accuracy) | 73 % | 97 | 96 | **35** | **40** |

Se elige **0,80**: mejora el grounding de las preguntas reales del niño sin
**colapsar** el rechazo de fuera-de-dominio. El máximo de accuracy (0,917) sobreajusta
a la mezcla RAG-pesada del set (61 % RAG-esperado) y dispararía la alucinación anclada
en preguntas de fuera de dominio — un mal negocio de producto pese a subir 3 puntos.

## Qué se descarta y por qué

- **sentence-transformers (A):** torch rompe la propiedad "backend ligero, sin
  GPU/torch" que el proyecto defiende; `fastembed` sirve ONNX sobre CPU.
- **e5-large (C):** su calidad no compensa 2,24 GB de descarga y una latencia de
  retrieval mayor en CPU, que pondría en riesgo el gate "latencia ≤ baseline".
- **Umbral max-accuracy 0,917:** se descarta por el colapso de fuera-de-dominio.

## Consecuencias

- **Código:** `services/embeddings.py` (backend seleccionable, embeddings manuales
  para modelos que exigen prefijos); indexado y consulta ramifican por backend;
  colección versionada por backend. Dependencia nueva: `fastembed`.
- **Configuración:** ajuste `EMBEDDING_BACKEND` (`minilm-en`|`multi-minilm`|`e5-large`),
  seleccionable en caliente. `minilm-en` + BAJO 0,75/0,95 reproduce la línea base.
- **Métrica nueva:** recall@3 a nivel de chunk (`respuesta_contiene` en el set dorado).
- **Deuda/limitación aceptada:** el umbral es una calibración provisional; el
  **reranker (H4.3)** debe sustituir esta decisión y resolver el trade-off de
  fuera-de-dominio. El umbral es único para todos los backends (cambiar de backend
  exige ajustarlo).
- **Revisar en:** H4.3 (reranker, que probablemente jubila el umbral) y H4.4 (quitar
  DeepL: la ganancia multilingüe se verá mayor consultando en español directo).
