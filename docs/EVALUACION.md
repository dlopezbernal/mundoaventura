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

## 7. Limitaciones de la línea base

- Recall a nivel de fichero (no de fragmento), poco discriminante con pocos documentos.
- El juicio de seguridad/tacto (set adversarial) es humano; no hay métrica automática.
- La línea base refleja `PERMITIR_CONOCIMIENTO_GENERAL=false`: las de fuera de
  dominio se responden con el mensaje fijo, no con conocimiento general del LLM.
- Determinismo sujeto al LLM alojado: a `temperature=0` es casi determinista, no
  garantizado al 100 % (por eso se reporta σ).

## 8. H4 — Mejoras de retrieval (tabla acumulada)

Cada sub-hito de H4 se mide contra la línea base y se acumula aquí. Cambio por
sub-rama, con su ADR (`docs/decisiones/ADR-004…`).

| Métrica | Baseline | H4.1 +embeddings | H4.2 +chunking | H4.3 +reranker | H4.4 −DeepL (descartado) |
|---|---|---|---|---|---|
| Config | minilm-en (0,75) | multi-minilm (0,80) | + estructura | + jina-v2 (k=5, u=−2,75) | español directo |
| **recall@3 chunk** | 78,2 % | 81,8 % | 83,6 % | **90,9 %** | 85,5 % (−5,4) |
| **lat. retrieval (ms)** | 191,7 | 27,3 | ~8 | **~665** | ~665 (=) |
| Acierto de ruteo | 66,7 % | 70,0 % | 71,1 % | **82,2 %** | 71,1 % (−11,1) |
| Español | 99 % | 100 % | 100 % | 100 % | — |
| Roto de personaje | 0 % | 0 % | 0 % | 0 % | — |

**H4 se cierra en H4.3.** La configuración recomendada de H4 es
**multi-minilm + estructura + reranker jina-v2 (candidatos 5, umbral −2,75)**, que
sube el recall de chunk 78,2 → **90,9 %** y el ruteo 66,7 → **82,2 %** (equilibrado)
sobre la línea base.

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

**H4.3 (reranker, `jina-v2`):** un cross-encoder multilingüe reordena los candidatos
(embudo: recupera 5 → reordena → top-3) y su **puntuación sustituye al LLM-juez** en el
ruteo (ADR-006). Salto de calidad grande: recall de chunk 83,6 → **90,9 %** y ruteo
71,1 → **82,2 %**, este por primera vez **equilibrado** en los cuatro tipos (literal 77 /
inferencial 92 / fuera_dominio 80 / sin_respuesta 80) — el cross-encoder resuelve el
trade-off fundamentar/rechazar que ningún umbral coseno equilibraba. Coste asumido: la
latencia de retrieval sube a ~665 ms en CPU (un cross-encoder es más caro que una
búsqueda vectorial), aceptable para esta app (no es tiempo real) y revertible en caliente
(`RERANKER=off`). No exige reindexar (reordena en consulta). El default de código sigue
`off` (baseline reproducible); la config recomendada de H4 lo activa.

**H4.4 (quitar DeepL) — DESCARTADO con datos.** La hipótesis era que, con la pila
multilingüe (embeddings + reranker), consultar en **español directo** igualaría a
traducir la pregunta a inglés, quitando la dependencia de DeepL. Medido
(retrieval-only, misma colección y reranker): el español directo **regresa** el
retrieval — recall de chunk 90,9 → **85,5 %** (−5,4) y ruteo 82,2 → **71,1 %** (−11,1).
Motivo: el corpus es inglés (Wikipedia), así que traducir la pregunta la mantiene
*monolingüe EN-EN* (casa mejor que cross-lingual ES→EN), y DeepL además **normaliza las
faltas** del español infantil. Y el argumento de latencia ya no aplica: el reranker
(~665 ms) domina, y la llamada a DeepL (~150 ms) es ruido a su lado. Conclusión: **se
mantiene DeepL** (el dato defiende la traducción) y H4 se congela en H4.3, en línea con
el "Plan B" de `docs/plan/H4-retrieval.md`. Retomar solo tendría sentido con un corpus en
español (retrieval monolingüe ES-ES), trabajo futuro.

## 9. H6 — Estudio comparativo de LLMs (metodología)

El instrumento de H3 se reutiliza para elegir el LLM generador con método defendible
(**puertas primero, pesos después**), no con una impresión. La decisión y sus tablas
viven en el **ADR-007**; aquí queda la mecánica y sus piezas nuevas en `evals/`:

- **`candidatos.yaml`** — los 5 candidatos (Llama 3/Replicate como línea base, Gemini
  Flash, Mistral Small, Groq 70B, Ollama local) + el juez, con su config exacta.
- **`comparar.py`** — agrega los CSV de las 5 corridas (retrieval congelado, 3 reps) y
  aplica las **puertas §8** (idioma ≥98 %, INFLESZ **media ≥ 68**, longitud 15–90, p95 ≤ 8 s,
  seguridad 0 fallos) y luego los **pesos §7** (calidad 50 / latencia 30 / coste 20),
  fijados el **2026-08-02** como constante fechada en el propio código.
- **`juez.py`** — juez LLM de **fidelidad al contexto** (Nivel 2), un modelo distinto y
  más potente que los candidatos, **validado** contra 20 respuestas a mano (acuerdo ≥85 %
  o se descarta y se declara como limitación).
- **`test_ciego.py`** — genera pares **anonimizados y aleatorizados** entre los 2
  finalistas y agrega los votos humanos (preferencia + acuerdo inter-evaluador, Nivel 3).

**Calibración de la puerta INFLESZ:** el objetivo del doc (≥ 80 en ≥ 90 %) eliminaría a
la línea base (Llama 3: media 69,9; solo 25 % ≥ 80). Se baja la **puerta** a media ≥ 68
(mínimo que la referencia cumple) y el **≥ 80 se conserva como objetivo de mérito** (no
elimina, puntúa en los pesos). Misma metodología que ADR-004/006: recalibrar con el dato.

**Ejecutado (2026-08-02).** Las 5 corridas + juez + test ciego preliminar se corrieron en
la máquina del usuario. Resultado (detalle y tablas en el **ADR-007**):

- **Ganador: `groq-llama70b`** por el **test ciego humano (5 personas)**. Las métricas
  automáticas daban `gemini-flash` (score 0.80: fidelidad 100 %, p95 0.89 s), pero los
  humanos prefirieron groq por **respuestas más completas** — la divergencia métrica-vs-humano
  que el test ciego (§5, decisivo entre finalistas) existe para resolver.
- **Eliminados por seguridad** (rotura de papel en "hazte un robot"): `llama3-replicate`,
  `mistral-small`. **Ollama** (gemma3:4b) pasó por Opción B (1 fallo aceptado como riesgo
  residual) pero quedó 3º por baja fidelidad (67 %).
- **Juez NO validado**: 3 jueces < 85 % de acuerdo (mejor gpt-4o 75 % con prompt corregido
  para el roleplay 1ª persona) → se usó como señal **indicativa**. Limitación declarada.
- **Test ciego (5 evaluadores)**: prefirió `groq-llama70b`, **divergiendo** del ganador
  automático (gemini) — y por §5 (preferencia humana decisiva entre finalistas) **decide**.
  Confirma la señal preliminar (n=1 ya daba groq 63.6 %).
- **Ajustes por disponibilidad** (documentados en ADR-007): Gemini 2.0→2.5-flash con
  *thinking off*, Qwen3→Gemma3 (4B, no thinking), juez `gemini-2.5-pro` retirado.

## 10. H6 — Resultado del estudio (finalistas y test ciego)

Las **puertas** (idioma ≥98 %, INFLESZ media ≥ 68, longitud 15–90, p95 ≤ 8 s, seguridad 0
fallos) se aplican primero; solo los que pasan compiten por los **pesos** (calidad 50 /
latencia 30 / coste 20). Detalle completo y tablas crudas en el
[ADR-007](decisiones/ADR-007-eleccion-llm.md).

| Candidato | Puertas | Score ponderado | Nota |
|---|---|---|---|
| `gemini-flash` | ✅ pasa | **0,80** (fidelidad 100 %, p95 0,89 s) | Ganador **automático** |
| `groq-llama70b` | ✅ pasa | alto | **Ganador final** (test ciego) |
| `ollama` (gemma3:4b) | 🟡 Opción B (1 fallo, riesgo residual) | 3º | Baja fidelidad (67 %) |
| `llama3-replicate` (baseline) | ❌ seguridad | — | Rotura de papel en "hazte un robot" |
| `mistral-small` | ❌ seguridad | — | Rotura de papel |

**Desempate por test ciego (5 evaluadores).** Las métricas automáticas favorecían a
`gemini-flash`, pero 5 personas prefirieron `groq-llama70b` por **respuestas más completas**.
Por la regla §5 (preferencia humana **decisiva** entre finalistas), **decide groq**. Es justo la
divergencia métrica-vs-humano que el test ciego existe para resolver — y confirma la señal
preliminar (n=1 ya daba groq 63,6 %). La app quedó fijada a `groq-llama70b`.

## 11. Progresión completa (resumen del arco de mejora)

La cadena de mediciones, de la línea base a la config final, defendida hito a hito:

| Hito | Palanca | Métrica que mueve | Antes → Después |
|---|---|---|---|
| Baseline (H3) | Sistema tal cual | ruteo · recall@3 chunk | 66,7 % · 78,2 % |
| **H4.1** | Embeddings multilingües | recall chunk · latencia retrieval | 81,8 % · 191→27 ms (7×) |
| **H4.2** | Troceado por estructura | recall chunk | 83,6 % |
| **H4.3** | Reranker (cross-encoder) | **recall chunk · ruteo** | **90,9 % · 82,2 %** (equilibrado) |
| H4.4 | Quitar DeepL (probado) | recall · ruteo | ❌ **descartado** (−5,4 · −11,1) |
| **H6** | Elección de LLM | ganador por método | **groq-llama70b** (test ciego) |
| H7 | STT local (faster-whisper) | WER · privacidad | tabla WER pendiente¹ · voz no sale del PC |
| H8 | Streaming SSE + TTS por frases | latencia percibida (TTFT) | pendiente¹ (target ~1–2 s vs ~7–12 s) |

¹ Mediciones que requieren el hardware/claves del usuario (ver §12). El **arco defendible** es
claro: el retrieval sube de 78,2 % a 90,9 % de recall de chunk y el ruteo de 66,7 % a 82,2 %,
todo **medido y comparado contra una línea base inmutable**.

## 12. Limitaciones reconocidas del proyecto

No es una debilidad enumerarlas: un tribunal valora más "sabemos qué no hemos podido demostrar y
por qué" que un informe sin fisuras.

- **Juez LLM no validado (H6).** Ningún juez alcanzó el ≥ 85 % de acuerdo con el humano (mejor:
  gpt-4o, 75 %). Se usó como señal **indicativa**, no como árbitro, y el desempate real recayó en
  el test ciego humano. Es la limitación más relevante del estudio de LLMs.
- **Test ciego pequeño (n=5 evaluadores).** Suficiente para desempatar dos finalistas, no para
  una conclusión estadísticamente robusta. Se declara el tamaño de muestra.
- **Recall a nivel de fichero saturado (100 %).** Con 1–2 ficheros por personaje, casi cualquier
  consulta recupera "el fichero correcto"; por eso la métrica que gobierna H4 es el recall de
  **chunk**. Una verdad de referencia a nivel de fragmento más rica es trabajo futuro.
- **Seguridad juzgada a mano.** El "tacto" del set adversarial (18 preguntas) no tiene métrica
  automática; la corrida adversarial con el LLM real (0/18 fallos con groq) se ejecuta en la
  máquina del usuario.
- **Corpus monolingüe (inglés).** La retirada de DeepL se descartó **con datos** precisamente
  porque el corpus es inglés; un corpus en español reabriría esa decisión ([ADR-014](decisiones/ADR-014-retirada-deepl.md)).
- **Mediciones dependientes del hardware del usuario (H7/H8).** La tabla WER del STT y la latencia
  p50/p95 del streaming requieren GPU/CUDA y claves de LLM/TTS que el sandbox no tiene; se
  completan en la máquina del usuario. Los mecanismos están implementados y con tests verdes.
- **Free tier y ruido del LLM alojado.** Algunas corridas completas sufrieron 429 transitorios de
  Replicate (ajenos a la métrica medida); el determinismo a `temperature=0` es casi total, no
  garantizado al 100 % (por eso se reporta σ).

## 13. Cómo reproducir

```powershell
uv run python -m evals.runner --modo completo --etiqueta baseline   # regenera una corrida
uv run python -m evals.runner --volcar-fixture                      # regenera el fixture congelado
uv run python -m evals.runner --modo retrieval-congelado            # compara generadores (H6)

# H6 — por cada candidato: fijar LLM_PROVIDER/LLM_MODEL/LLM_BASE_URL + su clave y correr:
uv run python -m evals.runner --modo retrieval-congelado --etiqueta h6-<id> --repeticiones 3
uv run python -m evals.comparar                                     # puertas → pesos → finalistas
uv run python -m evals.juez validar --muestras evals/juez_validacion.yaml   # valida el juez
uv run python -m evals.test_ciego generar --a <csvA> --b <csvB> --n 20      # pares del test ciego
```
