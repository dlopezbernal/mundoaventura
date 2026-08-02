# ADR-009 — Streaming de la respuesta (SSE) + TTS por frases + caché de audio

- **Estado:** propuesta — **implementado y verde**; la medición de latencia p50/p95
  (primer token, primera sílaba) se completa en la máquina del usuario (el sandbox no
  tiene claves de LLM/TTS para cronometrar el flujo real).
- **Fecha:** 2026-08-02
- **Hito:** H8 (`feat/h8-streaming`)
- **Depende de:** H5 (`completar_streaming`), H7 (rama madre; ambos tocan `Chat.tsx`).

## Contexto

La cadena era estrictamente secuencial y el niño no oía nada hasta el final:
LLM completo → TTS completo → base64 → JSON → reproducir (~7–12 s en blanco). El salto
de latencia PERCIBIDA sale casi entero de **quitar etapas serializadas**, no de pagar
más: empezar a mostrar el texto en cuanto llega el primer token y a hablar en cuanto
cierra la primera frase.

## Decisión

Un canal **SSE** nuevo, `POST /api/ask/stream`, que emite eventos `fuentes` → `token`
(uno por trozo del LLM) → `audio_chunk` (uno por FRASE sintetizada) → `fin`. El
endpoint **JSON `/api/ask` se mantiene intacto** (lo usa el runner y es la vía de
compatibilidad) — criterio de aceptación explícito.

- **Streaming de tokens:** `llm_service.completar_streaming` pasa de esqueleto (H5) a
  real: cede el iterador nativo de Replicate y los deltas de `stream=True` en openai.
- **Separación de capas intacta:** `rag_service.responder_streaming` cede solo TEXTO
  (comparte `_preparar` con `responder`, así el JSON y el streaming no divergen);
  `chat_service.responder_streaming` orquesta y añade la voz. `rag_service` sigue sin
  saber que existe ElevenLabs.
- **TTS por frases:** `chat_service` acumula tokens y, en cuanto se cierra una frase
  (`.?!…`, vía `dividir_frases`), sintetiza ESA frase y emite su `audio_chunk` mientras
  el LLM sigue generando. El frontend encola y reproduce las frases en orden.
- **Caché de audio en disco** (`audio_cache`): `hash(voz_id, modelo_tts, texto) → mp3`.
  Las frases fijas (`MENSAJE_SIN_INFORMACION`, `FRASE_PRUEBA_VOZ`) y las preguntas
  repetidas dejan de re-sintetizarse — era dinero regalado. La usan el streaming por
  frases y también el `/api/ask` JSON (respuesta completa cacheada).
- **Frontend:** render incremental del texto (token a token), cola de reproducción de
  audio (frase a frase, sin pisarse), y el "pensando…" desaparece con el primer token.

## Degradación (criterio de aceptación)

Si el TTS falla a mitad de respuesta, `_sintetizar_cacheado` devuelve None: no se emite
ese `audio_chunk` pero **el texto sigue llegando**. Si el flujo entero revienta antes de
empezar (personaje inexistente, DeepL caído), se emite un evento `error` con mensaje apto
para el niño (los 500 internos van saneados con `error_id`, sin filtrar el detalle).

## Mejora aparte (§6): imagen en webp

`IMG_OUTPUT_FORMAT` pasa a **`webp`** por defecto: una escena 16:9 en PNG pesa varios MB
y, al viajar en base64 dentro del JSON, crece otro +33%; en webp pesa una fracción. El
frontend **deduce el tipo de imagen de los bytes** (`SceneView.mimeDeBase64`: webp→"UklGR",
jpg→"/9j/", png por defecto), así el formato es intercambiable sin tocar el render.
Devolver la imagen por URL (en vez de incrustada) queda como trabajo futuro.

## Medición — p50/p95 (a completar en la máquina del usuario)

Con el runner (endpoint JSON) y un cronómetro del flujo SSE real. Pegar aquí la tabla:

| Métrica | Antes (JSON) | Después (SSE) | Objetivo |
|---|---|---|---|
| Primer token en pantalla | fin de todo (~s) | | < 1 s |
| Primera sílaba de audio | fin de todo (~s) | | < 1,5 s |
| Respuesta completa p50/p95 | | | — |
| Coste TTS en preguntas repetidas | 100% | | ↓ por caché |

## Consecuencias

- **Código backend:** `conversacion.ask_stream` (SSE), `chat_service.responder_streaming`
  + `dividir_frases` + `_sintetizar_cacheado`, `rag_service._preparar`/`responder_streaming`,
  `llm_service.completar_streaming` real, `audio_cache` (nuevo), `errores.mensaje_generico`.
  **Sin dependencia nueva** (SSE se emite a mano con `StreamingResponse`).
- **Código frontend:** `client.askStream` (fetch + parseo SSE), `Chat.tsx` (render
  incremental + cola de audio), `SceneView` (mime por bytes).
- **Endpoint JSON `/api/ask` intacto:** el runner y los clientes antiguos siguen igual.
- **Caché de audio:** vive en `backend/.cache/tts/` (gitignored, se regenera sola).
- **Concurrencia:** el endpoint SSE es `def`; Starlette itera el generador síncrono en
  el threadpool, así el event loop no se bloquea (invariante de H2).
- **Plan B no necesario:** se implementó el alcance completo (texto + voz por frases +
  caché); el streaming de texto funciona de forma independiente si el audio fallara.
