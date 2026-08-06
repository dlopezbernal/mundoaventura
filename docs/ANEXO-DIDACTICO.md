# Anexo didáctico — cómo funciona por dentro

Este anexo reúne el material **explicativo** del proyecto: qué es un RAG, por qué se
trocea el texto con solape, por qué el prompt de imagen va ordenado, y cómo leer las
trazas del chat. No son decisiones (esas están en [`DECISIONES.md`](DECISIONES.md) y sus
ADRs) ni mediciones (esas están en [`EVALUACION.md`](EVALUACION.md)): es la teoría de
fondo, pensada para defender el proyecto y para que un tercero entienda el pipeline.

El **README** cuenta cómo instalar y usar; la **[arquitectura](ARQUITECTURA.md)** cuenta
cómo está montado; este anexo cuenta **por qué las piezas de IA funcionan así**.

---

## 1. Qué es el RAG y cómo conversa el personaje

**RAG** (*Retrieval-Augmented Generation*) = "generación aumentada por recuperación". En
vez de que el modelo responda solo con lo que "recuerda" de su entrenamiento (que puede
inventar), primero **recuperamos** fragmentos de documentos reales sobre el personaje y se
los damos al modelo para que **genere** la respuesta fundamentada en ellos. Así el T-Rex
contesta con datos de una enciclopedia, no con lo que se imagine.

El recorrido de una pregunta:

1. Escribes una pregunta → el frontend la manda a `POST /api/ask` (o `/api/ask/stream`
   para la respuesta en directo) con el `personaje_id`.
2. **Traducción (DeepL, obligatoria):** los documentos están en **inglés** (los embeddings
   rinden mucho mejor en inglés), así que la pregunta del niño se traduce **ES→EN** antes de
   buscar. Esa versión en inglés se usa en **todas** las peticiones al modelo (retrieval,
   Evaluator y generación), porque el LLM obedece mejor en inglés. Solo se traduce la
   pregunta; la **respuesta la genera directamente en español**. Sin DeepL la recuperación
   falla, así que el chat devuelve un error claro en su lugar.
3. **Retrieval:** **ChromaDB** busca, entre los fragmentos (*chunks*) de **ese** personaje,
   los más parecidos a la pregunta (ya en inglés), y devuelve su **distancia coseno**
   (0 = idéntico, 2 = opuesto). Los fragmentos se crearon al indexar los documentos.
4. **(Opcional) Reranker:** si está activo, un *cross-encoder* reordena los candidatos
   leyendo pregunta y ficha **juntas** (más fino que el coseno) y se queda con los mejores.
   Ver el [ADR-006](decisiones/ADR-006-reranker.md).
5. **Evaluator + Router:** se decide si esos fragmentos son relevantes (¿respondemos con el
   RAG o con conocimiento general?). Ver §3.
6. **Generación:** el LLM redacta la respuesta en primera persona y en español, a partir de
   las fichas (vía RAG) o de su conocimiento propio (vía GENERAL).

> **"Entra en inglés, sale en español".** La base de conocimiento, las consultas de
> recuperación y todos los prompts al modelo van en inglés; la única cosa en español es la
> respuesta final, porque es lo que lee el niño. Es un **invariante del sistema**, no una
> decisión con ADR propio: está declarado en `CLAUDE.md` §Invariantes críticos, y lo que sí
> se midió —si se podía quitar DeepL y consultar en español— está en el
> [ADR-014](decisiones/ADR-014-retirada-deepl.md), que salió **negativo**.

---

## 2. El chunking con solape, explicado

Los documentos no se meten enteros en el índice: se **trocean** en fragmentos. Y los
fragmentos **se solapan** entre sí.

- **`CHUNK_SIZE`** (por defecto 800 caracteres): tamaño de cada fragmento. Trozos pequeños
  = vectores más "enfocados" y mejor recuperación.
- **`CHUNK_OVERLAP`** (por defecto 120): caracteres que se **repiten** entre un chunk y el
  siguiente, para que una idea partida justo en la frontera no se pierda.

Ejemplo de por qué hace falta el solape: si un dato ("el Triceratops medía **9 metros** de
largo") cae justo en el corte entre dos chunks, sin solape ninguno de los dos lo contiene
completo. Con solape, el final de un chunk y el principio del siguiente **comparten** esa
frase, así que la idea sobrevive al troceo.

Se usa `RecursiveCharacterTextSplitter` de LangChain, que intenta cortar por límites
naturales (párrafos, frases) antes que por mitad de palabra. Existe también un modo de
troceado **por estructura** (encabezados de Markdown); el porqué de tener las dos opciones
está en el [ADR-005](decisiones/ADR-005-troceado-estructural.md).

---

## 3. El Evaluator: `origen` vs `método` (cómo leer las decisiones del chat)

Cada respuesta del chat lleva dos etiquetas que **son cosas distintas** y conviene no
confundir:

- **`origen`** = de DÓNDE sale el contenido de la respuesta.
- **`método`** = CÓMO se tomó la decisión de ruteo.

### Eje 1 — `origen`: de dónde sale el contenido

| `origen` | Icono | Qué significa |
|----------|-------|---------------|
| **RAG** | 🟢 | La respuesta está **fundamentada en las fichas** recuperadas de los documentos del personaje. El LLM responde usando **solo** esa información → fiable y verificable. |
| **GENERAL** | 🟡 | Las fichas **no servían**, así que el personaje responde con el **conocimiento propio del modelo**. Útil para lo que está fuera de los documentos (p. ej. "¿cuánto es 2+2?"), pero **no respaldado por tus fuentes**. |
| **SIN_INFO** | 🔴 | Las fichas no servían y `PERMITIR_CONOCIMIENTO_GENERAL` está **desactivado**: se devuelve el mensaje fijo `MENSAJE_SIN_INFORMACION` **sin llamar a ningún LLM** (coste cero). No aparece con la configuración de fábrica (ese ajuste viene activado). |

Se decide en `_decidir_origen` (`backend/services/rag_service.py`): si las fichas son
relevantes → **RAG**; si no y `PERMITIR_CONOCIMIENTO_GENERAL` está activo → **GENERAL**;
si no → **SIN_INFO**.

### Eje 2 — `método`: cómo se decidió el ruteo

| `método` | Coste | Qué significa |
|----------|-------|---------------|
| **umbral** | **0** (sin LLM) | Se decidió **solo con la distancia coseno** de ChromaDB. Mejor ficha por debajo de `EVALUATOR_UMBRAL_BAJO` → RAG; por encima de `EVALUATOR_UMBRAL_ALTO` → GENERAL. |
| **llm** | 1 llamada extra | La distancia cayó en la **zona dudosa** (entre los dos umbrales), así que se llamó al **LLM-juez**, que responde `YES`/`NO` sobre si las fichas sirven. |
| **rerank** | 0 llamadas extra | Con el reranker activo, el ruteo lo decide la **puntuación del cross-encoder** (`rerank_score ≥ RERANK_UMBRAL ⇒ RAG`). Sustituye al LLM-juez. |

Qué `método` aparece depende de la config: `EVALUATOR_MODE` (`umbral`/`llm`/`hibrido`)
cuando **no** hay reranker; con reranker activo (`RERANKER != off`) el ruteo es siempre
`rerank` y el LLM-juez ya no se llama. El porqué de que el reranker jubile al juez está en el
[ADR-006](decisiones/ADR-006-reranker.md); la calibración de los umbrales coseno (y por qué
dependen del backend de embeddings) en el
[ADR-004](decisiones/ADR-004-embeddings-multilingues.md).

### Las combinaciones que puedes ver (sin reranker)

| Traza | Lectura |
|-------|---------|
| `RAG · umbral` | La pregunta se parecía mucho a una ficha (`d` baja). Decidido **gratis** y respondido con los documentos. **El caso ideal.** |
| `GENERAL · umbral` | Ninguna ficha se parecía (`d` alta). **Gratis**, y el personaje tiró de conocimiento propio. |
| `RAG · llm` | Caso **dudoso**; el LLM-juez dijo "sí, las fichas valen" → respuesta fundamentada. |
| `GENERAL · llm` | Caso **dudoso**; el LLM-juez dijo "no valen" → conocimiento propio. |

En modo `hibrido` ves las cuatro; en `umbral`, solo las dos `· umbral`; en `llm`, solo las
dos `· llm`. Con `PERMITIR_CONOCIMIENTO_GENERAL` desactivado, `GENERAL` se convierte en
`SIN_INFO` en esas mismas combinaciones.

**En una frase:** `origen` = **qué fuente respondió** (documentos, modelo, o ninguno);
`método` = **quién tomó la decisión** (un número gratis, una llamada al LLM-juez, o el
reranker).

> **Calibración:** los umbrales `EVALUATOR_UMBRAL_BAJO`/`ALTO` se afinan mirando las
> distancias `d=...` reales que imprime el backend con `DEBUG=true`. Se configuran como
> **distancia coseno directa (0–2)**, la misma métrica nativa del motor, nunca como "%".
> La calibración medida está en [`EVALUACION.md`](EVALUACION.md).

---

## 4. Dos flags que a veces se confunden: `DEBUG` y `MOSTRAR_FUENTES`

Son ajustes **independientes**:

- **`DEBUG`** — enciende las **trazas en la consola del backend** (prompts al LLM/DeepL,
  origen RAG/GENERAL, voz `[VOZ] 🎙️ STT` / `🔊 TTS`). No tiene ningún efecto visible para
  el niño. Es un ajuste editable en caliente.
- **`MOSTRAR_FUENTES`** — controla si el chat le muestra al niño el desplegable
  **"📚 ¿De dónde lo he sacado?"** con los fragmentos usados en cada respuesta RAG. Es
  **pedagogía**, no depuración, por eso es un flag aparte de `DEBUG`.

> Históricamente `DEBUG` controlaba ambas cosas; desde el Hito 4.2 mostrar las fuentes al
> niño se separó en `MOSTRAR_FUENTES`. Si lees un comentario o doc antiguo que diga que
> "`DEBUG` enseña las fuentes", está obsoleto.

---

## 5. La traza de prompts (con `DEBUG=true`)

Con `DEBUG=true` el backend imprime en **su** consola todos los prompts que envía a un
servicio externo, centralizados en `backend/debug_log.py` (`trazar_prompt`). Se trazan:

| Servicio | Qué se imprime |
|----------|----------------|
| **LLM — RAG** | `SYSTEM` + `USER` (respuesta fundamentada en fichas) |
| **LLM — GENERAL** | `SYSTEM` + `USER` (conocimiento propio) |
| **LLM — Evaluator (juez)** | `SYSTEM` + `USER` (la llamada `SI`/`NO`) |
| **Replicate — escena** | `PROMPT` (texto→imagen) |
| **Replicate — edición foto** | `PROMPT` (modo "usar mi foto") |
| **DeepL** | `PROMPT` (texto a traducir) |
| **ElevenLabs — STT** | `[VOZ] 🎙️ STT · <bytes> → "<texto>"` |
| **ElevenLabs — TTS** | `[VOZ] 🔊 TTS · voz=<voz_id> · <chars> · <personaje_id>` |

**Roles del LLM.** Las llamadas al LLM tienen dos partes: `SYSTEM` (el rol y las reglas,
**en inglés**, incluida la orden *"ALWAYS reply in Spanish"*) y `USER` (la pregunta ya
traducida + las fichas recuperadas). La generación de imagen y DeepL no usan roles: envían
un único texto etiquetado `PROMPT`.

Ejemplo al chatear:

```
┌─ PROMPT → Replicate · RAG (meta/meta-llama-3-8b-instruct) ───
│ [SYSTEM]
│   You are Sherlock Holmes, speaking in the first person to a child aged 8 to 12. ALWAYS reply in Spanish...
│ [USER]
│   Cards with data about me:
│   - ...
│   Child's question: Where do you live?
└──────────────
```

Con `DEBUG=false` no se imprime nada (coste cero en la versión final).

---

## 6. Por qué el prompt de imagen va ordenado (CLIP vs T5)

FLUX (el modelo de imagen) codifica el prompt con **dos** codificadores a la vez:

- **CLIP**, que **trunca a ~77 tokens** (`CLIP_TOKEN_LIMIT`).
- **T5**, que admite prompts largos.

Por eso el prompt se monta **de más a menos importante**: primero el **sujeto** (personaje +
ubicación), luego el **encuadre**, y al final el **estilo**. Así lo esencial **siempre entra
en CLIP**; lo que cae al final puede quedar fuera de CLIP, pero **T5 lo sigue leyendo**, así
que apenas afecta al resultado. Si el prompt supera el límite, el backend emite un **warning**
(prefijo `[GEN]`), no un error: **la imagen se genera igual**.

Además, FLUX schnell (el modelo por defecto) **no tiene *negative prompt***: la seguridad
infantil y el estilo "Pixar 3D amigable" se cuecen dentro del prompt **positivo** (vía
`STYLE_SUFFIX`/`FRAMING`).

---

## Nota histórica: la voz en el frontend

El frontend graba y reproduce voz con las **APIs nativas del navegador**, sin librerías:
`MediaRecorder` (`getUserMedia`) captura el micro (webm/opus en Chrome, ogg/opus en Firefox,
ambos aceptados por el STT) y el `Audio()` estándar reproduce el mp3. `getUserMedia` solo
funciona en contextos seguros (https o localhost); si no está disponible o se deniega el
permiso, el micro se deshabilita con un aviso y el chat de texto sigue funcionando.

> El primer frontend (de escritorio, en Flet) no podía usar `flet-audio` —un spike demostró
> que no graba micrófono y que arrastraba una actualización de Flet que rompía la interfaz—,
> así que grababa con `sounddevice` + `soundfile`. La migración a la SPA React eliminó esa
> fricción al usar las APIs del navegador.
