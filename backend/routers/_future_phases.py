"""
routers/_future_phases.py — Marcadores de las fases siguientes
===============================================================

Este archivo NO se usa todavía. Sirve como mapa de lo que vendrá, para que la
estructura del proyecto cuente la historia completa del pipeline.

Cuando llegue el momento de implementar la fase, crearemos su propio router
(`transcription.py`) siguiendo el mismo patrón que `generation.py` y
`conversacion.py`, y lo enchufaremos en `backend/main.py`.

──────────────────────────────────────────────────────────────────────────────
 (Generación de la escena con Replicate → YA IMPLEMENTADA en routers/generation.py)

 (Conversación por texto / RAG → YA IMPLEMENTADA en routers/conversacion.py:
  POST /api/ask, con ChromaDB + LLM en Replicate, documentos en backend/documentos/)

 SIGUIENTE — Transcripción de voz          → router: transcription.py
   POST /api/transcribe
   Entrada: un archivo de audio (la pregunta del niño grabada con el micro).
   Tecnología: Whisper (vía Replicate).
   Salida: el texto transcrito, que se enviará a /api/ask para conversar por voz.
──────────────────────────────────────────────────────────────────────────────
"""
