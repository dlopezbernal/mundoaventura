# Arquitectura — Máquina del Tiempo en tu Habitación

Documento técnico de conjunto del pipeline completo (imagen + RAG + voz). El
README es la guía de uso; este documento es la referencia de arquitectura para la
memoria final del capstone.

## Visión general

App educativa (niños 8–12) cliente-servidor desacoplada:

- **Frontend (Flet):** asistente por pasos; catálogos, escena y chat (texto + voz).
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
Niño (Flet)        Backend (FastAPI)         Nube
   │  audio (mic)        │                     │
   │───/api/transcribe──►│──Scribe (STT)──────►│  ElevenLabs
   │◄──── texto ES ──────│◄────────────────────│
   │                     │                     │
   │───/api/ask─────────►│──DeepL ES→EN───────►│  DeepL
   │                     │──retrieval (ChromaDB, local CPU)
   │                     │──Evaluator (umbral/LLM)
   │                     │──LLM respuesta ES──►│  Replicate
   │                     │──Flash (TTS)───────►│  ElevenLabs
   │◄── texto + audio ───│◄────────────────────│
   │  (burbuja + auto-play)                    │
```

Una pregunta **escrita** salta `/api/transcribe`: va directa a `/api/ask` y la
respuesta vuelve igualmente con `audio_base64` (toda respuesta se habla).

En el frontend, la grabación del micro y la reproducción de la respuesta **no
pasan por los controles de audio de Flet** (`flet-audio`): un spike (Task 5)
comprobó que esa librería no graba y que, sin pinnear versión, arrastra una
actualización de Flet 0.28.3 → 1.x que rompe la interfaz (API pre-0.80 usada por
este proyecto: `ft.app`, `ImageFit`, `FilePicker` por callback). Por eso se usan
librerías autocontenidas e independientes de Flet: `sounddevice` + `soundfile`
para grabar el `.wav` del micrófono, y `just-playback` para reproducir el mp3 de
la respuesta sin bloquear la UI (con `numpy` de apoyo para el buffer PCM). Ver
`requirements-frontend.txt`.

## Invariante `personaje_id`

Una misma clave conecta cinco sitios (los cuatro primeros para cualquier
personaje; el quinto solo si habla):

1. `backend/personajes.py` → `PROMPTS`
2. `backend/personajes.py` → `NOMBRES`
3. `frontend/personajes.py` → tarjeta visual
4. `backend/documentos/<personaje_id>/` → base de conocimiento
5. `backend/personajes.py` → `VOCES` (`voz_id` de ElevenLabs) — solo si el personaje habla

Las ubicaciones siguen el mismo patrón (sin voz) entre `backend/ubicaciones.py` y
`frontend/ubicaciones.py`.

## Degradación y modo DEBUG

- **Degradación:** sin ElevenLabs (o si el TTS falla), `audio_base64` es `null` y el
  chat de texto sigue vivo. Sin DeepL, el chat responde con un error claro (la
  traducción es obligatoria para el RAG). En el frontend, si `sounddevice`/`soundfile`
  o `just-playback` no están instalados o fallan, el chat de texto sigue disponible
  igualmente (la voz es un añadido, no un requisito del flujo).
- **DEBUG (`config.DEBUG`):** trazas en la consola del backend: prompts al LLM/DeepL,
  origen RAG/GENERAL (`[CHAT] ...`) y voz (`[VOZ] 🎙️ STT ...`, `[VOZ] 🔊 TTS ...`).
