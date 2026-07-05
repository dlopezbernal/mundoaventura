# Diseño — Conversación por voz (ElevenLabs)

**Fecha:** 2026-07-05
**Estado:** Aprobado (pendiente de revisión final del usuario antes del plan de implementación)
**Fase del proyecto:** siguiente fase tras "Conversación por texto (RAG)"

---

## 1. Objetivo

Permitir que el niño (8–12 años) **haga preguntas por voz** y que el personaje **responda también por voz**, además del texto que ya existe hoy. Se completa así el pipeline anticipado en `backend/routers/_future_phases.py`.

Dos capacidades nuevas:

- **STT (voz → texto):** el niño graba su pregunta con el micrófono; se transcribe a español.
- **TTS (texto → voz):** la respuesta del personaje (español) se sintetiza con una voz expresiva y con carácter, distinta por personaje.

**Decisión de producto:** *todas* las respuestas se hablan (tanto si la pregunta se escribió como si se dijo por voz) y se **auto-reproducen** en cuanto aparece la burbuja de respuesta.

---

## 2. Proveedor: ElevenLabs (Scribe + Flash)

ElevenLabs entra como **tercer proveedor** junto a Replicate (imagen + LLM) y DeepL (traducción), con una única API key nueva.

- **STT:** ElevenLabs **Scribe** (`scribe_v1`), idioma `es`.
- **TTS:** ElevenLabs **Flash** (`eleven_flash_v2_5`), ~0,05 $/1K caracteres.
- **Modalidad:** pago por uso (pay-as-you-go), sin free tier, para no toparse con cuotas en desarrollo ni en la demo.
- **Voz por personaje:** cada `personaje_id` tiene una `voz_id` de ElevenLabs específica y con carácter (p. ej. Sherlock Holmes grave y pausado; Da Vinci cálido y sabio).

### Por qué ElevenLabs y no Whisper/Replicate (decisión de diseño)

El placeholder original (`_future_phases.py`) preveía Whisper vía Replicate solo para STT. Se elige ElevenLabs para **STT + TTS** porque:

- La calidad de **voz expresiva en español** para dar carácter a cada personaje es netamente superior a los TTS disponibles en Replicate.
- Un único proveedor cubre las dos mitades (STT y TTS) con una sola key y un SDK.
- El modelo Flash tiene latencia baja, importante para que un niño no espere.

**Contrapartida asumida:** un proveedor y un coste más. Se mitiga con degradación elegante (ver §6) para que un fallo de voz nunca rompa el chat de texto.

---

## 3. Arquitectura y flujo de datos

Se mantiene el patrón actual: **routers finos → services → config**, "todo lo pesado en la nube", backend sin torch/CUDA.

### Enfoque elegido (Opción A): TTS acoplado a `/api/ask` + endpoint aparte para STT

- **STT** es una unidad aislada (`POST /api/transcribe`), invocada **solo** en el flujo de voz.
- **TTS** viaja **acoplado a la respuesta** de `/api/ask`, porque *toda* respuesta se habla. Así el audio acompaña a cualquier respuesta, venga de una pregunta hablada o escrita.
- `/api/ask` sigue siendo la **puerta única del chat**; su lógica RAG (DeepL → retrieval → Evaluator → LLM) **no se toca**.

### Flujo — pregunta hablada

```
[Niño toca 🎤]  Flet AudioRecorder graba (tap start / tap stop)
      │  audio (archivo temporal)
      ▼
POST /api/transcribe (multipart)
      │  ElevenLabs Scribe (idioma: es) → texto en español
      ▼
[Frontend pinta burbuja 🧒 con el texto transcrito]
      ▼
POST /api/ask  { personaje_id, pregunta }        ← flujo RAG existente, INTACTO
      │  1) DeepL ES→EN  2) retrieval  3) Evaluator  4) LLM → respuesta ES
      │  5) NUEVO: TTS ElevenLabs Flash con la voz_id del personaje → audio_base64
      ▼
{ respuesta, audio_base64, origen, ... }
      ▼
[Frontend pinta burbuja del personaje + auto-play del audio]
```

### Flujo — pregunta escrita

Idéntico saltando `/api/transcribe`: el niño escribe → `/api/ask` → la respuesta vuelve con `audio_base64` y suena. **Un solo viaje.**

### Contrato de datos

- `POST /api/transcribe` — multipart, campo `audio` (archivo). Respuesta: `{ "texto": "<transcripción en español>" }`.
- `POST /api/ask` — sin cambios de entrada. La respuesta añade un campo nuevo:
  `audio_base64: <string mp3 en base64 | null>` (null si el personaje no tiene voz o si el TTS falló).

---

## 4. Componentes del backend

### 4.1 `config.py` — nuevos tunables (desde `.env`)

| Variable | Por defecto | Uso |
|----------|-------------|-----|
| `ELEVENLABS_API_KEY` | (vacío) | Obligatoria para voz. Sin ella: voz desactivada, chat de texto intacto. |
| `ELEVENLABS_STT_MODEL` | `scribe_v1` | Modelo de transcripción. |
| `ELEVENLABS_TTS_MODEL` | `eleven_flash_v2_5` | Modelo de síntesis. |
| `TTS_OUTPUT_FORMAT` | `mp3_44100_128` | Formato del audio devuelto. |
| `STT_LANG` | `es` | Idioma de la transcripción. |

`describe()` añade `elevenlabs_configurado: bool` para verlo en `/health`.

### 4.2 `backend/personajes.py` — `voz_id` por personaje

Se añade un dict `VOCES` paralelo a `NOMBRES`/`PROMPTS`, siguiendo el estilo actual (un dict por concepto):

```python
VOCES = {
    "sherlock":  "<voz_id grave y pausada>",
    "davinci":   "<voz_id cálida y sabia>",
    "t-rex":     "<voz_id juguetona>",
    # ... una por personaje_id que hable
}
```

La `voz_id` pasa a ser el **5º sitio** del invariante `personaje_id` (para personajes que hablan). Un personaje sin entrada en `VOCES` responde solo en texto (no rompe).

### 4.3 `backend/services/voice_service.py` — módulo nuevo

Un proveedor (ElevenLabs), tres funciones con interfaz limpia:

- `transcribir(audio_bytes, filename) -> str` — Scribe, idioma `STT_LANG`. Lanza `VoiceError(ValueError)` si falla o falta la key.
- `sintetizar(texto, voz_id) -> bytes` — Flash con esa voz. Devuelve mp3 en bytes.
- `estado() -> dict` — para `/health` (key presente / alcanzable), como hace `translation_service`.

### 4.4 `backend/routers/transcription.py` — router fino nuevo

Reemplaza el placeholder `_future_phases.py`. `POST /api/transcribe` (multipart `audio`) → `{ "texto": "..." }`. Mapea `ValueError`→400, resto→500. Se enchufa en `main.py`.

### 4.5 `routers/conversacion.py` + `rag_service.py` — TTS acoplado

Tras generar `respuesta` (español), si el personaje tiene `voz_id` y hay key, `rag_service` llama a `voice_service.sintetizar(respuesta, voz_id)`, codifica el mp3 a base64 y lo añade como `audio_base64` al dict de retorno. Ver degradación en §6.

### 4.6 Dependencias y arranque

- `requirements-backend.txt`: `elevenlabs` (SDK oficial).
- Hook de startup en `main.py`: avisa si falta `ELEVENLABS_API_KEY` (no bloquea el server, igual que con DeepL).

---

## 5. Componentes del frontend (Flet)

### 5.1 Dependencia nueva

`flet-audio` en `requirements-frontend.txt` (aporta `Audio` para reproducir y `AudioRecorder` para grabar).

> ⚠️ **Riesgo a validar pronto (spike):** que `AudioRecorder` grabe micrófono en **Windows escritorio** con Flet 0.28.3. Si diera problemas, fallback a grabación vía `sounddevice`. Este spike es la primera tarea del plan de implementación.

### 5.2 UI del chat (`frontend/main.py`)

1. **Botón de micrófono 🎤** junto al campo de texto y el botón enviar. Estados:
   - Reposo → icono micro.
   - Tocar → `AudioRecorder.start_recording()`, el icono cambia a "⏹ grabando…" (color/animación).
   - Tocar de nuevo → `stop_recording()`, se obtiene el archivo temporal; el botón se deshabilita mientras transcribe.

2. **Al parar de grabar** (asíncrono en un `threading.Thread(daemon=True)`, como `_run_ask`/`_run_generate` hoy):
   - `api_client.transcribe(audio_path)` → texto.
   - Pinta burbuja 🧒 con el texto transcrito.
   - `api_client.ask(...)` → `{respuesta, audio_base64}`.
   - Pinta burbuja del personaje **y** reproduce el audio.

3. **Reproducción auto (no bloqueante):** un control `Audio` con `autoplay=True`; se le asigna `src_base64 = audio_base64` y se reproduce al pintar la burbuja. La reproducción de Flet es asíncrona (no bloquea el hilo principal). Texto y audio arrancan a la vez.

4. **El campo de texto sigue funcionando**: escribir una pregunta también devuelve `audio_base64` y suena.

### 5.3 `frontend/api_client.py`

- `transcribe(audio_path) -> str`: multipart a `/api/transcribe`, errores → `BackendError` (patrón idéntico a `generate_on_photo`).
- `ask(...)`: sin cambio de firma; solo se aprovecha el nuevo campo `audio_base64`.

---

## 6. Manejo de errores (degradación elegante)

| Caso | Comportamiento |
|------|----------------|
| Falta `ELEVENLABS_API_KEY` | `/health` lo avisa; `/api/transcribe`→400; `/api/ask` responde solo texto (`audio_base64: null`). |
| Scribe falla | `/api/transcribe`→400 con mensaje claro (sin transcripción no hay pregunta). |
| TTS falla | Respuesta de texto **intacta**, `audio_base64: null`, warning en consola. |
| Personaje sin `voz_id` | Respuesta solo texto (no rompe). |

**Principio:** un fallo de voz **nunca** rompe el chat de texto.

---

## 7. Modo DEBUG (consola del backend)

Reutiliza el patrón de `debug_log.py` / `[CHAT]`. Nuevas trazas condicionadas a `config.DEBUG` (coste cero en producción):

- **STT:** `[VOZ] 🎙️ STT · <n> bytes → "<texto transcrito>"`.
- **TTS:** `[VOZ] 🔊 TTS · voz=<voz_id> · <n> chars · <personaje_id>` (el nº de caracteres controla coste).
- **Fallo TTS:** `[VOZ] ⚠️ TTS falló: <motivo> (respuesta va solo en texto)`.

Toda la traza de voz vive en la **consola del backend**, no en el frontend (coherente con las trazas actuales).

---

## 8. Documentación a actualizar

### `README.md`
- Tabla del pipeline: "Entrada por voz" → **ElevenLabs Scribe ✅**; nueva fila **"Respuesta por voz — ElevenLabs Flash (TTS) ✅"**.
- Diagrama de arquitectura: añadir `/api/transcribe` y el `audio_base64` en la respuesta de `/api/ask`.
- Estructura de archivos: `voice_service.py`, `routers/transcription.py`, `VOCES` en `personajes.py`.
- Puesta en marcha §3: `ELEVENLABS_API_KEY` como obligatoria para voz (enlace + nota de pago por uso).
- Sección DEBUG: documentar las nuevas trazas `[VOZ]`.
- "Decisiones de diseño": nueva entrada **"6. Voz con ElevenLabs (Scribe + Flash), pago por uso"**.
- "Personalizar": cómo asignar `voz_id` a un personaje nuevo.

### `.env.example`
Añadir `ELEVENLABS_API_KEY=`, `ELEVENLABS_STT_MODEL=scribe_v1`, `ELEVENLABS_TTS_MODEL=eleven_flash_v2_5`, `TTS_OUTPUT_FORMAT=mp3_44100_128`, `STT_LANG=es`.

### `CLAUDE.md`
El invariante `personaje_id` pasa a mencionar `VOCES`/`voz_id`; añadir el endpoint `/api/transcribe` y el flujo de voz; mencionar ElevenLabs como tercer proveedor.

### `ARQUITECTURA.md` (nuevo, raíz del repo)
Documento único y visual del pipeline completo (imagen + RAG + voz), con diagrama de secuencia de los tres proveedores (Replicate, DeepL, ElevenLabs). Pensado como material para la **memoria final del capstone**. El README queda como guía de uso; `ARQUITECTURA.md` como referencia técnica de conjunto.

---

## 9. Verificación (manual — el proyecto no tiene test suite)

- `GET /health` muestra `elevenlabs_configurado: true`.
- **Spike temprano** del `AudioRecorder` en Windows escritorio.
- **End-to-end por la UI:** hablar → transcripción correcta → respuesta suena con la voz del personaje; y pregunta escrita → también suena.
- **Degradación:** sin `ELEVENLABS_API_KEY`, el chat de texto sigue funcionando (respuestas sin audio).
- Con `DEBUG=true`, las trazas `[VOZ]` aparecen en la consola del backend.

---

## 10. Fuera de alcance (YAGNI)

- Voz en la fase de selección de escena o en cualquier pantalla que no sea el chat.
- Detección automática de fin de habla (VAD) / manos libres: se usa tap-to-start / tap-to-stop explícito.
- Streaming de audio token a token: se sintetiza la respuesta completa y se reproduce.
- Cacheo de audios de respuestas repetidas.
- Selección de voz por el usuario: la `voz_id` la fija el backend por personaje.
