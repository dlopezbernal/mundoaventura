# 🕰️ Máquina del Tiempo en tu Habitación

Herramienta educativa (para niños de 8 a 12 años) que **genera escenas divertidas combinando
un lugar y un personaje histórico o prehistórico** (¡un T-Rex en un laboratorio!) y, más
adelante, te dejará **conversar con ellos por voz**. Combina varias tecnologías de
Inteligencia Artificial en un pipeline por fases.

> Este repositorio se construye **paso a paso**. Ahora mismo está implementada la
> **generación de la escena** (ubicación + personaje) usando **Replicate.com**.

---

## 🧩 El pipeline

| Paso | Qué hace | Tecnología | Estado |
|------|----------|------------|--------|
| **Elegir lugar y personaje** | Eliges una **ubicación** (laboratorio, bosque del jurásico, renacimiento, época victoriana...) y un **personaje** (T-Rex, Leonardo da Vinci, Sherlock Holmes...). Cualquier combinación vale. | **Flet** (interfaz, sin IA) | ✅ **Implementado** |
| **Generación de la escena** | Combina lugar + personaje + estilo en un prompt y pide la imagen a la nube. Devuelve una escena completa. | **Replicate.com** (FLUX schnell, txt2img) | ✅ **Implementado** |
| **Conversación por texto (RAG)** | Escribes una pregunta y el personaje responde **en primera persona**, fundamentado en documentos (enciclopedias) troceados. | **LangChain** (chunking) + **ChromaDB** + **DeepL** + **LLM** (Replicate) | ✅ **Implementado** |
| Entrada por voz | Graba la pregunta con el micro y la transcribe a texto. | Whisper (Replicate) | ⏳ Pendiente |

> **¿Por qué Replicate y no Stable Diffusion en local?** Generar con Stable Diffusion +
> IP-Adapter en una GPU modesta (p. ej. una GTX 1660 de 6 GB) es lento e inestable. Con
> **Replicate.com** la generación se hace en su GPU: el backend solo manda un prompt y recibe
> la imagen. Así el proyecto es ligero y corre en cualquier ordenador, sin necesidad de GPU.
> El modelo por defecto es **FLUX schnell** (rápido y barato). El estilo "Pixar 3D amigable" y
> la seguridad para niños se integran en el prompt (FLUX schnell no admite *negative prompt*).

---

## 🏗️ Arquitectura

Arquitectura **Cliente-Servidor desacoplada**:

```
┌─────────────────────────┐         HTTP / REST         ┌──────────────────────────────┐
│   FRONTEND (Flet)        │                             │   BACKEND (FastAPI)          │
│                          │   POST /api/generate        │                              │
│   - Elegir lugar         │   { personaje_id,           │   [Imagen]                   │
│   - Elegir personaje     │     ubicacion_id }          │   - Construye el prompt      │
│   - Ver la escena        │  ─────────────────────────► │   - Llama a Replicate (FLUX) │
│                          │  ◄───────────────────────── │   - Devuelve la imagen       │
│                          │     escena (PNG base64)     │                              │
│                          │                             │                              │
│   - Chatear con el       │   POST /api/ask             │   [Conversación / RAG]       │
│     personaje            │   { personaje_id,           │   - ChromaDB recupera fichas │
│                          │     pregunta }              │   - LLM (Replicate) responde │
│                          │  ─────────────────────────► │     en primera persona       │
│                          │  ◄───────────────────────── │   - Devuelve el texto        │
└─────────────────────────┘     respuesta (texto)       └──────────────────────────────┘
        tu PC (ligero)                                    tu PC (ligero)  →  Replicate (GPU)
```

El backend ya no necesita GPU: la generación de imagen y el LLM corren en Replicate
(la nube), y ChromaDB indexa los documentos en local sobre CPU.

---

## 📁 Estructura del proyecto

```
capston/
├── backend/                  # Servidor de IA (FastAPI)
│   ├── main.py               # Arranque de la app y rutas globales
│   ├── config.py             # Configuración (Replicate, LLM, ChromaDB) desde .env
│   ├── debug_log.py          # Traza en consola de los prompts enviados (solo con DEBUG)
│   ├── personajes.py         # Prompts + NOMBRES de cada personaje + estilo común
│   ├── ubicaciones.py        # Prompts de cada ubicación
│   ├── ingest.py             # Ingesta: trocea (chunking) e indexa los documentos
│   ├── fetch_wikipedia.py    # Descarga un artículo de Wikipedia limpio a documentos/
│   ├── documentos/           # 📚 Base de conocimiento: una carpeta por personaje
│   │   ├── triceratops/      #   · documentos (.pdf/.txt/.md, en inglés) del personaje
│   │   ├── t-rex/
│   │   └── ...
│   ├── schemas/              # Forma de los datos de entrada/salida
│   │   ├── generation.py     #   · datos de /api/generate
│   │   └── conversacion.py   #   · datos de /api/ask
│   ├── services/             # Lógica de IA
│   │   ├── generation_service.py   #   · generación de imagen → Replicate
│   │   ├── rag_service.py          #   · conversación → ChromaDB + Evaluator + LLM
│   │   └── translation_service.py  #   · traducción ES→EN de la pregunta (DeepL)
│   ├── routers/              # Endpoints HTTP
│   │   ├── generation.py     #   · POST /api/generate, /api/generate-on-photo
│   │   └── conversacion.py   #   · POST /api/ask
│   └── chroma_db/            # Índice vectorial de ChromaDB (lo crea ingest.py; no se versiona)
├── frontend/                 # Interfaz de usuario (Flet)
│   ├── main.py               # La ventana de la app (catálogos + resultado + chat)
│   ├── personajes.py         # Catálogo visual de personajes (label, emoji)
│   ├── ubicaciones.py        # Catálogo visual de ubicaciones (label, emoji)
│   └── api_client.py         # Llamadas HTTP al backend
├── requirements-backend.txt
├── requirements-frontend.txt
└── .env.example              # Plantilla de configuración
```

---

## 🚀 Puesta en marcha

### 1. Crear y activar un entorno virtual

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Instalar las dependencias

```powershell
pip install -r requirements-backend.txt
pip install -r requirements-frontend.txt
```

> El backend es ligero: no instala torch ni diffusers.

### 3. Configurar el .env (con tu token de Replicate)

```powershell
Copy-Item .env.example .env
```

Edita `.env` y pega tu token de Replicate en `REPLICATE_API_TOKEN`. Lo creas en
[replicate.com/account/api-tokens](https://replicate.com/account/api-tokens).

**Obligatorio para el chat:** pega también una clave de **DeepL** en `DEEPL_API_KEY`. Se usa
para traducir la pregunta ES→EN antes de buscar; **sin ella la recuperación falla** (recupera
fichas equivocadas) y el chat responde con un error claro. Clave gratis (500.000 chars/mes) en
[deepl.com/pro-api](https://www.deepl.com/pro-api).

### 4. Arrancar el backend (una terminal)

```powershell
uvicorn backend.main:app --reload
```

Comprueba que abre en http://127.0.0.1:8000/docs. En `GET /health` debe aparecer
`"token_configurado": true` y el modelo de Replicate.

### 5. Arrancar el frontend (otra terminal, con el venv activado)

```powershell
flet run frontend/main.py
```

La interfaz es un **asistente por pasos**: **1)** elige un personaje, **2)** elige un lugar (o sube
tu foto) y pulsa «Siguiente». Al llegar al **paso 3 («¡Listo!») la escena se genera sola** (sin
botón intermedio), mostrando mientras tanto una **animación «Creando…»** para amenizar la espera;
al terminar aparece la escena y, debajo, un **chat**: escríbele una pregunta al personaje (ej. "¿Qué
comes?") y te responderá en primera persona. Si vuelves atrás y cambias la elección, al volver al
paso 3 se regenera; si no cambias nada, se conserva la escena y el chat.

> Antes de usar el chat hay que **indexar los documentos una vez** (ver
> [§ Preparar la base de conocimiento](#-preparar-la-base-de-conocimiento-documentos--chunking)).
> La **primera** pregunta tarda un poco más (ChromaDB descarga su modelo de embeddings, en CPU).

> **Modo desarrollo (`DEBUG=true`):** activa herramientas de diagnóstico que **no** ve el niño:
> el botón **🔌 Probar conexión** en la cabecera del frontend (consulta `/health`), la traza del
> **origen de cada respuesta** del chat (ver *«Origen de la respuesta»*) y la **traza de todos los
> prompts** que el backend envía al LLM, a la generación de imagen y a DeepL (ver *«Traza de
> prompts»*), todo en la **consola del backend**. Con `DEBUG=false` no se imprime nada y la
> interfaz queda limpia.

---

## 📚 Preparar la base de conocimiento (documentos + chunking)

El conocimiento del chat **ya no está en el código**: viene de documentos que tú aportas. La
fase de preparación (cargar → trocear → indexar) la hace `backend/ingest.py` con **LangChain**.

### Paso 0 (opcional) — Descarga contenido de Wikipedia

El script `backend/fetch_wikipedia.py` descarga un artículo de Wikipedia como
texto limpio y lo deja en `backend/documentos/<personaje_id>/` listo para indexar.
Filtra las secciones irrelevantes para el RAG (References, External links, Bibliography…).

```powershell
# Inglés estándar
python -m backend.fetch_wikipedia t-rex https://en.wikipedia.org/wiki/Tyrannosaurus

# Simple English Wikipedia (vocabulario de niños — recomendado si el artículo existe)
python -m backend.fetch_wikipedia t-rex https://simple.wikipedia.org/wiki/Tyrannosaurus_rex
```

El idioma y el título se extraen automáticamente de la URL: pega la URL que quieras
y el script la descarga en el idioma correcto.

> Tras descargar, ejecuta `python -m backend.ingest` para reconstruir el índice.

### Paso 1 — Deja los documentos en su carpeta

Una **carpeta por personaje** dentro de `backend/documentos/`, con el nombre = `personaje_id`:

```
backend/documentos/
├── triceratops/        ←  PDFs/txt/md (en INGLÉS) sobre el triceratops
├── t-rex/
├── leonardo_da_vinci/
└── sherlock_holmes/
```

- **Formatos:** `.pdf`, `.txt`, `.md`.
- **Idioma: inglés** (los embeddings rinden mucho mejor; la pregunta se traduce sola ES→EN).
- Un documento que sirva a dos personajes (p. ej. una enciclopedia de dinosaurios) se **copia**
  en las dos carpetas.
- Vienen unos `*_ejemplo.md` de muestra para que pruebes ya; bórralos y pon los tuyos.

### Paso 2 — Indexa (la primera vez y cada vez que cambies documentos)

Desde la raíz del proyecto, con el venv activado:

```powershell
python -m backend.ingest
```

Esto **trocea** cada documento en fragmentos (*chunks*) con **solape** y los **indexa** en
ChromaDB, etiquetando cada fragmento con su personaje. Verás un resumen por archivo:

```
[triceratops]
   · triceratops_ejemplo.md: 1 chunks
...
✅ Indexado completo: 4 archivos → 4 chunks en la colección 'documentos_en'.
```

### El chunking con solape, explicado

- **`CHUNK_SIZE`** (por defecto 800 caracteres): tamaño de cada fragmento. Trozos pequeños =
  vectores más “enfocados” y mejor recuperación.
- **`CHUNK_OVERLAP`** (por defecto 120): caracteres que se **repiten** entre un chunk y el
  siguiente, para que una idea partida en la frontera no se pierda.
- Se ajustan en el `.env`. Usamos `RecursiveCharacterTextSplitter` de LangChain, que intenta
  cortar por límites naturales (párrafos, frases) antes que por mitad de palabra.

> Reindexado: `ingest.py` **reconstruye** la colección desde cero cada vez (borra y vuelve a
> indexar), así que basta con re-ejecutarlo tras añadir o cambiar documentos.

---

## 💬 Cómo funciona la conversación (RAG con Evaluator)

1. Escribes una pregunta → el frontend la manda a `POST /api/ask` con el `personaje_id`.
2. **Traducción (DeepL, obligatoria):** los documentos están en **inglés** (los embeddings rinden
   mucho mejor en inglés), así que la pregunta del niño se traduce **ES→EN** antes de buscar. Esa
   versión en inglés se usa en **todas las peticiones al modelo** (retrieval, Evaluator y generación),
   porque Llama 3 obedece mejor en inglés. Solo se traduce la pregunta; la **respuesta el LLM la
   genera directamente en español** (no se traduce de vuelta). Sin DeepL la recuperación falla, así
   que el chat devuelve un error claro en su lugar.
3. **Retrieval:** **ChromaDB** busca, entre los fragmentos (chunks) de **ese** personaje, los más
   parecidos a la pregunta (ya en inglés), y devuelve su **distancia coseno** (0 = idéntico,
   2 = opuesto). Los fragmentos los generó `backend/ingest.py` a partir de los documentos.
4. **Evaluator + Router:** se decide si esos fragmentos son relevantes (¿respondemos con el RAG?).
   Hay **tres modos**, configurables con `EVALUATOR_MODE` en el `.env`:
   - `umbral` → decide **solo la distancia** (gratis, sin LLM). RAG si el mejor fragmento está por
     debajo de `EVALUATOR_UMBRAL_BAJO`.
   - `llm` → decide **solo el LLM-juez**: una llamada extra que responde `SI`/`NO`. Más listo,
     pero cuesta.
   - `hibrido` *(recomendado)* → el **umbral** cierra gratis los casos claros (muy cerca = RAG,
     muy lejos = GENERAL) y el **LLM** solo entra a **desempatar la zona dudosa**. Mejor relación
     calidad/coste.
5. **Bifurcación según la decisión:**
   - **RAG** → el LLM responde fundamentándose en los fragmentos (`origen: RAG`).
   - **GENERAL** → el personaje responde con su conocimiento propio (`origen: GENERAL`).
     *(Aquí, más adelante, se podría enrutar a una búsqueda web.)*

### ⚖️ Comparativa de los tres modos

| Modo | Coste por pregunta | Inteligencia | Cuándo usarlo |
|------|--------------------|--------------|---------------|
| `umbral` | **0** (solo números) | Baja (solo similitud) | Maximizar ahorro; baseline para comparar |
| `llm` | 1 llamada extra siempre | Alta (entiende matices) | Mostrar el patrón Evaluator puro |
| `hibrido` | Llamada extra **solo en dudas** | Alta donde importa | **Producción / capstone** |

> Los umbrales `EVALUATOR_UMBRAL_BAJO` / `EVALUATOR_UMBRAL_ALTO` son orientativos. Actívate
> `DEBUG=true` para ver por consola la distancia real (`d=...`) de tus preguntas y ajustarlos.

### 🏷️ Origen de la respuesta (modo desarrollo, consola del backend)

Para saber si una respuesta vino del **RAG** o del conocimiento **GENERAL** del modelo, con
`DEBUG=true` en el `.env` el **backend lo imprime en SU consola** (la del `uvicorn`), no en el
chat ni en el frontend. Se hace en el backend porque ahí ya se calcula todo: así el frontend **no
recibe ni procesa** datos de depuración (más ligero) y la interfaz que ve el niño queda **siempre
limpia**. En la consola del backend verás líneas como:

```
[CHAT] 🟢 [RAG · umbral · d=0.42 · "what do you eat"]
[CHAT] 🟡 [GENERAL · llm · "how much is 2+2"]
```

El formato es `[CHAT] <icono> [<origen> · <metodo> · d=<distancia> · "<pregunta_en>"]`. **Lo más
importante es entender que `origen` y `metodo` son DOS cosas distintas**, por eso aparecen juntas:

#### Eje 1 — `origen`: de DÓNDE sale el contenido de la respuesta

| `origen` | Icono | Qué significa |
|----------|-------|---------------|
| **RAG** | 🟢 | La respuesta está **fundamentada en las fichas** recuperadas de los documentos del personaje (ChromaDB). El LLM responde usando **solo** esa información → fiable y verificable. |
| **GENERAL** | 🟡 | Las fichas **no servían**, así que el personaje responde con el **conocimiento propio del modelo** (lo que Llama 3 ya sabe). Útil para lo que está fuera de los documentos (p. ej. "¿cuánto es 2+2?"), pero **no respaldado por tus fuentes**. |

Se decide en `_decidir_origen` ([backend/services/rag_service.py](backend/services/rag_service.py)):
si las fichas recuperadas se consideran relevantes → **RAG**; si no → **GENERAL**. Internamente, cada
camino usa un prompt distinto (`_construir_prompt` para RAG, `_construir_prompt_general` para GENERAL).

#### Eje 2 — `metodo`: CÓMO se tomó esa decisión

| `metodo` | Coste | Qué significa |
|----------|-------|---------------|
| **umbral** | **0** (sin LLM) | Se decidió **solo con la distancia coseno** de ChromaDB (`d=...`). Si la mejor ficha está por debajo de `EVALUATOR_UMBRAL_BAJO` → RAG; por encima de `EVALUATOR_UMBRAL_ALTO` → GENERAL. |
| **llm** | 1 llamada extra | La distancia cayó en la **zona dudosa** (entre los dos umbrales), así que se llamó al **LLM-juez** (Evaluator), que responde `YES`/`NO` sobre si las fichas sirven. Más listo, pero cuesta una llamada. |

Qué `metodo` aparece depende de `EVALUATOR_MODE` en el `.env` (ver la comparativa de arriba):
`umbral` → siempre `· umbral`; `llm` → siempre `· llm`; `hibrido` → mezcla (umbral para los casos
claros, llm solo para desempatar los dudosos).

#### Las 4 combinaciones que puedes ver

| Traza | Lectura |
|-------|---------|
| `RAG · umbral` | La pregunta se parecía mucho a una ficha (`d` baja). Decidido **gratis** y respondido con los documentos. **El caso ideal.** |
| `GENERAL · umbral` | Ninguna ficha se parecía (`d` alta). **Gratis**, y el personaje tiró de conocimiento propio. |
| `RAG · llm` | Caso **dudoso**; el LLM-juez dijo "sí, las fichas valen" → respuesta fundamentada. |
| `GENERAL · llm` | Caso **dudoso**; el LLM-juez dijo "no valen" → conocimiento propio. |

> En modo `hibrido` verás las **4**; en modo `umbral` solo las dos `· umbral`; en modo `llm` solo
> las dos `· llm`. La distancia `d=...` aparece siempre que haya fichas candidatas (sirve para
> calibrar los umbrales).

**En una frase:** `origen` = **qué fuente respondió** (documentos vs. modelo) · `metodo` = **quién
tomó la decisión** (un número gratis vs. una llamada al LLM-juez).

Con `DEBUG=false` (versión final para el usuario) no se imprime nada. El JSON de `/api/ask` sigue
incluyendo `origen`/`metodo`/`distancia` (por si los necesitas), pero el frontend ya no los usa.

### 🔎 Traza de prompts (modo desarrollo, consola del backend)

Con `DEBUG=true` el backend imprime en **su** consola **todos los prompts que envía a un servicio
externo**, para tenerlos a la vista de un vistazo y poder depurarlos/ajustarlos. La traza la
centraliza `backend/debug_log.py` (`trazar_prompt`), que se llama en cada punto de envío. Se
trazan:

| Servicio | De dónde sale | Qué se imprime |
|----------|---------------|----------------|
| **LLM — RAG** | respuesta fundamentada en las fichas | `SYSTEM` + `USER` |
| **LLM — GENERAL** | respuesta con el conocimiento propio del personaje | `SYSTEM` + `USER` |
| **LLM — Evaluator (juez)** | la llamada `SI`/`NO` que decide si es RAG | `SYSTEM` + `USER` |
| **Replicate — escena** | generación texto→imagen (`/api/generate`) | `PROMPT` |
| **Replicate — edición foto** | modo «usar mi foto» (`/api/generate-on-photo`) | `PROMPT` |
| **DeepL** | traducción ES→EN de la pregunta antes del retrieval | `PROMPT` (texto a traducir) |

**Tipos de prompt (roles).** En las llamadas al **LLM** hay dos partes, y la traza las separa:

- **`SYSTEM`** → el **rol y las reglas**. Va **en inglés** en los tres usos (personaje RAG, personaje
  GENERAL y Evaluator), porque Llama 3 obedece mejor las instrucciones en inglés. En los del
  personaje se incluye la orden explícita *«ALWAYS reply in Spanish»* para que la respuesta al niño
  salga en español (ej.: *«You are Leonardo da Vinci, speaking to a child aged 8 to 12, ALWAYS reply
  in Spanish…»*, en `backend/services/rag_service.py`).
- **`USER`** → la **pregunta del niño** (ya traducida ES→EN) + las **fichas** recuperadas (también en
  inglés). Solo la pregunta pasa por DeepL; los `system` son texto **fijo en inglés en el código** y
  NO se traducen en runtime. Ver la decisión de diseño *«Todo lo que recibe el modelo va en inglés»*.

La generación de imagen y DeepL no usan roles: envían un **único texto**, etiquetado `PROMPT`.

Ejemplo de salida en la consola del backend al chatear:

```
┌─ PROMPT → Replicate · Evaluator (juez) (meta/meta-llama-3-8b-instruct) ───
│ [SYSTEM]
│   You are a strict evaluator for a RAG system. Your only task is to decide...
│ [USER]
│   Context cards:
│   - ...
│   Question: Where do you live?
└──────────────

┌─ PROMPT → Replicate · RAG (meta/meta-llama-3-8b-instruct) ───
│ [SYSTEM]
│   You are Sherlock Holmes, speaking in the first person to a child aged 8 to 12. ALWAYS reply in Spanish...
│ [USER]
│   Cards with data about me:
│   - ...
│   Child's question: Where do you live?
└──────────────
```

Con `DEBUG=false` no se imprime ningún prompt (coste cero en la versión final).

---

## 🧭 Decisiones de diseño

Registro de las decisiones técnicas relevantes y su justificación (material para la
memoria final del proyecto).

### 1. Embeddings sin PyTorch (onnx de ChromaDB, no sentence-transformers)

**Decisión:** generar los embeddings del RAG con el modelo por defecto de ChromaDB
(`all-MiniLM-L6-v2` sobre **onnxruntime**), en lugar del típico `HuggingFaceEmbeddings` /
`sentence-transformers` de LangChain, que depende de **PyTorch (torch)**.

**Por qué:**
- **Coherencia con el proyecto.** Toda la IA pesada se movió a la nube (Stable Diffusion y el
  LLM → Replicate) precisamente para evitar la complejidad de GPU local en una GTX 1660 (6 GB).
  Meter torch solo para los embeddings reintroduciría esa pesadez que se eliminó.
- **Peso e instalación.** PyTorch ocupa de cientos de MB a varios GB (con CUDA) y su instalación
  es delicada (wheels CPU/CUDA, `--index-url`). El modelo onnx pesa ~80 MB y `pip install`
  funciona sin fricción en cualquier máquina (local, Colab, evaluador).
- **No aporta rendimiento aquí.** El modelo de embeddings es diminuto y corre en milisegundos
  sobre CPU; la GPU no daría una mejora que justifique arrastrar 1-2 GB de dependencia.
- **Despliegue ligero.** Menor huella → contenedores y arranques en frío más rápidos.

**Alternativa descartada:** `sentence-transformers` (mejor catálogo de modelos), porque arrastra
torch obligatoriamente.

**Cuándo reconsiderarlo:** si se necesitara un modelo de embeddings claramente superior (p. ej.
multilingüe de alta calidad). Aun así, primero se valoraría **`fastembed`** (también onnx, sin
torch) antes que volver a PyTorch.

### 2. Generación de imagen y LLM en la nube (Replicate)

**Decisión:** no ejecutar Stable Diffusion ni el LLM en local; delegarlos a **Replicate**.
**Por qué:** una GPU modesta (GTX 1660, 6 GB) hace la inferencia local lenta e inestable; en la
nube el backend solo manda un prompt y recibe el resultado, y el proyecto corre en cualquier PC.

### 3. Todo lo que recibe el modelo va en inglés; la respuesta, en español

**Decisión:** mantener la base de conocimiento en **inglés**, traducir la **pregunta** del niño
ES→EN en runtime (DeepL) y escribir **todos los prompts que enviamos al LLM** —el `system`/`user`
del personaje (RAG y GENERAL) y el del Evaluator, las fichas y la pregunta— **en inglés**. La única
excepción es la **respuesta**, que el prompt pide explícitamente **en español** (es lo que lee el niño).

**Por qué:**
- **Embeddings:** rinden mucho mejor en inglés (medido: sin traducir, la recuperación elegía fichas
  equivocadas). Traducir solo la pregunta es barato; traducir todo el corpus gastaría mucha cuota.
- **Seguimiento de instrucciones:** el LLM por defecto (**Llama 3 8B**) está entrenado sobre todo en
  inglés y **obedece mejor las instrucciones en inglés**; con la petición en castellano responde
  peor. Por eso los `system`/`user` del personaje y del Evaluator van en inglés y se les pasa la
  pregunta ya traducida (`pregunta_en`), no la original en español.
- **La salida en español no penaliza:** el modelo es multilingüe al *generar*, así que produce la
  respuesta en español sin pérdida de calidad aunque se le instruya en inglés.

Ver [§ traducción](#-cómo-funciona-la-conversación-rag-con-evaluator) y *«Traza de prompts»* (para
ver los prompts reales en consola con `DEBUG=true`).

### 4. Evaluator híbrido (umbral + LLM-juez)

**Decisión:** decidir si una pregunta se responde con el RAG mediante un **umbral de distancia**
(gratis) para los casos claros y un **LLM-juez** solo para los dudosos.
**Por qué:** combina el coste cero del umbral con la inteligencia del LLM donde de verdad hace
falta. Configurable con `EVALUATOR_MODE` para poder comparar los tres modos.

### 5. Orden del prompt de imagen (CLIP vs T5) + aviso de longitud

**Decisión:** montar el prompt de generación de **más a menos importante** —primero el **sujeto**
(personaje + ubicación), luego el **encuadre** y al final el **estilo**— y **avisar con un
warning** (no un error) cuando el prompt supera el límite de tokens de **CLIP**.

**Por qué:** FLUX codifica el prompt con **dos** codificadores a la vez: **CLIP**, que **trunca a
~77 tokens** (`CLIP_TOKEN_LIMIT` en el `.env`), y **T5**, que admite prompts largos. Si ponemos lo
esencial al principio, **entra siempre en CLIP**; lo que cae al final (encuadre/estilo) puede
quedar fuera de CLIP pero **T5 lo sigue leyendo**, así que apenas afecta al resultado. El warning
(en la consola del backend, prefijo `[GEN]`) solo informa de que CLIP recortará; **la imagen se
genera igual**. La longitud se estima al alza contando palabras y signos (no usamos el tokenizador
exacto de CLIP), suficiente para decidir cuándo avisar.

---

## 💡 Personalizar

- **Añadir personajes:** edita `backend/personajes.py` (el prompt) y `frontend/personajes.py`
  (la tarjeta), usando el **mismo `id`** en ambos.
- **Añadir ubicaciones:** igual, en `backend/ubicaciones.py` y `frontend/ubicaciones.py`.
- **Cambiar el modelo o el estilo:** `REPLICATE_MODEL` en el `.env` y el `STYLE_SUFFIX` en
  `backend/personajes.py`.
