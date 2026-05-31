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
│   ├── personajes.py         # Prompts + NOMBRES de cada personaje + estilo común
│   ├── ubicaciones.py        # Prompts de cada ubicación
│   ├── ingest.py             # Ingesta: trocea (chunking) e indexa los documentos
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
tu foto), **3)** pulsa «¡Generar!» y verás la escena. Después, en ese mismo paso, aparece un
**chat**: escríbele una pregunta al personaje (ej. "¿Qué comes?") y te responderá en primera persona.

> Antes de usar el chat hay que **indexar los documentos una vez** (ver
> [§ Preparar la base de conocimiento](#-preparar-la-base-de-conocimiento-documentos--chunking)).
> La **primera** pregunta tarda un poco más (ChromaDB descarga su modelo de embeddings, en CPU).

---

## 📚 Preparar la base de conocimiento (documentos + chunking)

El conocimiento del chat **ya no está en el código**: viene de documentos que tú aportas. La
fase de preparación (cargar → trocear → indexar) la hace `backend/ingest.py` con **LangChain**.

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
   mucho mejor en inglés), así que la pregunta del niño se traduce **ES→EN** antes de buscar. Solo
   se traduce la pregunta; la **respuesta el LLM la genera directamente en español** (no se traduce
   de vuelta). Sin DeepL la recuperación falla, así que el chat devuelve un error claro en su lugar.
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
> `DEBUG=true` para ver la distancia real (`d=...`) de tus preguntas y ajustarlos.

### 🏷️ Etiqueta de origen (modo desarrollo)

Con `DEBUG=true` en el `.env`, cada respuesta del chat muestra **origen · método · distancia**,
útil para depurar y para **comparar modos**:

- 🟢 **[RAG · umbral · d=0.42]** → fundamentada en la enciclopedia; lo decidió el umbral.
- 🟡 **[GENERAL · llm]** → conocimiento propio del modelo; lo decidió el LLM-juez (p. ej. "2+2 = 4").

Con `DEBUG=false` (versión final para el usuario) las respuestas salen limpias, sin etiqueta.

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

### 3. Documentos en inglés + traducción de la pregunta (DeepL)

**Decisión:** mantener la base de conocimiento en **inglés** y traducir solo la **pregunta**
ES→EN en runtime (DeepL), en vez de usar embeddings multilingües o traducir todo el corpus.
**Por qué:** los embeddings rinden mucho mejor en inglés (medido: sin traducir, la recuperación
elegía fichas equivocadas); traducir solo la pregunta es barato, y traducir documentos extensos
gastaría mucha cuota. Ver [§ traducción](#-cómo-funciona-la-conversación-rag-con-evaluator).

### 4. Evaluator híbrido (umbral + LLM-juez)

**Decisión:** decidir si una pregunta se responde con el RAG mediante un **umbral de distancia**
(gratis) para los casos claros y un **LLM-juez** solo para los dudosos.
**Por qué:** combina el coste cero del umbral con la inteligencia del LLM donde de verdad hace
falta. Configurable con `EVALUATOR_MODE` para poder comparar los tres modos.

---

## 💡 Personalizar

- **Añadir personajes:** edita `backend/personajes.py` (el prompt) y `frontend/personajes.py`
  (la tarjeta), usando el **mismo `id`** en ambos.
- **Añadir ubicaciones:** igual, en `backend/ubicaciones.py` y `frontend/ubicaciones.py`.
- **Cambiar el modelo o el estilo:** `REPLICATE_MODEL` en el `.env` y el `STYLE_SUFFIX` en
  `backend/personajes.py`.
