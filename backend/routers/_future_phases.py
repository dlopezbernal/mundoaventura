"""
routers/_future_phases.py — Marcadores de las fases siguientes
===============================================================

Este archivo NO se usa todavía. Sirve como mapa de lo que vendrá, para que la
estructura del proyecto cuente la historia completa del pipeline.

Cuando llegue el momento de implementar cada fase, crearemos su propio router
(p. ej. `transcription.py`, `rag.py`) siguiendo el mismo patrón que
`generation.py`, y lo enchufaremos en `backend/main.py`.

──────────────────────────────────────────────────────────────────────────────
 (Generación de la escena con Replicate → YA IMPLEMENTADA en routers/generation.py)

 FASE 3A — Transcripción de voz            → router: transcription.py
   POST /api/transcribe
   Entrada: un archivo de audio (la pregunta del niño).
   Tecnología: Whisper (OpenAI).
   Salida: el texto transcrito de la pregunta.

 FASE 3B — Recuperación y respuesta (RAG)  → router: rag.py
   POST /api/ask
   Entrada: la pregunta en texto + qué personaje responde.
   Tecnología: LangChain + ChromaDB + LLM.
   Salida: respuesta "en primera persona" basada en enciclopedias infantiles.
──────────────────────────────────────────────────────────────────────────────
"""
