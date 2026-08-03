# Verificación H7 — faster-whisper en GPU (STT local)

Verificación en la máquina del usuario de la ruta de STT local (Hito 7, faster-whisper /
CTranslate2, **sin torch**), cuyo objetivo de privacidad es que **la voz del niño no salga
del PC**. Ver [ADR-008](../decisiones/ADR-008-stt-local.md).

## Entorno

- **GPU:** NVIDIA GeForce GTX 1660, 6 GB VRAM, driver 591.86 (Turing, soporta CUDA 12).
- **Config STT local:** modelo `large-v3-turbo`, device `cuda`, compute `int8`.
- **faster-whisper** 1.2.1 · **ctranslate2** 4.8.1 (extra `stt-local`).
- **Fecha:** 2026-08-03.

## Método

Clip de referencia sintetizado con ElevenLabs (texto conocido) y transcrito por tres vías:
directamente en GPU, directamente en CPU (control) y por la **ruta de producción**
(`stt_service.transcribir` con `STT_PROVIDER=local`, que incluye el fallback).

## Resultados

| Ruta | Resultado | Tiempo | WER (1 clip, indicativo) |
|---|---|---|---|
| **GPU (cuda/int8)** | ❌ **Falla**: `Library cublas64_12.dll is not found or cannot be loaded` | — | — |
| **CPU (int8)** | ✅ Transcribe correcto | carga 4,9 s + transcripción **8,2 s** | 0 % |
| **Producción (`local`)** | ✅ Intenta GPU → falla → **avisa y cae a ElevenLabs** | — | — (nube) |

Transcripción CPU del clip `"hola tirano rex por qué tienes los brazos tan pequeños"` →
`"Hola, Tirano Rex. ¿Por qué tienes los brazos tan pequeños?"` (perfecta).

## Conclusiones

1. **El riesgo previsto en el PLAN/CLAUDE.md se confirma:** en Windows, la ruta CUDA de
   CTranslate2 necesita las **DLLs de cuBLAS/cuDNN de CUDA 12** (`cublas64_12.dll` y
   compañía), que **no vienen** ni con el driver ni con el paquete `pip`. Sin ellas, la GPU
   no arranca.
2. **La resiliencia funciona (verificado en vivo):** `stt_service` detecta el fallo,
   registra un `logger.warning` y **transcribe con ElevenLabs**. La app **nunca se queda
   muda**; el fallback es transparente.
3. **CPU funciona pero es lento** (~8 s por un clip corto con `large-v3-turbo`): usable como
   respaldo, no ideal para que un niño espere. Para STT local ágil hace falta la GPU.
4. **El default `elevenlabs` (nube) es la decisión correcta de arranque:** un clon del repo
   funciona sin CUDA; el STT local es una mejora **opcional** de privacidad para quien
   complete el setup de GPU.

## Cómo habilitar la GPU (pendiente, opcional)

Para que la GPU funcione en esta máquina, faltan las librerías CUDA 12. Opciones:

- Instalar los wheels `nvidia-cublas-cu12` y `nvidia-cudnn-cu12` (~1 GB) y asegurar que sus
  carpetas `bin` estén en el `PATH` (o junto al `.dll` de ctranslate2).
- O instalar el **CUDA Toolkit 12** + **cuDNN 9** del sistema.

Con las DLLs presentes, `STT_LOCAL_DEVICE=cuda` debería dar transcripción **sub-segundo**.
Se decidió **no** instalarlas ahora (descarga pesada; la nube cubre el caso por defecto).

## Tabla de WER por proveedor — MEJORA FUTURA (fuera del scope de entrega)

La comparativa de WER (elevenlabs vs local vs groq) del doc H7 §3 se declara **mejora
futura** y **NO entra en el scope de entrega del proyecto**: exige un dataset de audio que
no existe en el repo. `evals/stt_clips/manifest.yaml` está **vacío** a propósito y necesita
**~20 clips reales, idealmente con voces infantiles** (donde todos los ASR flojean), que
solo puede grabar el usuario. La infraestructura ya está lista —el arnés `evals/stt.py`
consume el manifest en cuanto existan los clips—, así que la mejora es "grabar y ejecutar",
sin código nuevo. La decisión de STT (ADR-008) y la verificación de este documento no
dependen de esa tabla.
