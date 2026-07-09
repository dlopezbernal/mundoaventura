# Arquitectura — Máquina del Tiempo en tu Habitación

Documento técnico de conjunto del pipeline completo (imagen + RAG + voz). El
README es la guía de uso; este documento es la referencia de arquitectura para la
memoria final del capstone.

## Visión general

App educativa (niños 8–12) cliente-servidor desacoplada:

- **Frontend (SPA React):** Vite + React 18 + TypeScript, en el navegador; asistente por
  pasos: catálogos (carrusel), escena y chat (texto + voz). El frontend original de Flet
  se conserva como referencia en `legacy/`.
- **Backend (FastAPI):** routers finos → services → config. Sin GPU local.
- **Nube:** Replicate (imagen + LLM), DeepL (traducción), ElevenLabs (voz).

## Los tres proveedores

| Proveedor | Para qué | Dónde |
|-----------|----------|-------|
| **Replicate** | Generación de imagen (FLUX) y LLM del chat (Llama 3) | `generation_service.py`, `rag_service.py` |
| **DeepL** | Traducción ES→EN de la pregunta (mejora el retrieval) | `translation_service.py` |
| **ElevenLabs** | Voz: transcripción (Scribe/STT) y síntesis (Flash/TTS) | `voice_service.py` |

## Flujo de una pregunta por voz (secuencia)

```
Niño (SPA React)   Backend (FastAPI)         Nube
   │  MediaRecorder      │                     │
   │  (webm/ogg opus)    │                     │
   │───/api/transcribe──►│──Scribe (STT)──────►│  ElevenLabs
   │◄──── texto ES ──────│◄────────────────────│
   │                     │                     │
   │───/api/ask─────────►│──DeepL ES→EN───────►│  DeepL
   │                     │──retrieval (ChromaDB, local CPU)
   │                     │──Evaluator (umbral/LLM)
   │                     │──LLM respuesta ES──►│  Replicate
   │                     │──Flash (TTS)───────►│  ElevenLabs
   │◄── texto + audio ───│◄────────────────────│
   │  (burbuja + auto-play con Audio())        │
```

Una pregunta **escrita** salta `/api/transcribe`: va directa a `/api/ask` y la
respuesta vuelve igualmente con `audio_base64` (toda respuesta se habla).

En el frontend, la voz usa las **APIs estándar del navegador**, sin librerías:
la pregunta se graba con **`MediaRecorder`** (`getUserMedia`), que produce
webm/opus en Chrome y ogg/opus en Firefox — ambos aceptados por Scribe, que
deduce el formato de los propios bytes —, y la respuesta se reproduce con
**`Audio()`** (`data:audio/mpeg;base64,...`). `getUserMedia` solo existe en
contextos seguros (https o localhost): fuera de ellos, o si se deniega el
permiso, el micro se deshabilita con un aviso claro y el chat de texto sigue
funcionando.

> *Nota histórica:* el frontend legacy de Flet no podía usar `flet-audio` (un
> spike comprobó que no graba y que arrastraba una actualización de Flet que
> rompía la interfaz), así que grababa con `sounddevice` + `soundfile` y
> reproducía con `sounddevice`. Ver `legacy/`.

## Invariante `personaje_id`

Una misma clave conecta cinco sitios (los cuatro primeros para cualquier
personaje; el quinto solo si habla):

1. `backend/personajes.py` → `PROMPTS`
2. `backend/personajes.py` → `NOMBRES`
3. `frontend-react/src/data/personajes.ts` → tarjeta visual
4. `backend/documentos/<personaje_id>/` → base de conocimiento
5. `backend/personajes.py` → `VOCES` (`voz_id` de ElevenLabs) — solo si el personaje habla

Las ubicaciones siguen el mismo patrón (sin voz) entre `backend/ubicaciones.py` y
`frontend-react/src/data/ubicaciones.ts`.

## Degradación y modo DEBUG

- **Degradación:** sin ElevenLabs (o si el TTS falla), `audio_base64` es `null` y el
  chat de texto sigue vivo. Sin DeepL, el chat responde con un error claro (la
  traducción es obligatoria para el RAG). En el frontend, si no hay `getUserMedia`
  (contexto no seguro), micrófono o permiso, el micro se deshabilita y el chat de
  texto sigue disponible igualmente (la voz es un añadido, no un requisito del flujo).
- **DEBUG (`config.DEBUG`):** trazas en la consola del backend: prompts al LLM/DeepL,
  origen RAG/GENERAL (`[CHAT] ...`) y voz (`[VOZ] 🎙️ STT ...`, `[VOZ] 🔊 TTS ...`).
