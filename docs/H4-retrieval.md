# H4 — Retrieval multilingüe local

- **Rama madre:** `feat/h4-retrieval` (los sub-hitos se mergean aquí)
- **Semana:** S3 (semana completa)
- **Depende de:** H3 con OK. **Sin la línea base este hito no se puede evaluar.**
- **Prioridad que sirve:** #2 (calidad) y #4 (coste)

## Objetivo

Sustituir el apaño de traducción por un retrieval multilingüe local. En un RAG,
**la calidad del retrieval domina sobre la elección del LLM**: un modelo mejor no
puede responder desde un chunk que nunca recibió.

## El problema que se arregla

DeepL no está en el sistema porque haga falta: está para tapar que ChromaDB usa
por defecto `all-MiniLM-L6-v2`, que es monolingüe inglés. De ahí sale toda la
cadena: traducir los documentos al subirlos, traducir la pregunta en cada
consulta, una dependencia dura en el camino crítico ("sin DeepL no hay chat"),
+150–400 ms por pregunta, y el español coloquial del niño normalizado por el
camino. Además DeepL se usa como **detector de idioma**, que es gastar cuota de
traducción en algo que `lingua-py` hace local y gratis.

## Método: un cambio por sub-rama, cada uno con su medición

Si se meten los cuatro juntos y mejora un 18 %, no se sabe de dónde vino.
Aislarlos convierte cuatro commits en cuatro secciones de la memoria con datos.

**Cada sub-hito: rama propia → ejecutar runner → comparar con la medición
anterior → escribir ADR → merge a `feat/h4-retrieval`.**

---

## H4.1 — Embeddings multilingües (`feat/h4-retrieval-embeddings`)

**Librería: `fastembed`** (ONNX Runtime). Importante: **no** usar
`sentence-transformers`, que arrastra torch (~2 GB) y rompe la propiedad de la
que presume el proyecto en `requirements-backend.txt` ("no necesita torch").
`fastembed` sirve los mismos modelos en ONNX sobre CPU.

- Modelo inicial: `multilingual-e5-small` (120M par., corre en CPU sin tocar la GPU).
- Comparar contra: `BGE-M3` (568M, más lento, suele ganar en cross-lingual).
- **Cuidado con los prefijos de e5**: exige `query:` en las consultas y
  `passage:` en los documentos. Si se olvidan, degrada de forma silenciosa.
- Cambiar la `embedding_function` de la colección de Chroma. Requiere
  **reindexado completo** y nombre de colección nuevo y versionado (el repo ya
  usa ese patrón con `documentos_en`; usar p. ej. `documentos_ml_e5`).

**Medir:** recall@3, acierto de origen, distancias por banda, latencia de
retrieval. Comparar contra `BASELINE.csv`.

**Consecuencia esperada:** los umbrales del Evaluator (0,75 / 0,95) quedan
inválidos — son números atados a MiniLM. Recalibrar **con el runner**, no a ojo.

---

## H4.2 — Troceado por estructura (`feat/h4-retrieval-chunking`)

Hoy: `RecursiveCharacterTextSplitter(800, 120)` sobre artículos Markdown de
Wikipedia, que tira los encabezados a la basura.

- Usar `MarkdownHeaderTextSplitter` para trocear por secciones y luego el
  recursivo dentro de cada sección si hace falta.
- **Prefijar cada chunk con su ruta de encabezados**:
  `"Peter Pan > El País de Nunca Jamás > Los Niños Perdidos: <texto>"`.
- Guardar la ruta también en los metadatos del chunk.

Doble beneficio: el embedding gana el contexto que hoy pierde, y el desplegable
"¿De dónde lo he sacado?" pasa a mostrar la procedencia real. Eso, en una app
educativa, es **funcionalidad**, no depuración — ver §Extra.

**Medir:** recall@3 principalmente. Es la métrica que más debería moverse.

---

## H4.3 — Reranker (`feat/h4-retrieval-reranker`)

- Recuperar `top_k=10` en vez de 3.
- Pasarlos por `bge-reranker-v2-m3` (cross-encoder multilingüe, ~10–50 ms en CPU
  vía `fastembed`).
- Quedarse con los 3 mejores.
- **El score del reranker sustituye a la vez a la distancia coseno y al juez
  LLM.**

**Decisión importante que probablemente salga de aquí:** es muy posible que el
reranker haga innecesario el Evaluator híbrido. Si el runner lo confirma,
**retirar el juez LLM y documentarlo**. Retirar código propio con datos delante
es señal de madurez, no de fracaso, y es de las mejores cosas que se pueden
escribir en una memoria.

**Medir:** acierto de origen (debería subir), latencia (debería *bajar*, porque
se quita una llamada de red), coste (baja, una llamada menos al LLM).

---

## H4.4 — DeepL fuera (`feat/h4-retrieval-sin-deepl`) — ❌ DESCARTADO CON DATOS

**No se ejecuta.** La premisa —"ya no hace falta traducir"— se **midió y no se
sostiene** en este corpus. De-risk retrieval-only (misma colección multi-minilm +
estructura + reranker jina-v2), comparando por pregunta del set dorado:

| | recall@3 chunk | ruteo global |
|---|---|---|
| Traducido (DeepL, H4.3) | 90,9 % | 82,2 % |
| Español directo (sin DeepL) | **85,5 %** (−5,4) | **71,1 %** (−11,1) |

El corpus es **inglés** (Wikipedia): T-rex, Sherlock… son artículos en inglés. Traducir
la pregunta la mantiene *monolingüe EN-EN*, que casa mejor que cross-lingual ES→EN; y
DeepL, de paso, **normaliza las faltas** del español infantil ("bibes", "medias"…), un
segundo beneficio que el español crudo pierde. La latencia tampoco justifica el cambio:
el reranker (~665 ms) domina y la llamada a DeepL (~150 ms) es ruido a su lado.

**Decisión:** se **mantiene DeepL** (el dato defiende la traducción) y H4 se **congela en
H4.3** (§Plan B). Quitar DeepL solo tendría sentido con un **corpus en español** (retrieval
monolingüe ES-ES); queda como trabajo futuro condicionado a esa decisión de producto.
Los prompts en español y `lingua` como detector de idioma se posponen con él.

---

## Extra (barato, alto valor)

Desacoplar `fuentes` de `DEBUG`. Hoy las fuentes sólo se envían al frontend si
`DEBUG` está activo. Enseñar las fuentes a un niño de 10 años es **pedagogía**,
no depuración: merecen dos flags distintos (`DEBUG` y `MOSTRAR_FUENTES`).

## Criterios de aceptación (puerta) — H4 cerrado en H4.3

- [x] Tres sub-ramas ejecutadas, cada una con su medición y su ADR (004/005/006).
      La cuarta (H4.4) **descartada con datos**, no ejecutada (ver arriba).
- [x] Tabla comparativa acumulada: baseline → +embeddings → +chunking → +reranker
      (+ columna H4.4 con el dato del descarte). En `docs/EVALUACION.md §9`.
- [x] **Recall@3 (chunk) mejora respecto a la línea base:** 78,2 → **90,9 %**. (El
      recall de fichero estaba saturado al 100 %; la métrica que gobierna H4 es el
      recall de chunk, introducido en H4.1.)
- [x] Acierto de ruteo ≥ línea base: 66,7 → **82,2 %**.
- [~] Latencia del bloque de retrieval ≤ línea base: **NO** — el reranker la sube a
      ~665 ms (191 ms baseline). Trade-off **medido y aceptado** (ADR-006): la app no
      es tiempo real y la calidad pesa más; revertible en caliente (`RERANKER=off`).
- [x] Umbrales recalibrados con datos del runner, no a ojo (ADR-004/006).
- [ ] `DEEPL_API_KEY` deja de ser obligatoria: **no se logra** — H4.4 descartado; el
      dato defiende mantener la traducción. DeepL sigue obligatoria para el chat.
- [x] La configuración antigua sigue seleccionable y reproduce la línea base
      (defaults de código: `minilm-en` + `recursivo` + `RERANKER=off`).
- [x] `pytest` en verde (103 tests); CI verde al abrir el PR a `dev`.

## Evidencia a entregar para el OK

1. La tabla comparativa de las cinco columnas.
2. Los cuatro ADRs.
3. Decisión razonada sobre si se retira el Evaluator LLM.
4. Informe de hito.

## Riesgo y plan B

Si al final de S3 no hay mejora medida, **congelar en el mejor sub-hito logrado**
y documentar el resto como trabajo futuro. No arrastrar H4 a S4: el estudio de
LLMs necesita su semana entera.

## Instrucción de arranque para Claude Code

> Lee `docs/PLAN.md`, `docs/plan/H4-retrieval.md` y `docs/EVALUACION.md`.
> Trabaja **un sub-hito por sesión**, en su propia rama, y **ejecuta el runner
> después de cada uno** antes de pasar al siguiente. Usa `fastembed`, NO
> `sentence-transformers` (no queremos torch). Genera un ADR por sub-hito. Dame
> el plan antes de escribir código.
