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

Set `DEBUG=true` in the backend `.env` to print prompt traces, RAG decision traces, and voice traces (`[VOZ] 🎙️ STT ...` / `[VOZ] 🔊 TTS ...`) to the **backend console** (not the UI). Keep `false` for the child-facing build. The frontend's "Probar conexión" diagnostic button is controlled separately by `VITE_DEBUG=true` in `frontend-react/.env`.

## Architecture

**Two independent processes.** `backend/` (FastAPI) and `frontend-react/` (React SPA) run separately and communicate only over HTTP. The frontend's sole gateway to the backend is `frontend-react/src/api/client.ts`; the backend URL comes from `VITE_BACKEND_URL` in `frontend-react/.env` (in dev, Vite's proxy forwards `/api` and `/health` to the local backend, so no config is needed).

**Backend layering** — routers → services → config. Endpoints in `backend/routers/` stay thin: they validate, call a service, and map `ValueError` → HTTP 400 / other exceptions → 500. All real logic lives in `backend/services/`. All tunables are centralized in `backend/config.py`, read from `.env`.

- **Image generation** (`services/generation_service.py`, `routers/generation.py`): `POST /api/generate` (predefined location, JSON) and `POST /api/generate-on-photo` (child uploads a photo, multipart). Builds a single Replicate prompt and returns the image as base64. FLUX schnell (default) has **no negative prompt** — child-safety and style are baked into the *positive* prompt via `STYLE_SUFFIX`/`FRAMING` in `backend/personajes.py`. Prompts are ordered **most-important-first** (subject → framing → style) because FLUX's CLIP encoder truncates at ~77 tokens while T5 reads the rest; going over `CLIP_TOKEN_LIMIT` only logs a warning, it does not fail.
- **RAG chat** (`services/rag_service.py`, `routers/conversacion.py`): `POST /api/ask`. Flow: **translate** question ES→EN (DeepL) → **retrieve** top-K chunks for that character from ChromaDB (cosine distance) → **Evaluator/Router** decides RAG vs GENERAL → **generate** answer via Replicate LLM. See invariants below.
- **Ingestion** (`backend/ingest.py`, a standalone script, not part of the running server): loads `.pdf/.txt/.md` from `backend/documentos/<personaje_id>/`, chunks with LangChain's `RecursiveCharacterTextSplitter` (`CHUNK_SIZE`/`CHUNK_OVERLAP`), and indexes into ChromaDB tagging each chunk with `personaje_id`.
- **Voice** (`services/voice_service.py`, `routers/transcription.py`): `POST /api/transcribe` (audio→texto, ElevenLabs Scribe) feeds the existing `/api/ask`; `/api/ask` now also returns `audio_base64` (the answer voiced by ElevenLabs Flash using the character's `voz_id` from `VOCES`). ElevenLabs is the third provider (with Replicate and DeepL). Voice failures degrade to text-only (`audio_base64: null`) and never break the chat. On the frontend, recording/playback use the browser's built-in APIs with no extra libraries: `MediaRecorder` (`getUserMedia`) captures the mic (webm/opus in Chrome, ogg/opus in Firefox — both accepted by Scribe, which sniffs the format from the bytes), and the standard `Audio()` plays the mp3 (`data:audio/mpeg;base64,...`). `getUserMedia` only works in secure contexts (https or localhost); if it's unavailable or the child denies permission, the mic is disabled with a clear notice and text chat keeps working.

`backend/routers/_future_phases.py` no longer exists — voice input, originally planned around Whisper, shipped via ElevenLabs instead (see above).

## Critical invariants

- **`personaje_id` is a cross-cutting key** that must match in four (or five) places for a character to work end-to-end: `backend/personajes.py` (`PROMPTS` + `NOMBRES`, plus `VOCES` as a 5th site for characters that talk — each entry's `voz_id` is an ElevenLabs voice), `frontend-react/src/data/personajes.ts` (UI card), and the folder name `backend/documentos/<personaje_id>/`. Locations work the same way across `backend/ubicaciones.py` and `frontend-react/src/data/ubicaciones.ts`. Adding a character/location means editing the matching pair (or all four/five for a chatty character) with the **same id**.
- **English in, Spanish out.** The knowledge base, all retrieval queries, and every LLM prompt (`system`+`user` for RAG, GENERAL, and the Evaluator judge) are in **English** — Llama 3 follows English instructions better and embeddings score better in English. Only the child's *question* is translated (ES→EN via DeepL at runtime); the *answer* is generated directly in Spanish by prompt instruction. System prompts are hardcoded English strings and are **not** translated at runtime.
- **DeepL is mandatory for chat.** Without it, retrieval pulls the wrong chunks. `translation_service.traducir_es_en` raises `TranslationError` (a `ValueError` → HTTP 400) rather than degrading silently. `main.py`'s startup hook warns if DeepL is unreachable but does not block the server (so `/docs` and `/health` stay up).
- **Ingest before chatting.** `rag_service` only *reads* the ChromaDB collection; it never builds it. An empty collection logs a warning and yields poor answers. Re-run `python -m backend.ingest` after changing any document.
- **ChromaDB uses cosine distance** (`hnsw:space: "cosine"`, 0=identical … 2=opposite), set identically in both `ingest.py` and `rag_service.py`. The Evaluator's `EVALUATOR_UMBRAL_BAJO`/`ALTO` thresholds depend on this metric.

## The Evaluator (RAG vs GENERAL decision)

`rag_service._decidir_origen` decides whether an answer is grounded in retrieved chunks (`origen: RAG`) or falls back to the model's own knowledge (`origen: GENERAL`). Controlled by `EVALUATOR_MODE` in `.env`:

- `umbral` — distance thresholds only, no extra LLM call (free).
- `llm` — an LLM "judge" call answers YES/NO every time (smarter, costs a call).
- `hibrido` (default/recommended) — thresholds settle clear cases for free; the LLM judge only breaks ties in the ambiguous band between the two thresholds.

Calibrate `EVALUATOR_UMBRAL_BAJO`/`ALTO` by running with `DEBUG=true` and reading the `d=...` distances printed per question.
