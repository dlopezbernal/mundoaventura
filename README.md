# 🕰️ Máquina del Tiempo en tu Habitación

[![CI](https://github.com/dlopezbernal/maquina-del-tiempo/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/dlopezbernal/maquina-del-tiempo/actions/workflows/ci.yml)

Herramienta educativa (para niños de 8 a 12 años) que **genera escenas divertidas combinando
un lugar y un personaje histórico o prehistórico** (¡un T-Rex en un laboratorio!) y te deja
**conversar con ellos por texto o por voz**. Combina varias tecnologías de
Inteligencia Artificial en un pipeline por fases.

> Este repositorio se construye **paso a paso**. Ahora mismo están implementadas la
> **generación de la escena** (ubicación + personaje) con **Replicate.com**, el **chat con RAG**
> y la **voz** (ElevenLabs).

---

## 🧩 El pipeline

| Paso | Qué hace | Tecnología | Estado |
|------|----------|------------|--------|
| **Elegir lugar y personaje** | Eliges una **ubicación** (laboratorio, bosque del jurásico, renacimiento, época victoriana...) y un **personaje** (T-Rex, Leonardo da Vinci, Sherlock Holmes...). Cualquier combinación vale. | **SPA React** (Vite + TypeScript; interfaz, sin IA) | ✅ **Implementado** |
| **Generación de la escena** | Combina lugar + personaje + estilo en un prompt y pide la imagen a la nube. Devuelve una escena completa. | **Replicate.com** (FLUX schnell, txt2img) | ✅ **Implementado** |
| **Conversación por texto (RAG)** | Escribes una pregunta y el personaje responde **en primera persona**, fundamentado en documentos (enciclopedias) troceados. | **LangChain** (chunking) + **ChromaDB** + **DeepL** + **LLM** (Replicate) | ✅ **Implementado** |
| **Entrada por voz** | Graba la pregunta con el micro (toca para empezar / toca para parar) y la transcribe a texto en español. | **ElevenLabs Scribe** (STT) | ✅ **Implementado** |
| **Respuesta por voz** | La respuesta del personaje se sintetiza con una voz expresiva propia y se reproduce sola. | **ElevenLabs Flash** (TTS) | ✅ **Implementado** |

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
│  FRONTEND (SPA React)    │                             │   BACKEND (FastAPI)          │
│                          │   POST /api/generate        │                              │
│   - Elegir lugar         │   { personaje_id,           │   [Imagen]                   │
│   - Elegir personaje     │     ubicacion_id }          │   - Construye el prompt      │
│   - Ver la escena        │  ─────────────────────────► │   - Llama a Replicate (FLUX) │
│                          │  ◄───────────────────────── │   - Devuelve la imagen       │
│                          │     escena (PNG base64)     │                              │
│                          │                             │                              │
│   - Chatear con el       │   POST /api/transcribe      │   [Voz → texto (STT)]        │
│     personaje (texto     │   (audio del micro)         │   - ElevenLabs Scribe        │
│     o voz)               │  ─────────────────────────► │   - Devuelve el texto        │
│                          │   POST /api/ask             │   [Conversación / RAG]       │
│                          │   { personaje_id,           │   - ChromaDB recupera fichas │
│                          │     pregunta }              │   - LLM (Replicate) responde │
│                          │  ─────────────────────────► │   - TTS (ElevenLabs Flash)   │
│                          │  ◄───────────────────────── │   - Devuelve texto + audio   │
└─────────────────────────┘  respuesta (texto + audio)  └──────────────────────────────┘
     navegador (ligero)                                   tu PC (ligero)  →  Replicate (GPU)
```

El backend ya no necesita GPU: la generación de imagen y el LLM corren en Replicate
(la nube), y ChromaDB indexa los documentos en local sobre CPU.

---

## 📁 Estructura del proyecto

```
capston/
├── backend/                  # Servidor de IA (FastAPI)
│   ├── main.py               # Arranque de la app, CORS y enchufado de routers
│   ├── config.py             # Configuración (Replicate, LLM, ChromaDB) desde .env
│   ├── db.py                 # Motor SQLite + migración idempotente de columnas nuevas
│   ├── models.py             # Tablas SQLModel: Setting, Personaje, Ubicacion, Documento
│   ├── seed.py                # Vuelca personajes.py/ubicaciones.py a la BBDD (idempotente)
│   ├── debug_log.py          # Traza en consola de los prompts enviados (solo con DEBUG)
│   ├── personajes.py         # Prompts + NOMBRES + VOCES: solo "seed" inicial (la BBDD manda)
│   ├── ubicaciones.py        # Prompts de cada ubicación: solo "seed" inicial (la BBDD manda)
│   ├── ingest.py             # CLI de reindexado global (delega en documentos_service)
│   ├── fetch_wikipedia.py    # Descarga un artículo de Wikipedia limpio a documentos/
│   ├── documentos/           # 📚 Base de conocimiento: una carpeta por personaje
│   │   ├── triceratops/      #   · documentos (.pdf/.txt/.md, en inglés) del personaje
│   │   ├── t-rex/
│   │   └── ...
│   ├── schemas/              # Forma de los datos de entrada/salida (uno por router)
│   ├── services/             # Lógica de negocio
│   │   ├── generation_service.py   #   · generación de imagen → Replicate
│   │   ├── rag_service.py          #   · conversación → ChromaDB + Evaluator + LLM
│   │   ├── translation_service.py  #   · traducción ES↔EN (DeepL)
│   │   ├── voice_service.py        #   · voz → texto (Scribe) y texto → voz (Flash): ElevenLabs
│   │   ├── documentos_service.py   #   · CRUD de documentos del RAG (visor: ver/editar/descargar/
│   │   │                          #     copiar, subida múltiple, detección automática de idioma)
│   │   ├── personajes_service.py   #   · catálogo de personajes (BBDD) + límite MAX_PERSONAJES
│   │   ├── ubicaciones_service.py  #   · catálogo de ubicaciones (BBDD)
│   │   ├── settings_service.py     #   · ajustes editables en caliente (BBDD, con fallback a config.py)
│   │   ├── secrets_service.py      #   · claves API: leer/escribir el .env de forma atómica
│   │   └── admin_service.py        #   · PIN de adulto (hash + sesión) y backup del SQLite
│   ├── routers/               # Endpoints HTTP (finos: validan, llaman al service, mapean errores)
│   │   ├── generation.py     #   · POST /api/generate, /api/generate-on-photo
│   │   ├── conversacion.py   #   · POST /api/ask
│   │   ├── transcription.py  #   · POST /api/transcribe (voz → texto, ElevenLabs Scribe)
│   │   ├── personajes.py     #   · CRUD de personajes + voces de ElevenLabs
│   │   ├── ubicaciones.py    #   · CRUD de ubicaciones
│   │   ├── documentos.py     #   · CRUD de documentos del RAG (visor + copiar) + reindexado
│   │   ├── config.py         #   · GET/PUT /api/config (ajustes en caliente)
│   │   ├── apis.py           #   · claves de los proveedores (pestaña "APIs")
│   │   └── admin.py          #   · login/PIN, import/export, backup
│   └── chroma_db/            # Índice vectorial de ChromaDB (se reconstruye; no se versiona)
├── frontend-react/           # Interfaz de usuario (SPA: Vite + React 18 + TypeScript)
│   ├── src/
│   │   ├── App.tsx           # Orquesta el asistente por pasos (monta fondo, HUD y pantallas)
│   │   ├── main.tsx          # Punto de entrada de React (monta App)
│   │   ├── state/useFlow.ts  # Máquina de estados del flujo (useReducer: personaje→mundo→escena)
│   │   ├── api/              # Contrato tipado (types.ts) + cliente fetch (client.ts)
│   │   ├── data/              # Solo presentación: agrupación por categorías (holo.ts, personajes.ts);
│   │   │                      #   los catálogos en sí ya no viven en el frontend, se leen por API
│   │   ├── screens/           # CharacterSelect, PlaceSelect, SceneChat, Settings
│   │   │   └── config/        #   · menú ⚙️: ApisTab, ConfigForm (IA/General), PersonajesTab,
│   │   │                      #     UbicacionesTab, SistemaTab, AdminGate, DocumentosPanel (visor RAG)
│   │   ├── components/        # Background, Hud, Steps, Coverflow, HoloCard, Roster, Modal,
│   │   │                      #   Console, SceneView, Chat, QuickChips (tema "Arcade Holo")
│   │   └── styles/            # tokens.css (tokens de diseño) + global.css
│   ├── vite.config.ts        # Proxy /api y /health → backend local (dev y preview)
│   └── .env.example          # VITE_BACKEND_URL (backend) y VITE_DEBUG (botón de diagnóstico)
├── docs/                     # Guías puntuales (p. ej. Playwright MCP) y planes históricos (feats/)
├── requirements-backend.txt
└── .env.example              # Plantilla de configuración (backend)
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
# Backend (Python)
pip install -r requirements-backend.txt

# Frontend (Node 20+; una sola vez)
cd frontend-react
npm install
cd ..
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

**Obligatorio para la voz:** pega también tu clave de **ElevenLabs** en `ELEVENLABS_API_KEY`
(modalidad pago por uso). Se usa para transcribir la pregunta hablada del niño (Scribe) y dar
voz a la respuesta del personaje (Flash). Sin ella, la voz queda desactivada pero el chat de
**texto sigue funcionando**. Consigue una clave en [elevenlabs.io](https://elevenlabs.io).

### 4. Arrancar el backend (una terminal)

```powershell
uvicorn backend.main:app --reload
```

Comprueba que abre en http://127.0.0.1:8000/docs. En `GET /health` debe aparecer
`"token_configurado": true`, el modelo de Replicate y `"elevenlabs_ok": true`.

### 5. Arrancar el frontend (otra terminal)

```powershell
cd frontend-react
npm run dev
```

Abre la URL que imprime Vite (por defecto http://localhost:5173). En desarrollo **no hace
falta configurar nada más**: el proxy de `vite.config.ts` reenvía `/api` y `/health` al
backend local (mismo origen, sin CORS). Si el backend está en otra máquina (p. ej. el túnel
https de Colab), copia `frontend-react/.env.example` a `frontend-react/.env` y pon su URL en
`VITE_BACKEND_URL`.

La interfaz es un **asistente por pasos**: **1)** elige un personaje (carrusel), **2)** elige un
lugar (o sube tu foto) y pulsa «Siguiente». Al llegar al **paso 3 la escena se genera sola** (sin
botón intermedio), mostrando mientras tanto una **animación «Creando…»** para amenizar la espera;
al terminar aparece la escena y, a su lado, un **chat**: escríbele una pregunta al personaje (ej.
"¿Qué comes?") — o díctala con el **botón del micrófono** — y te responderá en primera persona,
con su propia voz. Si vuelves atrás y cambias la elección, al volver al paso 3 se regenera; si no
cambias nada, se conserva la escena y el chat.

### 6. Build de producción (opcional)

```powershell
cd frontend-react
npm run build      # genera dist/ (estático)
npm run preview    # sirve dist/ en local para probarla (proxy al backend incluido)
```

`dist/` se puede servir desde cualquier hosting estático. Si el frontend y el backend quedan
en **orígenes distintos**, limita los orígenes permitidos con la variable `CORS_ORIGINS` del
`.env` del backend (lista separada por comas; sin definir se permite cualquier origen) y
compila la SPA con `VITE_BACKEND_URL` apuntando al backend.

> Antes de usar el chat hay que **indexar los documentos una vez** (ver
> [§ Preparar la base de conocimiento](#-preparar-la-base-de-conocimiento-documentos--chunking)).
> La **primera** pregunta tarda un poco más (ChromaDB descarga su modelo de embeddings, en CPU).

> **Modo desarrollo (`DEBUG=true` en el `.env` del backend):** activa la traza del **origen de
> cada respuesta** del chat (ver *«Origen de la respuesta»*) y la **traza de todos los prompts**
> que el backend envía al LLM, a la generación de imagen y a DeepL (ver *«Traza de prompts»*),
> todo en la **consola del backend**. En la SPA, el botón **🔌 Probar conexión** de la cabecera
> (consulta `/health`) se activa aparte con `VITE_DEBUG=true` en `frontend-react/.env`. Con
> todo en `false` no se imprime nada y la interfaz queda limpia.

---

## 📚 Preparar la base de conocimiento (documentos + chunking)

El conocimiento del chat **ya no está en el código**: viene de documentos que tú aportas. La
fase de preparación (cargar → trocear → indexar) la hace `backend/ingest.py` con **LangChain**.

> **Sin terminal:** desde el botón ⚙️ → pestaña **Personajes** → editar un personaje (se abre en
> un **modal** a pantalla completa) → sección **📄 Documentos**, un visor completo: **subir uno o
> varios** `.pdf/.txt/.md` a la vez, **ingerir un artículo de Wikipedia por URL**, **ver/editar el
> texto** de un documento ya subido (excepto PDF, que no se reescribe in-place), **descargarlo**
> tal cual, **copiarlo** de forma independiente a otro(s) personaje(s) (editar la copia nunca toca
> al original) y **borrarlo**. El idioma se **detecta automáticamente con DeepL** en cada subida,
> URL o edición — ya no hay que marcar "ya está en inglés": cualquier idioma se traduce solo si
> hace falta, y el nombre del fichero guardado indica el idioma detectado (`_en`, `_es`, `_fr`…).
> Si subes o copias un documento con un nombre que ya existe para ese personaje, la app avisa del
> conflicto y deja elegir sobrescribir en vez de pisarlo en silencio. Cada cambio **reindexa
> automáticamente solo a ese personaje** (reindexado incremental), y hay un botón **♻️ Reindexar
> todo** para reconstruir el índice completo, con una barra de progreso real mientras dura.
> Mientras se procesa algo (subida, traducción, reindexado) el modal se bloquea para no
> interrumpir la operación a medias. Los pasos por terminal de abajo siguen disponibles como
> alternativa y para cargas masivas.

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
   - Si las fichas no sirven, hay dos comportamientos posibles según el ajuste
     **`PERMITIR_CONOCIMIENTO_GENERAL`** (pestaña IA, activado por defecto):
     - **GENERAL** → el personaje responde con su conocimiento propio del LLM (`origen: GENERAL`).
       *(Aquí, más adelante, se podría enrutar a una búsqueda web.)*
     - **SIN_INFO** *(si está desactivado)* → **no se llama a ningún LLM**: se devuelve un mensaje
       fijo y editable (`MENSAJE_SIN_INFORMACION`, pestaña IA) del tipo "no tengo esa información".
       Coste cero y respuesta anclada estrictamente a tus documentos.

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
`DEBUG=true` en el `.env` el **backend lo imprime en SU consola** (la del `uvicorn`). Se hace en
el backend porque ahí ya se calcula todo: así el frontend, con `DEBUG=false`, **no recibe ni
procesa** datos de depuración (más ligero) y la interfaz que ve el niño queda **siempre limpia**.

> ⚠️ **`DEBUG` deja de ser "solo consola" en un punto:** cuando está activo, el chat **también**
> muestra al niño el desplegable **"📚 ¿De dónde lo he sacado?"** con los fragmentos usados en
> cada respuesta RAG (`Chat.tsx`). Es el único efecto de `DEBUG` visible fuera de la consola —
> por eso hay que dejarlo en `false` para la versión final, no solo por las trazas.

En la consola del backend verás líneas como:

```
[CHAT] 🟢 Evaluator → origen=RAG: respuesta FUNDAMENTADA en las fichas recuperadas de este personaje
[CHAT]        método: decidido GRATIS por la distancia coseno (sin llamar al LLM-juez)
[CHAT]        mejor distancia d=0.42  (umbrales coseno: BAJO=0.75→RAG, ALTO=0.95→GENERAL; entre ambos=dudoso)
[CHAT]        pregunta traducida (EN) que se buscó: "what do you eat"

[CHAT] 🟡 Evaluator → origen=GENERAL: las fichas no servían → responde con el conocimiento propio del LLM
[CHAT]        método: desempatado por el LLM-juez (la distancia caía en la zona dudosa)
[CHAT]        mejor distancia d=0.88  (umbrales coseno: BAJO=0.75→RAG, ALTO=0.95→GENERAL; entre ambos=dudoso)
[CHAT]        pregunta traducida (EN) que se buscó: "how much is 2+2"
```

Cada decisión imprime un **bloque de varias líneas**: el **origen** (🟢 RAG / 🟡 GENERAL) con su
explicación, el **método** con el que se decidió (`umbral` gratis o `llm`-juez), la **mejor
distancia** `d=...` con los umbrales activos, y la **pregunta traducida** a inglés que se buscó.
**Lo más importante es entender que `origen` y `metodo` son DOS cosas distintas:**

#### Eje 1 — `origen`: de DÓNDE sale el contenido de la respuesta

| `origen` | Icono | Qué significa |
|----------|-------|---------------|
| **RAG** | 🟢 | La respuesta está **fundamentada en las fichas** recuperadas de los documentos del personaje (ChromaDB). El LLM responde usando **solo** esa información → fiable y verificable. |
| **GENERAL** | 🟡 | Las fichas **no servían**, así que el personaje responde con el **conocimiento propio del modelo** (lo que Llama 3 ya sabe). Útil para lo que está fuera de los documentos (p. ej. "¿cuánto es 2+2?"), pero **no respaldado por tus fuentes**. |
| **SIN_INFO** | 🔴 | Las fichas **no servían** y `PERMITIR_CONOCIMIENTO_GENERAL` está **desactivado**: se devuelve el mensaje fijo `MENSAJE_SIN_INFORMACION` **sin llamar a ningún LLM** (coste cero). No aparece con la configuración de fábrica (ese ajuste viene activado). |

Se decide en `_decidir_origen` ([backend/services/rag_service.py](backend/services/rag_service.py)):
si las fichas recuperadas se consideran relevantes → **RAG**; si no, y `PERMITIR_CONOCIMIENTO_GENERAL`
está activo → **GENERAL**; si no, → **SIN_INFO**. Internamente, cada camino usa una vía distinta:
`_construir_prompt` (RAG) y `_construir_prompt_general` (GENERAL) llaman al LLM; SIN_INFO solo
rellena la plantilla `MENSAJE_SIN_INFORMACION` con `settings_service.rellenar`, sin llamada alguna.

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
> calibrar los umbrales). Con `PERMITIR_CONOCIMIENTO_GENERAL` desactivado, cambia `GENERAL` por
> `SIN_INFO` en esas mismas combinaciones (`SIN_INFO · umbral` / `SIN_INFO · llm`).

**En una frase:** `origen` = **qué fuente respondió** (documentos, modelo, o ninguno) · `metodo` =
**quién tomó la decisión** (un número gratis vs. una llamada al LLM-juez).

Con `DEBUG=false` (versión final para el usuario) no se imprime nada en consola. El JSON de
`/api/ask` sigue incluyendo `origen`/`metodo`/`distancia` (por si los necesitas), y el frontend
no los usa para nada visual — **excepto `fuentes`**, que solo viaja no-vacío cuando `DEBUG=true`
(ver el aviso más arriba sobre el desplegable "¿De dónde lo he sacado?").

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
| **ElevenLabs — STT** | transcripción de la pregunta hablada (`/api/transcribe`) | `[VOZ] 🎙️ STT · <bytes> → "<texto>"` |
| **ElevenLabs — TTS** | síntesis de la respuesta del personaje (`/api/ask`) | `[VOZ] 🔊 TTS · voz=<voz_id> · <chars> · <personaje_id>` |

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

### 6. Voz con ElevenLabs (Scribe STT + Flash TTS), pago por uso

**Decisión:** usar **ElevenLabs** para las dos mitades de la voz —transcribir la pregunta
hablada (**Scribe**) y dar voz a la respuesta (**Flash**)— con una **voz propia por personaje**
(`VOCES` en `backend/personajes.py`), en modalidad **pago por uso**.

**Por qué:**
- **Voz expresiva en español:** dar carácter a cada personaje (Sherlock grave, Da Vinci cálido)
  pide voces netamente mejores que las de un TTS genérico. El placeholder original preveía solo
  Whisper (Replicate) para STT; ElevenLabs cubre STT **y** TTS con una sola clave y SDK.
- **Latencia:** el modelo Flash responde rápido, importante para que un niño no espere.
- **Coherencia:** encaja con "todo lo pesado en la nube"; el backend solo hace una llamada HTTP más.

**Degradación:** un fallo de voz (o falta de clave) nunca rompe el chat: la respuesta de texto
se sirve igual y `audio_base64` viaja como `null`.

**Arquitectura:** STT es un endpoint aislado (`/api/transcribe`); el TTS viaja **acoplado** a la
respuesta de `/api/ask` (`audio_base64`), porque *toda* respuesta se habla (escrita o hablada).

**Grabación y reproducción en el frontend (SPA):** el navegador ya trae todo lo necesario, sin
librerías: la pregunta se graba con **`MediaRecorder`** (`getUserMedia`), que produce
webm/opus en Chrome y ogg/opus en Firefox —ambos formatos verificados contra Scribe, que deduce
el formato de los propios bytes—, y la respuesta se reproduce con el **`Audio`** estándar del
navegador (`data:audio/mpeg;base64,...`). `getUserMedia` solo existe en contextos seguros
(https o localhost); si no está disponible o el niño deniega el permiso, el micro se
deshabilita con un aviso claro y el chat de texto sigue intacto.

> *Nota histórica:* el primer frontend (de escritorio, en Flet) no podía usar `flet-audio`
> —un spike demostró que no graba micrófono y que, sin fijar versión, arrastraba Flet de 0.28.3
> a 1.x rompiendo la interfaz—, así que grababa con `sounddevice` + `soundfile`. La migración a
> la SPA React eliminó esa fricción al usar las APIs nativas del navegador.

### 7. Menú de configuración sin código (ajustes en caliente sobre SQLite)

**Decisión:** en lugar de tener todos los parámetros congelados como constantes de `config.py`,
la app incorpora una **pantalla de configuración** que edita en caliente (sin reiniciar) los
ajustes de IA, los prompts de sistema y las claves API. Los ajustes vivos se guardan en **SQLite**
(vía `settings_service`) y las claves API siguen en el `.env`; con la base de datos vacía, la app
se comporta **exactamente como antes** (los valores por defecto son los de `config.py`).

**Por qué existe esta pantalla — dos motivos:**
- **(1) Democratizar el uso.** Una persona **sin conocimientos de IA ni de programación** puede
  poner en marcha y personalizar la aplicación —pegar las claves de las plataformas, crear
  personajes y ubicaciones, subir documentos al RAG y tocar los parámetros del motor— **sin abrir
  el código**. Basta con darse de alta en los proveedores (Replicate, DeepL, ElevenLabs) e
  introducir las claves desde la propia interfaz.
- **(2) Facilitar el testeo y la calibración.** Cambiar la configuración para **probar y comparar
  resultados en caliente** (umbrales del Evaluator, modo `umbral`/`llm`/`hibrido`, chunking, modelo
  y temperatura del LLM, prompts) es inmediato: no hay que reiniciar el backend ni editar ficheros.
  Esto convierte la app en un **banco de pruebas** del pipeline RAG.

**El umbral del RAG se configura como distancia coseno directa (0–2), sin porcentaje.** Los
umbrales del Evaluator (`EVALUATOR_UMBRAL_BAJO` por defecto `0.75`, `EVALUATOR_UMBRAL_ALTO` `0.95`)
se editan tal cual son —la **distancia coseno** de ChromaDB, `0` = idéntico … `2` = opuesto— con
rango `0.00–2.00` y paso `0.01`, validando `0 ≤ BAJO ≤ ALTO ≤ 2`. **No** se convierten a "% de
similitud" en ningún punto. Se deja en la métrica nativa porque: **(a)** mantiene el sistema honesto
—lo que el adulto configura es exactamente lo que usa el motor—; **(b)** simplifica el código al
eliminar una capa de conversión; y **(c)** facilita la calibración, ya que el valor configurado se
compara directamente con la distancia real `d=...` que la app expone (en la respuesta de
`/api/ask` y en la consola con `DEBUG`).

**Toda la configuración va detrás de un PIN de adulto.** Como el área contiene las claves de las
plataformas y operaciones destructivas (borrar personajes/documentos) y la app la usan niños, la
primera vez se crea un **PIN** y a partir de ahí se pide para entrar (⚙️). El PIN se guarda
*hasheado* (nunca en claro) y el backend protege los endpoints sensibles; el flujo del niño
(elegir personaje/mundo, generar y chatear) sigue siendo público. Desde la pestaña **Sistema** se
puede cambiar el PIN, **exportar/importar** la configuración en JSON (ajustes + catálogos, nunca las
claves API) y cerrar sesión; antes de importar se hace una **copia de seguridad** automática del
fichero SQLite.

### 8. Evaluator con un tercer camino: `PERMITIR_CONOCIMIENTO_GENERAL` (RAG estricto, opcional)

**Decisión:** separar **cómo se decide** si las fichas sirven (`EVALUATOR_MODE`) de **qué se hace
cuando no sirven**. Por defecto, sigue cayendo a GENERAL (conocimiento propio del LLM, como
siempre); con `PERMITIR_CONOCIMIENTO_GENERAL` desactivado, cae a un tercer camino, `SIN_INFO`, que
devuelve un mensaje fijo y editable (`MENSAJE_SIN_INFORMACION`) **sin llamar a ningún LLM**.

**Por qué:** surgió al calibrar el modo `umbral` — su coste "0" solo se refiere a que no hay
llamada extra del juez, pero la llamada de **generación** de la respuesta (RAG o GENERAL) se hace
siempre, en los tres modos del Evaluator. No había forma de tener un chat que respondiera
**exclusivamente** con lo que hay en los documentos, sin ninguna llamada a un LLM cuando no hay
nada relevante que fundamentar. Este ajuste lo permite, ortogonal a `EVALUATOR_MODE`.

### 9. Detección automática de idioma en los documentos del RAG (sin checkbox)

**Decisión:** eliminar el checkbox manual "ya está en inglés" del visor de documentos.
Cada subida, ingesta por URL o edición de contenido llama **siempre** a DeepL, que
además de traducir devuelve `detected_source_lang`; si el idioma detectado ya es
inglés se conserva el texto **original** (no el eco de la traducción) para no
arriesgarse a alterar sutilmente un documento que no lo necesitaba.

**Por qué:** el checkbox era un punto de fallo humano — un documento en español sin
marcar se indexaba tal cual y arruinaba la recuperación para ese personaje, sin
ningún aviso. DeepL ya hacía la detección como efecto colateral de traducir (no hace
falta una llamada aparte), así que automatizarlo elimina el error sin coste extra.
Como contrapartida, DeepL pasa a ser **obligatorio** también para gestionar
documentos (antes solo lo era para el chat): sin clave configurada, no se puede
subir/editar ni un documento ya en inglés, porque la detección en sí depende de la
llamada a la API.

---

## 💡 Personalizar

- **Añadir personajes (sin tocar código):** ábrelo con el botón ⚙️ → pestaña **Personajes** y pulsa
  **➕ Nuevo personaje**. Rellena nombre, categoría, emoji, la descripción para su imagen (en inglés)
  y, si quieres que hable, elige una **voz** del desplegable de ElevenLabs (un personaje sin voz
  responde solo en texto). Al guardarlo se crea también su carpeta `backend/documentos/<id>/` para
  los documentos del RAG. El catálogo se guarda en la BBDD (tabla `personajes`) y lo consumen tanto
  el backend como el frontend por API. Los personajes que trae la app de fábrica se siembran desde
  `backend/personajes.py` en el primer arranque. Hay un tope de `MAX_PERSONAJES` (10 por defecto,
  `.env`, no editable desde el menú): al alcanzarlo, "➕ Nuevo personaje" se deshabilita solo.
- **Añadir ubicaciones (sin tocar código):** ⚙️ → pestaña **Ubicaciones** → **➕ Nueva ubicación**.
  Rellena nombre, emoji y la descripción del fondo (en inglés). El catálogo se guarda en la BBDD
  (tabla `ubicaciones`) y lo consumen backend y frontend por API. Las ubicaciones de fábrica se
  siembran desde `backend/ubicaciones.py` en el primer arranque.
- **Cambiar el modelo o el estilo:** `REPLICATE_MODEL` en el `.env` y el `STYLE_SUFFIX` en
  `backend/personajes.py`.

---

## 🛠️ Herramientas de desarrollo

- **Playwright MCP (Claude Code):** para que Claude Code pueda navegar y probar la SPA
  (`http://localhost:5173`) directamente — clics, lectura de la consola del navegador,
  capturas — sin permisos de administrador. Guía paso a paso en
  [docs/playwright-mcp.md](docs/playwright-mcp.md).
