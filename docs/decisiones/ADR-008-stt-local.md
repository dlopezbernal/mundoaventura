# ADR-008 — Transcripción local (STT) con faster-whisper + proveedor seleccionable

- **Estado:** propuesta — **abstracción y fallback IMPLEMENTADOS y verdes**; la
  verificación en GPU y la tabla WER se completan en la máquina del usuario (el sandbox
  no tiene GPU/CUDA ni clips de voz infantil).
- **Fecha:** 2026-08-02
- **Hito:** H7 (`feat/h7-stt-local`)
- **Depende de:** H5 (patrón de capa de proveedor) y el flujo de voz existente (H-voz).

## Contexto

La transcripción de la pregunta hablada del niño (voz→texto) la hacía **ElevenLabs
Scribe** en la nube. Funciona, pero **la voz del niño sale del PC** hacia un tercero.
Para una app infantil española, mover el STT a **local** no es un ahorro de coste/latencia
(que también): es el **argumento central del capítulo de RGPD** — con STT local, toda la
voz y todo el historial de preguntas del menor se procesan en el propio equipo.

`faster-whisper` (CTranslate2, **sin torch**) corre `large-v3-turbo` en **int8** con
~1–1,5 GB de VRAM (con 6 GB sobran), transcribe 5 s de audio en <1 s, en español, gratis
y sin conexión.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| A. **faster-whisper local + capa de proveedor seleccionable** | Privacidad (voz no sale del PC); gratis; sin torch; reversible a nube | Instalación en Windows (DLLs cuBLAS/cuDNN) puede doler |
| B. Seguir solo con ElevenLabs (nube) | Cero fricción de instalación | La voz del niño sale del PC — pierde el eje de RGPD |
| C. STT local **obligatorio** (sin nube) | Máxima privacidad | Un clon sin GPU no arranca; frágil para la demo |

## Decisión

**Opción A**, calcada del patrón de `llm_service` (H5): un `stt_service` con
`STT_PROVIDER` (`elevenlabs` | `local` | `groq`) por el que pasa **toda** la
transcripción. `voice_service.transcribir` queda como puerta pública (router y tests
intactos) y delega.

- **Fallback automático:** si `local` no carga (paquete ausente, o DLLs de cuBLAS/cuDNN
  que faltan) o falla, se AVISA (`logger.warning`) y se cae a `elevenlabs`. **La app
  nunca se queda muda por un problema de DLLs** — responde al riesgo del `PLAN.md`.
- **`faster-whisper` como dependencia OPCIONAL** (extra `stt-local`), import perezoso:
  un `uv sync` normal queda ligero y usa la nube; quien quiera STT local hace
  `uv sync --extra stt-local` + las DLLs (ver README). Coherente con "backend ligero".
- **Default de código `elevenlabs`** (un clon limpio arranca **sin CUDA**); `local` es la
  **config recomendada** (privacidad), que se activa en caliente desde el menú o el `.env`.
  Mismo criterio que `RERANKER=off` (H4) y `LLM_PROVIDER=replicate` (H5): el default
  reproduce la línea base.
- **Groq** (Whisper en la nube, endpoint openai-compatible) se añade como tercer
  proveedor para la comparativa WER (candidato de latencia), con su propia clave
  (`GROQ_API_KEY`).

## Medición — WER (a completar en la máquina del usuario)

`evals/stt.py` mide **WER** (Word Error Rate) sobre ~20 clips reales, preferiblemente de
**voces infantiles** (doc H7 §3), contra una transcripción hecha a mano. El WER se calcula
sobre texto normalizado (minúsculas, sin puntuación, acentos conservados) para no medir la
puntuación que cada ASR inventa distinto. Pegar aquí la tabla que saca el runner:

| Proveedor | WER medio ± σ | latencia mediana (ms) | latencia máx (ms) | ¿la voz sale del PC? |
|---|---|---|---|---|
| local (faster-whisper `large-v3-turbo` int8) | | | | **no** |
| elevenlabs (Scribe) | | | | sí |
| groq (whisper-large-v3) | | | | sí |

**Nota esperada:** todos los ASR **suben el WER con voces infantiles** — por eso, además
de elegir el mejor, se añade el **paso de confirmación** en la UI (§ siguiente).

## Confirmación en la interfaz

Como todos los ASR fallan con voces infantiles, la transcripción **ya no se auto-envía**:
el texto entra en el input (editable) y aparece un **"¿has dicho esto?"** con
confirmar/repetir antes de mandar a `/api/ask`. Es más barato confirmar que responder a la
pregunta equivocada, y es buena pedagogía: el niño ve que la máquina le entendió.

## Consecuencias

- **Código:** `services/stt_service.py` (dispatch + fallback + singletons perezosos con
  firma), `voice_service.transcribir` delega, `secrets_service` gana el proveedor `groq`.
  `Chat.tsx`/`Chat.module.css` añaden el paso de confirmación. `evals/stt.py` (WER).
- **Dependencia:** `faster-whisper` como **extra opcional** (`stt-local`); el `uv sync`
  base no la instala (clon ligero). Clavada en `uv.lock`.
- **Configuración:** `STT_PROVIDER`/`STT_LOCAL_MODEL`/`STT_LOCAL_DEVICE`/`STT_LOCAL_COMPUTE`/
  `GROQ_STT_MODEL` (ajustes en caliente, categoría voz); `GROQ_API_KEY` (secreto, `.env`).
- **Instalación (Windows):** documentada paso a paso en el README (extra + DLLs de
  cuBLAS/cuDNN en el PATH). **Plan B** si no arranca en GPU tras medio día: `cpu`+`int8`
  (más lento pero funciona) o quedarse en nube — el fallback lo hace transparente.
- **Criterio del hito:** con `STT_PROVIDER=local`, `ELEVENLABS_API_KEY` deja de ser
  necesaria para transcribir (sigue haciendo falta para el TTS de la respuesta).
- **Privacidad (lo que se escribe en la memoria):** con STT local, la voz del niño no sale
  del PC. Es el eje del capítulo de RGPD, no una nota al pie.
