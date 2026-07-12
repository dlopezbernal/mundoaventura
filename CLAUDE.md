# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Educational app (kids 8–12) that generates a fun scene combining a **location** + a **historical/prehistoric character** (e.g. a friendly T-Rex in a lab), then lets the child **chat with that character** via a RAG pipeline. Decoupled **client-server**: a **React SPA** (Vite + TypeScript, in the browser) talks over HTTP/REST to a **FastAPI** backend. All heavy AI (image generation + LLM) runs in the cloud on **Replicate**; the backend stays lightweight (no torch/CUDA). The RAG index (ChromaDB) runs locally on CPU.

Codebase comments, docstrings, and the README are in **Spanish** — match that when editing.

## Commands

```powershell
# One-time setup (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-backend.txt
Copy-Item .env.example .env          # then fill REPLICATE_API_TOKEN, DEEPL_API_KEY, and ELEVENLABS_API_KEY
cd frontend-react; npm install; cd ..   # frontend deps (Node 20+), one-time

# Run the backend (one terminal) — serves http://127.0.0.1:8000, docs at /docs
uvicorn backend.main:app --reload

# Run the frontend (another terminal) — Vite dev server at http://localhost:5173
cd frontend-react; npm run dev          # proxies /api and /health to the backend

# Build/refresh the RAG index — REQUIRED before chat works, and after any doc change.
# Wipes and rebuilds the ChromaDB collection from scratch each run.
python -m backend.ingest

# (Optional) download a clean Wikipedia article into backend/documentos/<id>/, then re-ingest
python -m backend.fetch_wikipedia t-rex https://simple.wikipedia.org/wiki/Tyrannosaurus_rex
```

There is **no automated test suite**. Verify changes manually: check `GET /health` shows `token_configurado: true`, `deepl_ok: true`, and `elevenlabs_ok: true`, then exercise the flow through the React UI or `/docs`.

Set `DEBUG=true` to print prompt traces, RAG decision traces, and voice traces (`[VOZ] 🎙️ STT ...` / `[VOZ] 🔊 TTS ...`) to the **backend console** (not the UI). `DEBUG` is now a hot-editable setting (`settings_service`, seeded from the `.env` value), so it can also be toggled from the config menu's "Sistema" tab without a restart. Keep it off for the child-facing build. The frontend's "Probar conexión" diagnostic button is controlled separately by `VITE_DEBUG=true` in `frontend-react/.env`.

## Architecture

**Two independent processes.** `backend/` (FastAPI) and `frontend-react/` (React SPA) run separately and communicate only over HTTP. The frontend's sole gateway to the backend is `frontend-react/src/api/client.ts`; the backend URL comes from `VITE_BACKEND_URL` in `frontend-react/.env` (in dev, Vite's proxy forwards `/api` and `/health` to the local backend, so no config is needed).

**Backend layering** — routers → services → config. Endpoints in `backend/routers/` stay thin: they validate, call a service, and map `ValueError` → HTTP 400 / other exceptions → 500. All real logic lives in `backend/services/`. Tunables are **no longer read as frozen `config.py` constants**: they go through `backend/services/settings_service.py`, which returns the *live* value from **SQLite** (in-memory cache, invalidated on save) and **falls back to the `config.py` default** when the DB has no override. So a change made in the config menu takes effect on the **next request without a restart**, and an empty DB behaves exactly like before. `config.py` still holds the defaults (and reads secrets from `.env`); the no-code config menu is documented in README ("Decisiones de diseño") and ARQUITECTURA.md.

**Admin gate (Hito 7).** The whole config area sits behind an **adult PIN** (`backend/services/admin_service.py`): the PIN is stored PBKDF2-hashed in the `settings` table (reserved key, not in `_SPEC`, never exported), login returns an in-memory session token, and the `requiere_admin` dependency guards the sensitive endpoints. In `main.py` the `config`/`apis`/`documentos` routers are protected wholesale; the `personajes`/`ubicaciones` routers protect only their **writes** and `GET /api/voices` (the catalog `GET`s stay public for the child flow, along with `/generate`, `/ask`, `/transcribe`, `/health`). The frontend sends the token as `X-Admin-Token` on every request (`client.ts`), and the Sistema tab offers PIN change, JSON **import/export** (`/api/admin/export`|`import` — settings + catalogs, never secrets) and logout; import first calls `admin_service.backup_sqlite()`.

- **Image generation** (`services/generation_service.py`, `routers/generation.py`): `POST /api/generate` (predefined location, JSON) and `POST /api/generate-on-photo` (child uploads a photo, multipart). Builds a single Replicate prompt and returns the image as base64. FLUX schnell (default) has **no negative prompt** — child-safety and style are baked into the *positive* prompt via `STYLE_SUFFIX`/`FRAMING`, editable settings (categoría `estilo_imagen`, config menu's "General" tab; defaults seeded from `backend/personajes.py`). Prompts are ordered **most-important-first** (subject → framing → style) because FLUX's CLIP encoder truncates at ~77 tokens while T5 reads the rest; going over `CLIP_TOKEN_LIMIT` only logs a warning, it does not fail.
- **RAG chat** (`services/rag_service.py`, `routers/conversacion.py`): `POST /api/ask`. Flow: **translate** question ES→EN (DeepL) → **retrieve** top-K chunks for that character from ChromaDB (cosine distance) → **Evaluator/Router** decides RAG vs GENERAL → **generate** answer via Replicate LLM. See invariants below.
- **Ingestion / documents** (`services/documentos_service.py`, `routers/documentos.py`): the RAG knowledge base is now managed **from the config UI** (Personajes → Documentos) — `POST /api/personajes/{id}/documentos` (upload `.pdf/.txt/.md`, multipart), `POST .../documentos/url` (Wikipedia URL, wraps `fetch_wikipedia`), `DELETE .../documentos/{doc_id}`, `POST .../reindex` (per-character) and `POST /api/reindex` (global). Files live in `backend/documentos/<personaje_id>/`; metadata rows in the `documentos` table. On save, if the adult didn't mark "already in English", the text is translated ES→EN with DeepL (batched for long docs) before indexing. Reindexing is **incremental**: changing one character's docs only rebuilds *its* chunks (`collection.delete(where={"personaje_id": id})` + re-index that folder), never the others; a global reindex deletes+recreates the whole collection and invalidates `rag_service`'s cached handle. `backend/ingest.py` (the standalone `python -m backend.ingest` CLI) still does a full reindex but now **delegates to `documentos_service`** (single source of truth for reading/chunking/indexing). Chunking uses LangChain's `RecursiveCharacterTextSplitter` (`CHUNK_SIZE`/`CHUNK_OVERLAP`), tagging each chunk with `personaje_id`.
- **Voice** (`services/voice_service.py`, `routers/transcription.py`): `POST /api/transcribe` (audio→texto, ElevenLabs Scribe) feeds the existing `/api/ask`; `/api/ask` now also returns `audio_base64` (the answer voiced by ElevenLabs Flash using the character's `voz_id` from `VOCES`). ElevenLabs is the third provider (with Replicate and DeepL). Voice failures degrade to text-only (`audio_base64: null`) and never break the chat. On the frontend, recording/playback use the browser's built-in APIs with no extra libraries: `MediaRecorder` (`getUserMedia`) captures the mic (webm/opus in Chrome, ogg/opus in Firefox — both accepted by Scribe, which sniffs the format from the bytes), and the standard `Audio()` plays the mp3 (`data:audio/mpeg;base64,...`). `getUserMedia` only works in secure contexts (https or localhost); if it's unavailable or the child denies permission, the mic is disabled with a clear notice and text chat keeps working.

`backend/routers/_future_phases.py` no longer exists — voice input, originally planned around Whisper, shipped via ElevenLabs instead (see above).

## Critical invariants

- **`personaje_id` is a cross-cutting key.** Since the config menu (Hito 4), the character catalog lives in the **`personajes` SQLite table** (columns `nombre`, `categoria`, `emoji`, `prompt_imagen`, `voz_id`, `activo`, …), read through `backend/services/personajes_service.py` and consumed by **both** backend (image generation + RAG chat) and frontend **via `GET /api/personajes`** — the frontend no longer holds a static catalog. `backend/personajes.py` is now only the **seed source** (`PROMPTS`/`NOMBRES`/`VOCES`/`CATEGORIAS`/`EMOJIS`, plus the global `STYLE_SUFFIX`/`FRAMING` defaults — the *live* values are `settings_service` settings, categoría `estilo_imagen`), dumped to the table on first startup (`seed.py`, idempotent + backfill). Creating a character from the Personajes tab (`POST /api/personajes`) writes the row **and** creates its `backend/documentos/<personaje_id>/` folder for the RAG. So the only remaining hand-edited site for a character is that documents folder; `voz_id` (an ElevenLabs voice) stays optional (no voice = text-only). **Locations now work the same way** (Hito 6): the catalog lives in the **`ubicaciones` SQLite table** (`nombre`, `emoji`, `prompt`, `activo`), read through `backend/services/ubicaciones_service.py`, consumed by backend (image generation) and frontend via `GET /api/ubicaciones` (CRUD at `POST/PUT/DELETE /api/ubicaciones`); `backend/ubicaciones.py` is now just the seed source (`UBICACIONES`/`NOMBRES`/`EMOJIS`) and the old `frontend-react/src/data/ubicaciones.ts` was removed.
- **English in, Spanish out.** The knowledge base, all retrieval queries, and every LLM prompt (`system`+`user` for RAG, GENERAL, and the Evaluator judge) are in **English** — Llama 3 follows English instructions better and embeddings score better in English. Only the child's *question* is translated (ES→EN via DeepL at runtime); the *answer* is generated directly in Spanish by prompt instruction. The system/user prompts are **editable settings** (defaults live in `settings_service.py`, externalized from `rag_service.py`, with `{nombre}`/`{fichas}`/`{pregunta}` placeholders filled by literal replace); they are English by default and are **not** translated at runtime.
- **DeepL is mandatory for chat.** Without it, retrieval pulls the wrong chunks. `translation_service.traducir_es_en` raises `TranslationError` (a `ValueError` → HTTP 400) rather than degrading silently. `main.py`'s startup hook warns if DeepL is unreachable but does not block the server (so `/docs` and `/health` stay up).
- **Ingest before chatting.** `rag_service` only *reads* the ChromaDB collection; it never builds it. An empty collection logs a warning and yields poor answers. Managing docs from the config UI **auto-reindexes** the affected character; the `python -m backend.ingest` CLI still does a full rebuild after out-of-band document changes.
- **ChromaDB uses cosine distance** (`hnsw:space: "cosine"`, 0=identical … 2=opposite), set identically in `documentos_service` (indexing) and `rag_service.py` (querying). The Evaluator's `EVALUATOR_UMBRAL_BAJO`/`ALTO` thresholds depend on this metric.
- **The RAG threshold is exposed and stored as the raw cosine distance (0–2), never as a percentage.** The config UI edits `EVALUATOR_UMBRAL_BAJO`/`ALTO` directly as floats in `[0, 2]` (step 0.01, validating `0 ≤ BAJO ≤ ALTO ≤ 2`). Do **not** add any `(1 − d/2) × 100` conversion or "% similarity" label — the value the adult configures must be exactly what the engine uses, and it's compared against the real `d=...` shown in `/api/ask` and the `DEBUG` console.

## The Evaluator (RAG vs GENERAL decision)

`rag_service._decidir_origen` decides whether an answer is grounded in retrieved chunks (`origen: RAG`) or falls back to the model's own knowledge (`origen: GENERAL`). Controlled by `EVALUATOR_MODE` (a hot-editable setting via `settings_service`; default from `.env`):

- `umbral` — distance thresholds only, no extra LLM call (free).
- `llm` — an LLM "judge" call answers YES/NO every time (smarter, costs a call).
- `hibrido` (default/recommended) — thresholds settle clear cases for free; the LLM judge only breaks ties in the ambiguous band between the two thresholds.

Calibrate `EVALUATOR_UMBRAL_BAJO`/`ALTO` by running with `DEBUG=true` and reading the `d=...` distances printed per question.
