# 🌀 MundoAventura

> ¡Descubre tu próxima aventura!

[![CI](https://github.com/dlopezbernal/mundoaventura/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/dlopezbernal/mundoaventura/actions/workflows/ci.yml)

Herramienta educativa (para niños de 8 a 12 años) que **genera una escena divertida
combinando un lugar y un personaje histórico o prehistórico** (¡un T-Rex en un laboratorio!)
y te deja **conversar con ese personaje por texto o por voz**. Combina varias tecnologías de
Inteligencia Artificial en un pipeline por fases.

**Cliente-servidor desacoplado:** una **SPA React** (Vite + TypeScript, en el navegador) habla
por HTTP/REST con un backend **FastAPI**. Toda la IA pesada (imagen + LLM) corre en la nube
(**Replicate**), así que el backend es ligero y **no necesita GPU**; el índice del RAG
(ChromaDB) corre en local sobre CPU.

| Paso | Qué hace | Tecnología |
|------|----------|------------|
| **Elegir lugar y personaje** | Eliges una **ubicación** y un **personaje**. Cualquier combinación vale. | SPA React (sin IA) |
| **Generar la escena** | Combina lugar + personaje + estilo en un prompt y pide la imagen a la nube. | Replicate (FLUX schnell) |
| **Conversar (texto, RAG)** | El personaje responde **en primera persona**, fundamentado en documentos troceados. | LangChain · ChromaDB · DeepL · LLM |
| **Entrada por voz** | Graba la pregunta con el micro y la transcribe a texto. | Proveedor intercambiable: ElevenLabs Scribe · faster-whisper local · Whisper en Groq |
| **Respuesta por voz** | La respuesta se sintetiza con una voz propia por personaje y suena sola. | ElevenLabs Flash |

La respuesta llega **en directo** (streaming SSE): el niño empieza a leer y a oír a los
~1–2 s en vez de esperar a que se genere entera.

> **Documentación completa** en [`docs/`](docs/) (con [índice](docs/README.md)): arquitectura
> ([`ARQUITECTURA.md`](docs/ARQUITECTURA.md)), decisiones de diseño ([`DECISIONES.md`](docs/DECISIONES.md)),
> metodología y mediciones ([`EVALUACION.md`](docs/EVALUACION.md)), la teoría de fondo (qué es RAG,
> chunking, CLIP/T5) en el [anexo didáctico](docs/ANEXO-DIDACTICO.md), privacidad/RGPD en
> [`PRIVACIDAD.md`](docs/PRIVACIDAD.md), la puesta en producción en un VPS
> ([`DESPLIEGUE.md`](docs/DESPLIEGUE.md)) y el empaquetado como app de Android
> ([`APK-ANDROID.md`](docs/APK-ANDROID.md)); para la defensa, el [guion de demo](docs/DEFENSA.md) y el
> [trabajo futuro](docs/TRABAJO-FUTURO.md).

---

## 🚀 Puesta en marcha

### Requisitos

- **Python 3.12** y **[uv](https://docs.astral.sh/uv/)** (gestor de dependencias del backend).
- **Node 24+** (frontend).
- Claves de tres proveedores en la nube: **Replicate** (obligatoria), **DeepL**
  (obligatoria para el chat) y **ElevenLabs** (opcional, para la voz).

### 1. Instalar dependencias

```powershell
# Backend: crea .venv e instala EXACTAMENTE lo del uv.lock (fuente de reproducibilidad)
uv sync

# Frontend (una sola vez)
cd frontend-react; npm install; cd ..
```

> Sin `uv`, hay un `requirements-backend.txt` como *fallback sin pin*
> (`pip install -r requirements-backend.txt`). El backend es ligero: no instala
> torch ni diffusers.

### 2. Configurar el `.env`

```powershell
Copy-Item .env.example .env
```

Rellena las claves (el `.env.example` documenta cada variable):

- **`REPLICATE_API_TOKEN`** — obligatorio. Genera imágenes y (por defecto) el LLM del chat.
  Créalo en [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens).
- **`DEEPL_API_KEY`** — **obligatorio para el chat**: traduce la pregunta ES→EN antes de
  buscar; sin él la recuperación trae fichas equivocadas y el chat responde con un error
  claro. Clave gratis (500.000 chars/mes) en [deepl.com/pro-api](https://www.deepl.com/pro-api).
- **`ELEVENLABS_API_KEY`** — para la voz (transcribir la pregunta + dar voz a la respuesta).
  Sin él, la voz queda desactivada pero el **chat de texto sigue funcionando**.
  [elevenlabs.io](https://elevenlabs.io).

El LLM del chat es **intercambiable** (`LLM_PROVIDER`): por defecto `replicate` (Llama 3, la
línea base), o `openai` para un endpoint openai-compatible (Groq, Mistral, Ollama local…).
El estudio del Hito 6 eligió **Groq (Llama 3.1 70B)**; ver [`EVALUACION.md`](docs/EVALUACION.md)
y el [ADR-007](docs/decisiones/ADR-007-eleccion-llm.md).

### 3. Construir el índice del RAG (obligatorio antes de chatear)

```powershell
uv run python -m backend.ingest
```

Trocea los documentos de `backend/documentos/<personaje_id>/` e indexa los fragmentos en
ChromaDB. **Hay que hacerlo una vez** y repetirlo tras cambiar documentos. El repositorio ya
trae una base de conocimiento lista: **11 documentos** repartidos en cinco carpetas (T-Rex,
Triceratops, Peter Pan, Sherlock Holmes y Leonardo da Vinci), así que se puede chatear sin
aportar nada. Ver
[§ Preparar la base de conocimiento](#-preparar-la-base-de-conocimiento).

### 4. Arrancar backend + frontend

```powershell
# Ambos a la vez, cada uno en su ventana (Windows)
.\scripts\dev.ps1                 # o -Solo back / -Solo front
```

O a mano, en dos terminales:

```powershell
uv run uvicorn backend.main:app --reload    # backend → http://127.0.0.1:8000  (docs en /docs)
cd frontend-react; npm run dev              # frontend → http://localhost:5173
```

Comprueba `GET /health`: debe mostrar `token_configurado: true`, `deepl_ok: true` y
`elevenlabs_ok: true`. En desarrollo el proxy de Vite reenvía `/api` y `/health` al backend
local (mismo origen, sin CORS): **no hace falta configurar nada más**. Si el backend está en
otra máquina (p. ej. un túnel https de Colab), copia `frontend-react/.env.example` a
`frontend-react/.env` y pon su URL en `VITE_BACKEND_URL`.

---

## 🎮 Cómo se usa

La app va detrás de una **cuenta de familia** (el adulto se da de alta con email + contraseña;
la sesión es persistente). Al entrar:

1. **"¿Quién juega?"** — si la familia tiene varios niños, se elige el perfil (con uno solo se
   entra directo). El nombre y el sexo del niño personalizan el chat.
2. **Elige un personaje** en el carrusel.
3. **Elige un lugar** (o sube tu foto) y pulsa «Siguiente».
4. **La escena se genera sola** (con una animación «Creando…» mientras tanto). Al terminar
   aparece la imagen y, a su lado, un **chat**: escríbele o **díctale** una pregunta al
   personaje y te responderá en primera persona, con su propia voz, palabra a palabra.

La interfaz tiene **efectos de sonido tipo arcade** (girar el carrusel, elegir, enviar,
recibir…) **sintetizados con la Web Audio API**: ni un solo fichero de audio ni una librería
extra. Se apagan y encienden con el interruptor **🔊/🔇** del HUD, que está fuera del menú ☰
porque es un control del niño, y la preferencia se recuerda en el navegador. Ese interruptor
silencia **todo lo que suena**, también la voz del personaje: con el sonido apagado el chat
responde solo por texto, y al volver a encenderlo el personaje vuelve a hablar.

El botón **📖 Manual de usuario** (en el menú ☰ del HUD) abre la **guía en pantalla**, con una sección para el
niño (los 3 pasos y el chat) y otra para el adulto (cuenta de familia y ⚙️ Configuración). También
se llega a ella desde la pantalla de acceso, para poder leerla **antes** de crear la cuenta.

Dos zonas de adulto, cada una con su botón en el HUD:

- **⚙️ Configuración** — autoservicio de la familia: perfiles de niños (hasta `MAX_NINOS`, 4 por
  defecto), PIN de familia (protege la foto y la edición del perfil) y **eliminar la cuenta**
  (derecho de supresión del RGPD: borra la familia, sus perfiles, sus sesiones y su registro de
  uso).
- **🛡️ Admin** — configuración global compartida, detrás de contraseña de admin y con **2FA
  opcional**. Nueve pestañas: **APIs** (claves), **IA** (LLM, RAG y prompts), **Imagen**,
  **Voz**, **Personajes** (con sus documentos del RAG), **Ubicaciones**, **Correo** (SMTP de la
  verificación por email), **Auditoría** (registro de uso de la familia, exportable a CSV y con
  purga por antigüedad) y **Sistema** (contraseña, 2FA, import/export, copias).

> **Subir tu foto** pasa por un aviso de **consentimiento parental** (PIN de familia o casilla)
> antes de abrir el selector. **La foto no se guarda**: se procesa solo en memoria. Detalles en
> [`PRIVACIDAD.md`](docs/PRIVACIDAD.md).

### En el móvil, la tablet y como app instalable

La interfaz es **responsive**, diseñada *mobile-first* y con dos cortes: móvil hasta 640 px,
tablet entre 641 y 959 px, y escritorio desde 960 px. La escena y el chat se apilan o se ponen
lado a lado según el sitio que haya.

Además es una **PWA instalable**: hay `manifest.webmanifest`, iconos (incluido uno *maskable*) y
un service worker propio, así que el navegador ofrece **añadirla a la pantalla de inicio** y se
abre a pantalla completa, sin barra de direcciones. La propia **pantalla de acceso muestra un
botón «Instalar la app»** cuando el navegador lo permite. Empaquetarla además como **APK de
Android** (técnica TWA, que reutiliza esa misma PWA) está documentado paso a paso en
[`docs/APK-ANDROID.md`](docs/APK-ANDROID.md).

### Build de producción

```powershell
cd frontend-react
npm run build      # genera dist/ (estático)
npm run preview    # lo sirve en local para probar
```

`dist/` se sirve desde cualquier hosting estático. Si el frontend y el backend quedan en
**orígenes distintos**, limita los permitidos con `CORS_ORIGINS` en el `.env` del backend y
compila con `VITE_BACKEND_URL` apuntando al backend.

### Despliegue en un servidor propio

La app corre en producción en **[chatmundoaventura.com](https://chatmundoaventura.com)** sobre un
VPS: `uv sync --frozen` + systemd para el backend y **Caddy** (TLS automático de Let's Encrypt)
sirviendo la SPA y haciendo de proxy de `/api` y `/health`, de modo que SPA y API comparten origen
y no hay CORS que configurar. El procedimiento completo —instalación desde cero, migración de la
configuración, operación, copias y problemas frecuentes— está en
[`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md).

---

## 📚 Preparar la base de conocimiento

El conocimiento del chat **no está en el código**: viene de documentos que tú aportas, una
**carpeta por personaje** en `backend/documentos/<personaje_id>/` (`.pdf`, `.txt`, `.md`). El
idioma recomendado es **inglés** (mejores embeddings; la pregunta se traduce sola). El índice
se construye troceando esos documentos (ver [anexo: chunking](docs/ANEXO-DIDACTICO.md#2-el-chunking-con-solape-explicado)).

**Dos formas de gestionarlos:**

- **Sin terminal (recomendado):** 🛡️ Admin → **Personajes** → editar un personaje → sección
  **📄 Documentos**. Un visor completo: subir uno o varios ficheros, ingerir un artículo de
  Wikipedia por URL, ver/editar/descargar/copiar/borrar, con **detección automática de idioma**
  (DeepL) y **reindexado automático** del personaje afectado. Hay un botón **♻️ Reindexar todo**
  con barra de progreso real.
- **Por terminal (cargas masivas o CI):**

  ```powershell
  # (Opcional) descargar un artículo de Wikipedia limpio a backend/documentos/<id>/
  uv run python -m backend.fetch_wikipedia t-rex https://simple.wikipedia.org/wiki/Tyrannosaurus_rex

  # Reconstruir el índice completo (tras cambiar documentos fuera de la UI)
  uv run python -m backend.ingest
  ```

> DeepL es **obligatorio también aquí**: la detección de idioma de cada documento pasa por su
> API, así que no se puede subir/editar ni un documento ya en inglés sin la clave.

---

## 🔒 (Opcional) Transcripción local con faster-whisper — privacidad

El proveedor de voz→texto se elige con `STT_PROVIDER` (`elevenlabs` por defecto | `local` |
`groq`). Con `local` la transcripción la hace **faster-whisper en tu propio PC** —la voz del
niño no sale de la máquina, que es el argumento de RGPD—, tras instalar el extra opcional
(`uv sync --extra stt-local`) y ajustar `STT_LOCAL_MODEL`/`_DEVICE`/`_COMPUTE` en el `.env` o en
🛡️ Admin → Voz. Si no carga (en Windows suelen faltar las DLL de cuBLAS/cuDNN para `cuda`;
`STT_LOCAL_DEVICE=cpu` es el plan B), **cae solo a la nube** y la app nunca se queda muda. La
comparación de proveedores por WER y el porqué de todo esto, en el
[ADR-008](docs/decisiones/ADR-008-stt-local.md).

---

## 🗂️ Estructura del repositorio

| Carpeta | Qué hay dentro |
|---|---|
| `backend/` | La API FastAPI: `routers/` (endpoints finos), `services/` (toda la lógica), `documentos/` (la base de conocimiento del RAG, una carpeta por personaje) y, generados en tiempo de ejecución, el índice de ChromaDB (`chroma_db/`), la BBDD SQLite de configuración y los `avatares/`. |
| `frontend-react/` | La SPA (Vite + TypeScript): `src/` con pantallas, componentes y el **único** cliente HTTP (`src/api/client.ts`); `public/` con los iconos, el `manifest.webmanifest` y el service worker de la PWA. |
| `tests/` | La suite de `pytest` del backend (la que corre el CI). |
| `evals/` | El banco de pruebas: sets en YAML, runner, métricas y la línea base congelada. |
| `docs/` | Toda la documentación ([índice](docs/README.md)), con `decisiones/` (ADRs), `mediciones/`, `plan/` (los hitos H1–H10) e `historico/` (documentos de hitos ya cerrados). |
| `deploy/` | Lo que corre en el VPS: unidades de systemd, `Caddyfile` y los scripts de despliegue y de copia de seguridad. |
| `scripts/` | Utilidades de desarrollo: arranque doble (`dev.ps1`), generación de tipos desde OpenAPI y bancos de medida. |

---

## 🧪 Calidad (tests, lint, evaluación)

```powershell
uv run ruff check backend/ tests/       # lint (reglas E,F,I,UP,B,SIM)
uv run ruff format backend/ tests/      # formateo
uv run pytest --cov=backend             # tests + cobertura
uv run pre-commit install               # (una vez) engancha ruff + oxlint a cada commit
```

No es solo CI, es **CI/CD**. El flujo de GitHub Actions (`.github/workflows/ci.yml`) corre en
cada push y cada PR contra **`dev` y `main`** dos trabajos de verificación —lint + formato +
pytest (backend) y oxlint + build (frontend)— y un tercero, **`deploy`**, que solo se activa en
`main` y que, si los dos anteriores pasan, **publica en producción por SSH y comprueba después
el `/health` del sitio**. Es decir: un merge a `main` despliega solo. El procedimiento está en
[`DESPLIEGUE.md`](docs/DESPLIEGUE.md).

El **banco de pruebas** (`evals/`) mide la calidad del RAG con números; su metodología y
resultados están en [`EVALUACION.md`](docs/EVALUACION.md).

---

## 💡 Personalizar

- **Personajes y ubicaciones (sin tocar código):** 🛡️ Admin → pestañas **Personajes** /
  **Ubicaciones** → **➕ Nuevo**. El catálogo vive en SQLite y lo consumen backend y frontend por
  API. Los de fábrica se siembran desde `backend/personajes.py` / `backend/ubicaciones.py` en el
  primer arranque. Tope: `MAX_PERSONAJES` (10 por defecto, `.env`); el de niños por familia es
  `MAX_NINOS` (4). Ambos son límites **fijos de despliegue**: se cambian en el `.env`, no desde
  la interfaz.
- **Avatar de un personaje o de una ubicación:** al editarlo, **🎨 Generar imagen** dibuja su
  retrato a partir de su propio prompt y lo recorta sobre fondo transparente; el carrusel lo usa
  en lugar del emoji. Ojo: **son dos llamadas a Replicate por avatar** (dibujo + recorte del
  fondo), así que **cuesta dinero** cada vez que se pulsa.
- **Parámetros del motor (en caliente):** 🛡️ Admin edita umbrales del Evaluator, chunking,
  modelo/temperatura del LLM, prompts de sistema, etc. sin reiniciar (se guardan en SQLite; con
  la BBDD vacía la app usa los valores por defecto de `config.py`).
- **Modelo o estilo de imagen:** `REPLICATE_MODEL` en el `.env`; el estilo (`STYLE_SUFFIX`) es un
  ajuste editable en 🛡️ Admin → **Imagen**.

---

## 🛠️ Herramientas de desarrollo

- **Modo desarrollo:** `DEBUG=true` en el `.env` del backend enciende las trazas de diagnóstico
  en la **consola del backend** (prompts, origen RAG/GENERAL, voz). El botón «🔌 Probar conexión»
  del frontend se activa aparte con `VITE_DEBUG=true`. Cómo leer esas trazas: ver el
  [anexo didáctico](docs/ANEXO-DIDACTICO.md#5-la-traza-de-prompts-con-debugtrue).
- **Playwright MCP (Claude Code):** para que Claude Code navegue y pruebe la SPA. Guía en
  [docs/playwright-mcp.md](docs/playwright-mcp.md).
