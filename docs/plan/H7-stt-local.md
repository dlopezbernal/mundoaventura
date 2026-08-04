# H7 — Transcripción local (STT)

- **Rama:** `feat/h7-stt-local`
- **Semana:** S5, días 1–2
- **Depende de:** H6 con OK
- **Prioridad que sirve:** #2, #3 y #4 — y sobre todo, privacidad

## Objetivo

Mover la transcripción de ElevenLabs Scribe a `faster-whisper` local en GPU.

## Por qué es el mejor cambio del proyecto

`large-v3-turbo` en int8 ocupa **~1–1,5 GB de VRAM**: con 6 GB sobran 4,5 GB.
Transcribe 5 segundos de audio en menos de un segundo, en español, gratis y sin
conexión.

Pero lo importante no es el coste ni la latencia: **la voz del niño deja de
salir del PC.** Para una app infantil española, ese es el argumento central del
capítulo de RGPD, no una nota al pie.

## Tareas

### 1. Instalación (el paso que va a doler)

**Aviso de Windows:** `faster-whisper` (CTranslate2) tiene ruedas para Windows y
funciona bien, pero **necesita las DLL de cuBLAS y cuDNN en el PATH**. Es donde
se pierde media tarde si no se espera.

- Documentar el procedimiento exacto en `README.md` (sección instalación).
- Si tras medio día no arranca en GPU: **plan B** = `int8` en CPU (más lento
  pero funciona) o mantener el STT en nube. Documentar la decisión, no insistir.

### 2. Abstracción de STT

Mismo patrón que H5 hizo con el LLM: `voice_service` expone `transcribir()` y
por debajo elige implementación según configuración.

- `STT_PROVIDER`: `local` | `elevenlabs` | `groq`.
- Modelo y tamaño configurables (`large-v3-turbo`, `medium`, `small`).
- **Fallback automático**: si el local falla al cargar, caer a nube y avisar por
  `logger.warning`. La app nunca se queda sin voz por un problema de DLLs.

### 3. Medición comparativa

Añadir al runner un modo de evaluación de STT:

- Grabar **20 clips de audio reales**, preferiblemente **con voces infantiles**
  (es el caso de uso, y es donde todos los ASR flojean).
- Transcribir con Scribe, con `faster-whisper` local y con Groq Whisper.
- Medir **WER** (tasa de error por palabra) contra una transcripción manual, y
  latencia.
- Tabla comparativa → ADR.

### 4. Confirmación en la interfaz

Todos los ASR degradan bastante con voces infantiles. Añadir un paso de
confirmación en el frontend: mostrar el texto transcrito y un *"¿has dicho
esto?"* antes de enviar a `/api/ask`.

Es más barato confirmar que responder a la pregunta equivocada, y además es
buena pedagogía: el niño ve que la máquina le ha entendido.

## Criterios de aceptación (puerta)

- [ ] `faster-whisper` transcribe en GPU, con el procedimiento de instalación
      documentado paso a paso para Windows.
- [ ] Tabla WER + latencia de los tres proveedores sobre los 20 clips.
- [ ] Fallback a nube funciona (probado desconfigurando el local a propósito).
- [ ] `ELEVENLABS_API_KEY` deja de ser necesaria para la transcripción.
- [ ] El paso de confirmación está en la interfaz.
- [ ] ADR escrito.

## Evidencia a entregar para el OK

1. Tabla WER/latencia.
2. Vídeo o captura del flujo de voz completo funcionando en local.
3. Informe de hito.

## Instrucción de arranque para Claude Code

> Lee `docs/PLAN.md` y `docs/plan/H7-stt-local.md`. Empieza por la instalación y
> **documenta cada paso que hagas en Windows** — va al README. Si a media
> jornada no arranca en GPU, para y aplica el plan B de §1 en vez de insistir.
> Dame el plan antes de escribir código.
