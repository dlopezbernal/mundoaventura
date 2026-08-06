# ADR-008 — Transcripción local (STT) con faster-whisper + proveedor seleccionable

- **Estado:** aceptada — abstracción y fallback implementados y verdes, y
  **verificados en la máquina del usuario el 2026-08-03**
  ([`mediciones/H7-stt-gpu.md`](../mediciones/H7-stt-gpu.md)). La tabla WER queda
  **fuera del alcance de la entrega**, no por falta de GPU sino porque exige grabar
  ~20 clips con voces infantiles que no existen en el repositorio (ver "Medición").
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

## Verificación en GPU (hecha: 2026-08-03)

Informe completo: [`mediciones/H7-stt-gpu.md`](../mediciones/H7-stt-gpu.md). Máquina del
usuario: NVIDIA GTX 1660 (6 GB), faster-whisper 1.2.1 / ctranslate2 4.8.1, modelo
`large-v3-turbo` en int8.

| Ruta | Resultado |
|---|---|
| **GPU (`cuda`/int8)** | ❌ falla: `Library cublas64_12.dll is not found or cannot be loaded` |
| **CPU (int8)** | ✅ transcribe correcto (carga 4,9 s + transcripción 8,2 s) |
| **Producción (`STT_PROVIDER=local`)** | ✅ intenta GPU → falla → **avisa y cae a ElevenLabs** |

Dos conclusiones que sostienen esta decisión: (1) **el riesgo previsto se confirma** — en
Windows, la ruta CUDA de CTranslate2 necesita las DLLs de cuBLAS/cuDNN de CUDA 12, que no
vienen ni con el driver ni con el paquete `pip`; (2) **el fallback funciona, verificado en
vivo**: la app nunca se queda muda, que era justamente el criterio de aceptación. Y por eso
el **default `elevenlabs` es el correcto**: un clon del repositorio arranca sin CUDA.

## Medición — WER: fuera del alcance de la entrega

`evals/stt.py` mide **WER** (Word Error Rate) sobre texto normalizado (minúsculas, sin
puntuación, acentos conservados) para no medir la puntuación que cada ASR inventa distinto.
El arnés está **listo y consume `evals/stt_clips/manifest.yaml` en cuanto existan los clips**;
ese manifest está **vacío a propósito**.

La comparativa (local vs elevenlabs vs groq) se declara **mejora futura y fuera del alcance
de entrega**, y el motivo **no es la GPU** —el CPU transcribe bien y la ruta local se verificó
arriba—: es que exige un **dataset de ~20 clips reales, idealmente con voces infantiles**, que
no existe en el repositorio y que solo puede grabar el usuario. Es "grabar y ejecutar", sin
código nuevo. **Esta decisión no depende de esa tabla:** se toma por privacidad (la voz del
menor no sale del PC) y por reversibilidad, no por una diferencia de WER.

**Lo que sí se sabe sin la tabla:** todos los ASR **suben el WER con voces infantiles** — por
eso, además de poder elegir proveedor, se añadió un **paso de confirmación** en la UI, que
después se retiró (§ siguiente).

## Confirmación en la interfaz — añadida en H7 y RETIRADA el 2026-08-04

**Decisión original (H7).** Como todos los ASR fallan con voces infantiles, la transcripción
no se auto-enviaba: el texto entraba en el input (editable) y aparecía un **"¿has dicho
esto?"** con confirmar/repetir antes de mandar a `/api/ask`. El razonamiento era que es más
barato confirmar que responder a la pregunta equivocada.

> **Addendum (2026-08-04, commit `eb870b7`): revertido.** Probado con la app terminada, el paso
> intermedio pesaba más que el error que evitaba: rompía el ritmo justo en el momento más
> divertido para el niño, y obligaba a leer y pulsar antes de que le contestaran. Hoy
> `Chat.transcribirYEnviar` **envía el texto directamente**, igual que una pregunta escrita; si
> el ASR se equivoca queda el aviso "No te oí bien" y el niño repregunta, que a esta edad es más
> natural que corregir un campo de texto.
>
> **Lo que NO cambia con la reversión:** el argumento de esta decisión sigue en pie, porque el
> ADR-008 se decide por **privacidad y reversibilidad del proveedor** (§ Decisión), no por la
> UI. El WER alto con voces infantiles sigue siendo cierto y sigue sin tabla; lo que cambió es
> cómo se absorbe ese error en la interfaz.

## Consecuencias

- **Código:** `services/stt_service.py` (dispatch + fallback + singletons perezosos con
  firma), `voice_service.transcribir` delega, `secrets_service` gana el proveedor `groq`.
  `Chat.tsx` gestiona el micro y manda la transcripción al mismo flujo que una pregunta
  escrita (el paso de confirmación que añadió H7 se retiró después, ver arriba).
  `evals/stt.py` (WER).
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
