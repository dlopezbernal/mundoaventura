# Conversación por voz (ElevenLabs) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir entrada por voz (el niño pregunta hablando) y salida por voz (el personaje responde también en audio) al chat, usando ElevenLabs.

**Architecture:** Se mantiene el patrón routers finos → services → config. STT vive en un endpoint aislado (`POST /api/transcribe`); TTS viaja acoplado a la respuesta de `/api/ask` (`audio_base64`), porque toda respuesta se habla. El frontend Flet graba con `AudioRecorder` (tap start/stop) y reproduce con `Audio`, ambos de `flet-audio`, sin bloquear el hilo principal.

**Tech Stack:** FastAPI, Flet 0.28.3 + flet-audio, ElevenLabs Python SDK (Scribe STT + Flash TTS), Python 3.12.

## Global Constraints

- **Idioma del código:** comentarios, docstrings y textos en **español** (coincide con el resto del repo).
- **Backend ligero:** NO añadir torch/CUDA ni modelos locales; ElevenLabs es una llamada HTTP más.
- **Modelos exactos:** STT `scribe_v1`, TTS `eleven_flash_v2_5`, formato de audio `mp3_44100_128`, idioma STT `es`. Pago por uso (sin free tier).
- **Invariante `personaje_id`:** debe coincidir en `backend/personajes.py` (`PROMPTS`+`NOMBRES`+**`VOCES`**), `frontend/personajes.py`, y `backend/documentos/<personaje_id>/`. `voz_id` es el 5º sitio (solo para personajes que hablan).
- **Degradación:** un fallo de voz **nunca** rompe la respuesta de texto (`audio_base64: null`).
- **DEBUG:** todas las trazas de voz (`[VOZ]`) van a la **consola del backend**, solo si `config.DEBUG`.
- **Sin test suite:** el proyecto se verifica **manualmente** (CLAUDE.md). Cada tarea termina con comandos de verificación concretos y su salida esperada, no con pytest.
- **`personaje_id` reales:** `triceratops`, `t-rex`, `leonardo_da_vinci`, `sherlock_holmes`, `peter_pan`.
- **Scratchpad para ficheros temporales:** `C:\Users\dlope\AppData\Local\Temp\claude\D--DEV-repo-vs-capston\f2b8a075-2c42-4af0-a831-f696f1b2f4e3\scratchpad` (los scripts de smoke NO se comitean).

---

### Task 1: Configuración de ElevenLabs (config + .env.example + dependencia)

**Files:**
- Modify: `.env.example`
- Modify: `backend/config.py` (tras la sección 3, antes de la sección 4 "Modo desarrollo", ~línea 138)
- Modify: `requirements-backend.txt`

**Interfaces:**
- Produces: `config.ELEVENLABS_API_KEY: str`, `config.ELEVENLABS_STT_MODEL: str`, `config.ELEVENLABS_TTS_MODEL: str`, `config.TTS_OUTPUT_FORMAT: str`, `config.STT_LANG: str`.

- [ ] **Step 1: Añadir la dependencia del SDK**

En `requirements-backend.txt`, tras la línea `deepl` (dentro del bloque "Conversación / RAG"), añade:

```
elevenlabs                # Cliente de ElevenLabs: transcripción (Scribe/STT) y síntesis de voz (Flash/TTS)
```

- [ ] **Step 2: Instalar la dependencia**

Run:
```powershell
.\.venv\Scripts\Activate.ps1
pip install elevenlabs
```
Expected: `Successfully installed elevenlabs-...`

- [ ] **Step 3: Añadir los tunables en `backend/config.py`**

Inserta este bloque justo **antes** de `def _leer_bool(` (línea ~140):

```python
# ---------------------------------------------------------------------------
# 3b) Voz (ElevenLabs): transcripción (Scribe/STT) + síntesis (Flash/TTS)
# ---------------------------------------------------------------------------
# ElevenLabs es el TERCER proveedor (junto a Replicate y DeepL). Una sola clave
# cubre las dos mitades: transcribir la pregunta hablada del niño (Scribe) y dar
# voz a la respuesta del personaje (Flash). Modalidad pago por uso.
# Sin esta clave, la voz queda desactivada pero el chat de TEXTO sigue funcionando.
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "").strip()

# Modelo de transcripción (voz → texto). Scribe entiende bien el español.
ELEVENLABS_STT_MODEL: str = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v1").strip()

# Modelo de síntesis (texto → voz). Flash: baja latencia y barato (~0,05 $/1K chars).
ELEVENLABS_TTS_MODEL: str = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5").strip()

# Formato del audio devuelto por el TTS (mp3, reproducible por Flet en base64).
TTS_OUTPUT_FORMAT: str = os.getenv("TTS_OUTPUT_FORMAT", "mp3_44100_128").strip()

# Idioma de la transcripción (la pregunta del niño se dice en español).
STT_LANG: str = os.getenv("STT_LANG", "es").strip()
```

- [ ] **Step 4: Añadir las variables a `.env.example`**

Tras el bloque de DeepL / ChromaDB en `.env.example`, y antes del bloque `─── DESARROLLO ───`, añade:

```
# ─── BACKEND (Voz / ElevenLabs) ─────────────────────────────────────
# Clave de ElevenLabs para transcribir la voz del niño (Scribe) y dar voz a la
# respuesta del personaje (Flash). Pago por uso. https://elevenlabs.io
ELEVENLABS_API_KEY=
# Modelos (no suele hacer falta cambiarlos).
ELEVENLABS_STT_MODEL=scribe_v1
ELEVENLABS_TTS_MODEL=eleven_flash_v2_5
# Formato del audio de la respuesta (mp3) e idioma de la transcripción.
TTS_OUTPUT_FORMAT=mp3_44100_128
STT_LANG=es
```

- [ ] **Step 5: Verificar que la config carga**

Run:
```powershell
python -c "from backend import config; print(config.ELEVENLABS_STT_MODEL, config.ELEVENLABS_TTS_MODEL, config.TTS_OUTPUT_FORMAT, config.STT_LANG)"
```
Expected: `scribe_v1 eleven_flash_v2_5 mp3_44100_128 es`

- [ ] **Step 6: Commit**

```powershell
git add requirements-backend.txt backend/config.py .env.example
git commit -m "feat(voz): configuracion de ElevenLabs (STT Scribe + TTS Flash)"
```

---

### Task 2: Servicio de voz (`voice_service.py`)

**Files:**
- Create: `backend/services/voice_service.py`

**Interfaces:**
- Consumes: `config.ELEVENLABS_API_KEY`, `config.ELEVENLABS_STT_MODEL`, `config.ELEVENLABS_TTS_MODEL`, `config.TTS_OUTPUT_FORMAT`, `config.STT_LANG`, `config.DEBUG` (Task 1).
- Produces:
  - `VoiceError(ValueError)`
  - `transcribir(audio_bytes: bytes, filename: str = "audio.mp3") -> str`
  - `sintetizar(texto: str, voz_id: str) -> bytes`
  - `estado() -> dict` con claves `elevenlabs_ok: bool`, `elevenlabs_mensaje: str`.

- [ ] **Step 1: Crear el módulo**

Crea `backend/services/voice_service.py` con este contenido:

```python
"""
services/voice_service.py — Voz con ElevenLabs (STT Scribe + TTS Flash)
=======================================================================

Dos mitades, un solo proveedor y una sola clave (ELEVENLABS_API_KEY):

  - transcribir(...)  voz del niño (bytes de audio) → texto en español  (Scribe)
  - sintetizar(...)   texto de la respuesta → audio mp3 (bytes)          (Flash)

Igual que translation_service (DeepL), la clave se valida de forma perezosa y los
errores se lanzan como VoiceError (subclase de ValueError) para que el router los
devuelva como HTTP 400 con un mensaje claro, en vez de un 500 genérico.
"""

import io

from elevenlabs.client import ElevenLabs

from backend import config


class VoiceError(ValueError):
    """Error de voz: ElevenLabs no configurado, o fallo en STT/TTS.

    Hereda de ValueError para que el router lo devuelva como 400.
    """


# Cliente de ElevenLabs, creado una sola vez (singleton perezoso).
_client: ElevenLabs | None = None


def _get_client() -> ElevenLabs:
    """Devuelve el cliente de ElevenLabs, o lanza VoiceError si falta la clave."""
    global _client
    if _client is not None:
        return _client
    if not config.ELEVENLABS_API_KEY:
        raise VoiceError(
            "Falta ELEVENLABS_API_KEY en el .env. La voz (transcripción y síntesis) "
            "la provee ElevenLabs. Consigue una clave en https://elevenlabs.io y "
            "añádela al .env."
        )
    _client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
    return _client


def transcribir(audio_bytes: bytes, filename: str = "audio.mp3") -> str:
    """Transcribe audio (bytes) a texto en español con ElevenLabs Scribe.

    Lanza VoiceError si falta la clave o falla la transcripción.
    """
    client = _get_client()
    try:
        resultado = client.speech_to_text.convert(
            file=io.BytesIO(audio_bytes),
            model_id=config.ELEVENLABS_STT_MODEL,
            language_code=config.STT_LANG,
        )
        texto = (resultado.text or "").strip()
    except Exception as exc:
        raise VoiceError(f"Error al transcribir con ElevenLabs: {exc}")

    if config.DEBUG:
        print(f'[VOZ] 🎙️ STT · {len(audio_bytes)} bytes → "{texto}"')
    return texto


def sintetizar(texto: str, voz_id: str) -> bytes:
    """Sintetiza `texto` a audio mp3 (bytes) con la voz `voz_id` (ElevenLabs Flash).

    Lanza VoiceError si falta la clave o falla la síntesis.
    """
    client = _get_client()
    try:
        stream = client.text_to_speech.convert(
            voice_id=voz_id,
            model_id=config.ELEVENLABS_TTS_MODEL,
            text=texto,
            output_format=config.TTS_OUTPUT_FORMAT,
        )
        # convert() devuelve un iterador de trozos de bytes: los unimos.
        return b"".join(stream)
    except Exception as exc:
        raise VoiceError(f"Error al sintetizar con ElevenLabs: {exc}")


def estado() -> dict:
    """Estado de ElevenLabs SIN lanzar excepción (para /health y arranque).

    Comprueba solo que la clave esté presente (no hace llamada de red, para no
    gastar cuota en cada /health).
    """
    if not config.ELEVENLABS_API_KEY:
        return {
            "elevenlabs_ok": False,
            "elevenlabs_mensaje": "Falta ELEVENLABS_API_KEY (voz desactivada).",
        }
    return {"elevenlabs_ok": True, "elevenlabs_mensaje": "ElevenLabs configurado."}
```

- [ ] **Step 2: Smoke test de ida y vuelta (TTS → STT)**

> Requiere `ELEVENLABS_API_KEY` real en `.env` (consume una pizca de cuota). Si aún no tienes clave, salta al Step 4 y verifica solo `estado()`.

Crea un script temporal en el scratchpad `smoke_voz.py`:

```python
from backend.services import voice_service

# TTS: sintetiza una frase corta con una voz premade.
mp3 = voice_service.sintetizar("Hola, soy una prueba de voz.", "onwK4e9ZLuTAKqWW03F9")
print("TTS bytes:", len(mp3))
assert len(mp3) > 1000, "El mp3 salió sospechosamente pequeño"

# STT: transcribe ese mismo audio y comprueba que reconoce algo.
texto = voice_service.transcribir(mp3, "prueba.mp3")
print("STT texto:", repr(texto))
assert texto.strip(), "La transcripción vino vacía"
print("OK")
```

Run:
```powershell
python "C:\Users\dlope\AppData\Local\Temp\claude\D--DEV-repo-vs-capston\f2b8a075-2c42-4af0-a831-f696f1b2f4e3\scratchpad\smoke_voz.py"
```
Expected: `TTS bytes: <número grande>`, `STT texto: '...prueba...'`, `OK`.

- [ ] **Step 3: Verificar la traza DEBUG**

Con `DEBUG=true` en `.env`, re-ejecuta el script del Step 2.
Expected: aparece en consola `[VOZ] 🎙️ STT · <n> bytes → "..."`.

- [ ] **Step 4: Verificar `estado()` sin clave**

Run:
```powershell
python -c "import os; os.environ.pop('ELEVENLABS_API_KEY', None); from backend import config; config.ELEVENLABS_API_KEY=''; from backend.services import voice_service; print(voice_service.estado())"
```
Expected: `{'elevenlabs_ok': False, 'elevenlabs_mensaje': 'Falta ELEVENLABS_API_KEY (voz desactivada).'}`

- [ ] **Step 5: Commit**

```powershell
git add backend/services/voice_service.py
git commit -m "feat(voz): servicio ElevenLabs (transcribir/sintetizar/estado)"
```

---

### Task 3: Endpoint `POST /api/transcribe` + arranque y /health

**Files:**
- Create: `backend/routers/transcription.py`
- Delete: `backend/routers/_future_phases.py`
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `voice_service.transcribir`, `voice_service.estado` (Task 2).
- Produces: `POST /api/transcribe` (multipart `audio`) → `{"texto": str}`. `/health` incluye `elevenlabs_ok`.

- [ ] **Step 1: Crear el router**

Crea `backend/routers/transcription.py`:

```python
"""
routers/transcription.py — Endpoint de transcripción de voz (STT)
=================================================================

Una puerta de entrada (la lógica vive en services/voice_service.py):

  POST /api/transcribe → el niño sube el audio de su pregunta (multipart) y
                         recibe el texto transcrito en español (ElevenLabs
                         Scribe), listo para enviarse a /api/ask.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services import voice_service

router = APIRouter(prefix="/api", tags=["Transcripción (voz)"])


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Transcribe el audio de la pregunta del niño a texto en español."""
    try:
        audio_bytes = await audio.read()
        texto = voice_service.transcribir(audio_bytes, audio.filename or "audio.mp3")
    except ValueError as exc:
        # Falta la clave o el audio no se pudo transcribir -> 400.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error al transcribir: {exc}"
        ) from exc

    return {"texto": texto}
```

- [ ] **Step 2: Borrar el placeholder ya implementado**

```powershell
git rm backend/routers/_future_phases.py
```

- [ ] **Step 3: Enchufar el router en `main.py`**

En `backend/main.py`, línea 22, cambia el import:

```python
from backend.routers import conversacion, generation, transcription
```

Y en la sección "3) Enchufar los routers" (tras `app.include_router(conversacion.router)`, línea 67), añade:

```python
# Transcripción de voz (STT): la pregunta hablada del niño → texto (ElevenLabs Scribe).
app.include_router(transcription.router)
```

- [ ] **Step 4: Añadir voice_service al arranque y a /health**

En `backend/main.py`, línea 23, añade el import del servicio:

```python
from backend.services import translation_service, voice_service
```

En el hook `_verificar_dependencias` (tras el bloque de DeepL, antes de cerrar la función, ~línea 98), añade:

```python
    est_voz = voice_service.estado()
    if est_voz["elevenlabs_ok"]:
        print("[Arranque] ElevenLabs (voz) configurado. ✅")
    else:
        print("[Arranque] ⚠️  ElevenLabs NO configurado (voz desactivada):")
        print(f"[Arranque]     {est_voz['elevenlabs_mensaje']}")
```

En `health()` (línea 108), añade el estado de voz al dict devuelto:

```python
    return {
        "status": "ok",
        **config.describe(),
        **translation_service.estado(),
        **voice_service.estado(),
    }
```

- [ ] **Step 5: Verificar /health**

Arranca el backend en otra terminal (`uvicorn backend.main:app --reload`) y:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/health | Select-Object status, elevenlabs_ok
```
Expected: `status = ok`, `elevenlabs_ok = True` (si la clave está puesta). En la consola del backend: `[Arranque] ElevenLabs (voz) configurado. ✅`.

- [ ] **Step 6: Verificar /api/transcribe end-to-end**

Genera un mp3 de prueba (reutiliza el TTS) y transcríbelo por HTTP. Script temporal `smoke_transcribe.py` en scratchpad:

```python
from backend.services import voice_service
mp3 = voice_service.sintetizar("Qué comes tú.", "onwK4e9ZLuTAKqWW03F9")
open(r"C:\Users\dlope\AppData\Local\Temp\claude\D--DEV-repo-vs-capston\f2b8a075-2c42-4af0-a831-f696f1b2f4e3\scratchpad\pregunta.mp3", "wb").write(mp3)
print("mp3 escrito")
```
Run:
```powershell
python "C:\Users\dlope\AppData\Local\Temp\claude\D--DEV-repo-vs-capston\f2b8a075-2c42-4af0-a831-f696f1b2f4e3\scratchpad\smoke_transcribe.py"
curl.exe -s -F "audio=@C:\Users\dlope\AppData\Local\Temp\claude\D--DEV-repo-vs-capston\f2b8a075-2c42-4af0-a831-f696f1b2f4e3\scratchpad\pregunta.mp3" http://127.0.0.1:8000/api/transcribe
```
Expected: `{"texto":"Qué comes tú."}` (o texto muy parecido).

- [ ] **Step 7: Commit**

```powershell
git add backend/routers/transcription.py backend/main.py
git commit -m "feat(voz): endpoint POST /api/transcribe + arranque y /health"
```

---

### Task 4: Voz por personaje (`VOCES`) + TTS acoplado a `/api/ask`

**Files:**
- Modify: `backend/personajes.py` (tras `NOMBRES`, línea ~84)
- Modify: `backend/services/rag_service.py` (imports ~28-34; función `responder` ~321-387)
- Modify: `backend/schemas/conversacion.py` (`AskResponse`, tras `fuentes`, línea ~59)

**Interfaces:**
- Consumes: `voice_service.sintetizar` (Task 2), `personajes_cfg.VOCES`.
- Produces: `responder(...)` devuelve además `audio_base64: str | None`. `AskResponse.audio_base64`.

- [ ] **Step 1: Añadir el diccionario `VOCES`**

En `backend/personajes.py`, tras el dict `NOMBRES` (línea 84), añade:

```python
# voz_id de ElevenLabs con la que habla cada personaje en el chat (TTS Flash).
# Es el 5º sitio del invariante personaje_id: la clave debe coincidir con PROMPTS,
# NOMBRES, la carta del frontend y la carpeta backend/documentos/<personaje_id>/.
# Un personaje SIN entrada aquí responde solo en texto (no rompe).
# Los IDs de abajo son voces "premade" de ElevenLabs (funcionan out-of-the-box);
# sustitúyelos por voces en español con más carácter desde tu biblioteca de ElevenLabs.
VOCES = {
    "sherlock_holmes":   "onwK4e9ZLuTAKqWW03F9",  # grave y pausada (Daniel)
    "leonardo_da_vinci": "pNInz6obpgDQGcFmaJgB",  # cálida y sabia (Adam)
    "t-rex":             "IKne3meq5aSn9XLyUdCD",  # juguetona (Charlie)
    "triceratops":       "ErXwobaYiN019PkySvjV",  # amable (Antoni)
    "peter_pan":         "TxGEqnHWrfWFTfGW9XjX",  # aventurera y joven (Josh)
}
```

- [ ] **Step 2: Añadir el campo `audio_base64` al schema de salida**

En `backend/schemas/conversacion.py`, dentro de `AskResponse`, tras el campo `fuentes` (línea 59), añade:

```python
    audio_base64: str | None = Field(
        default=None,
        description="Respuesta del personaje sintetizada a voz (mp3 en base64), o "
        "null si el personaje no tiene voz o si el TTS falló (el texto no se rompe).",
    )
```

- [ ] **Step 3: Importar base64 y voice_service en `rag_service.py`**

En `backend/services/rag_service.py`, tras la línea `import replicate` (línea 29), añade:

```python
import base64
```

Y tras `from backend.services import translation_service` (línea 34), añade:

```python
from backend.services import voice_service
```

- [ ] **Step 4: Añadir el helper de síntesis con degradación**

En `backend/services/rag_service.py`, justo **antes** de `def responder(` (línea 321), añade:

```python
def _sintetizar_respuesta(personaje_id: str, respuesta: str) -> str | None:
    """Devuelve la respuesta como mp3 en base64, o None.

    Degradación elegante: si el personaje no tiene voz_id, si falta la clave de
    ElevenLabs, o si el TTS falla, devuelve None. El texto de la respuesta NUNCA
    se rompe por un fallo de voz.
    """
    voz_id = personajes_cfg.VOCES.get(personaje_id)
    if not voz_id or not config.ELEVENLABS_API_KEY:
        return None
    try:
        audio_bytes = voice_service.sintetizar(respuesta, voz_id)
    except Exception as exc:
        if config.DEBUG:
            print(f"[VOZ] ⚠️ TTS falló: {exc} (respuesta va solo en texto)")
        return None
    if config.DEBUG:
        print(f"[VOZ] 🔊 TTS · voz={voz_id} · {len(respuesta)} chars · {personaje_id}")
    return base64.b64encode(audio_bytes).decode("ascii")
```

- [ ] **Step 5: Llamar al helper y devolver `audio_base64` en `responder`**

En `responder`, tras la línea `_trazar_origen(origen, metodo, distancia, pregunta_en)` (línea 371), añade:

```python
    # Síntesis de voz de la respuesta (si el personaje tiene voz_id y hay clave).
    # Si falla, audio_base64 queda None y la respuesta sigue viva en texto.
    audio_base64 = _sintetizar_respuesta(personaje_id, respuesta)
```

Y en el `return { ... }` (líneas 373-387), añade la clave nueva antes de cerrar el dict (tras `"fuentes": fuentes,`):

```python
        "audio_base64": audio_base64,
```

- [ ] **Step 6: Verificar que `/api/ask` devuelve audio**

Con el backend arrancado (Task 3) e índice ChromaDB construido (`python -m backend.ingest`):
```powershell
$body = @{ personaje_id = "sherlock_holmes"; pregunta = "¿Dónde vives?" } | ConvertTo-Json
$r = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/ask -Method Post -Body $body -ContentType "application/json"
"respuesta: $($r.respuesta)"
"audio_base64 presente: $([bool]$r.audio_base64) (len=$($r.audio_base64.Length))"
```
Expected: `respuesta:` con texto en español; `audio_base64 presente: True` con longitud grande (miles de chars). En consola del backend: `[VOZ] 🔊 TTS · voz=onwK4e9ZLuTAKqWW03F9 · <n> chars · sherlock_holmes`.

- [ ] **Step 7: Verificar la degradación (sin clave → solo texto)**

Comenta temporalmente `ELEVENLABS_API_KEY` en `.env`, reinicia el backend y repite el comando del Step 6.
Expected: `respuesta:` con texto; `audio_base64 presente: False`. El chat de texto sigue funcionando. (Vuelve a poner la clave después.)

- [ ] **Step 8: Commit**

```powershell
git add backend/personajes.py backend/schemas/conversacion.py backend/services/rag_service.py
git commit -m "feat(voz): voz por personaje (VOCES) + audio_base64 en /api/ask"
```

---

### Task 5: Spike — validar grabación de micrófono con flet-audio en Windows

**Files:**
- Modify: `requirements-frontend.txt`
- Create (throwaway, NO se comitea): `frontend/_spike_recorder.py`

**Interfaces:**
- Produces: decisión GO/NO-GO sobre `flet_audio.AudioRecorder` en Windows escritorio. Si NO-GO, el plan cambia a fallback `sounddevice` en la Task 8 (se anota aquí el resultado).

- [ ] **Step 1: Añadir la dependencia de audio de Flet**

En `requirements-frontend.txt`, tras la línea `flet==0.28.3`, añade:

```
flet-audio                # Controles de audio de Flet: Audio (reproducir) y AudioRecorder (grabar micro)
```

- [ ] **Step 2: Instalar**

Run:
```powershell
.\.venv\Scripts\Activate.ps1
pip install flet-audio
```
Expected: `Successfully installed flet-audio-...`

- [ ] **Step 3: Escribir el spike de grabación**

Crea `frontend/_spike_recorder.py` (throwaway):

```python
"""Spike: comprobar que flet-audio graba micrófono en Windows escritorio.
Arráncalo con:  flet run frontend/_spike_recorder.py
Pulsa "Grabar", habla 3 s, pulsa "Parar". Debe crearse un fichero reproducible."""
import os
import tempfile

import flet as ft
import flet_audio as fta


def main(page: ft.Page):
    out = os.path.join(tempfile.gettempdir(), "spike_grabacion.m4a")
    rec = fta.AudioRecorder()
    page.overlay.append(rec)
    estado = ft.Text("Listo.")

    def grabar(_):
        rec.start_recording(out)
        estado.value = "Grabando... habla y pulsa Parar."
        page.update()

    def parar(_):
        path = rec.stop_recording()
        existe = os.path.exists(out)
        tam = os.path.getsize(out) if existe else 0
        estado.value = f"Parado. path={path} existe={existe} bytes={tam}"
        page.update()

    page.add(
        ft.Row([ft.ElevatedButton("Grabar", on_click=grabar),
                ft.ElevatedButton("Parar", on_click=parar)]),
        estado,
    )


ft.app(target=main)
```

- [ ] **Step 4: Ejecutar el spike y decidir**

Run:
```powershell
flet run frontend/_spike_recorder.py
```
Pulsa Grabar → habla 3 s → Parar. Observa el texto de estado.
- **GO** si `existe=True` y `bytes` > 0 (y el fichero `%TEMP%\spike_grabacion.m4a` se reproduce en un reproductor). La Task 8 usa `AudioRecorder` tal cual.
- **NO-GO** si falla el permiso de micro, no se crea el fichero, o la API difiere. Anota el error y en la Task 8 usa el fallback `sounddevice` (grabar a un `.wav` con `sounddevice`+`scipy.io.wavfile`), manteniendo el resto del flujo idéntico.

- [ ] **Step 5: Limpiar el spike y commit de la dependencia**

```powershell
Remove-Item frontend/_spike_recorder.py
git add requirements-frontend.txt
git commit -m "chore(voz): dependencia flet-audio (validada por spike de grabacion)"
```

---

### Task 6: Cliente HTTP — `api_client.transcribe`

**Files:**
- Modify: `frontend/api_client.py` (tras `ask`, línea ~97)

**Interfaces:**
- Produces: `transcribe(audio_path: str) -> str` (lanza `BackendError`).

- [ ] **Step 1: Añadir la función**

En `frontend/api_client.py`, tras la función `ask` (línea 97), añade:

```python
def transcribe(audio_path: str) -> str:
    """Sube el audio grabado (multipart) a /api/transcribe y devuelve el texto.

    Se usa cuando el niño pregunta por voz: graba → transcribe → el texto entra
    al mismo flujo que una pregunta escrita.
    """
    url = f"{BACKEND_URL}/api/transcribe"

    try:
        with open(audio_path, "rb") as f:
            files = {"audio": (Path(audio_path).name, f, "application/octet-stream")}
            # timeout holgado: Scribe puede tardar unos segundos en clips largos.
            response = requests.post(url, files=files, timeout=60)

        response.raise_for_status()
        return response.json().get("texto", "")

    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:
            detail = exc.response.text if exc.response is not None else ""
        raise BackendError(f"El backend devolvió un error: {detail or exc}")
    except requests.RequestException as exc:
        raise BackendError(f"Fallo de conexión con el backend: {exc}")
```

- [ ] **Step 2: Verificar contra el backend**

Con el backend arrancado y el `pregunta.mp3` del Task 3 Step 6 disponible:
```powershell
python -c "import sys; sys.path.insert(0,'frontend'); import api_client; print(api_client.transcribe(r'C:\Users\dlope\AppData\Local\Temp\claude\D--DEV-repo-vs-capston\f2b8a075-2c42-4af0-a831-f696f1b2f4e3\scratchpad\pregunta.mp3'))"
```
Expected: imprime el texto transcrito (p. ej. `Qué comes tú.`).

- [ ] **Step 3: Commit**

```powershell
git add frontend/api_client.py
git commit -m "feat(voz): api_client.transcribe (POST /api/transcribe)"
```

---

### Task 7: Frontend — reproducir la respuesta en voz (auto-play, just_playback)

> **Enfoque BYPASS (decidido en Task 5):** NO se usa flet-audio (no graba y su instalación sin pin sube Flet a 1.x, rompiendo el frontend pre-0.80). La reproducción usa `just_playback` (miniaudio), independiente de Flet, en su propio hilo (no bloquea la UI).

**Files:**
- Modify: `frontend/main.py` (imports ~19-27; helper + estado dentro de `main`; `_run_ask` ~748-760)

**Interfaces:**
- Consumes: `result["audio_base64"]` de `api_client.ask` (Task 4).
- Produces: helper `_reproducir_respuesta(audio_b64: str) -> None` que reproduce el mp3 sin bloquear, reutilizando un único `Playback`.

- [ ] **Step 1: Imports**

En `frontend/main.py`, tras `import flet as ft` (línea 23), añade:

```python
import base64
import tempfile

from just_playback import Playback
```
(`os`, `threading`, `time` ya están importados arriba.)

- [ ] **Step 2: Crear el reproductor reutilizable y el helper (dentro de `main`)**

Junto a la creación de los controles del chat (tras `chat_column = ...`, línea ~145), añade:

```python
    # Reproductor de la voz del personaje. just_playback usa miniaudio (mp3) y
    # reproduce en su propio hilo: NO bloquea la UI. Reutilizamos UNA sola
    # instancia (si se recolectara, se cortaría el sonido).
    reproductor = Playback()

    def _reproducir_respuesta(audio_b64: str) -> None:
        """Decodifica el mp3 (base64) a un temporal y lo reproduce sin bloquear.

        Un fallo de reproducción NUNCA rompe la UI: el texto ya está visible. Se
        usa un nombre único por respuesta para no chocar con un mp3 aún bloqueado.
        """
        try:
            mp3 = base64.b64decode(audio_b64)
            ruta = os.path.join(tempfile.gettempdir(), f"respuesta_{int(time.time() * 1000)}.mp3")
            with open(ruta, "wb") as f:
                f.write(mp3)
            reproductor.load_file(ruta)
            reproductor.play()
        except Exception as exc:
            print(f"[Frontend] No se pudo reproducir la voz: {exc}")
```

- [ ] **Step 3: Reproducir el audio en `_run_ask`**

En `_run_ask` (línea 748), tras `_add_burbuja(f"{PERSONAJES[pid]['emoji']} {respuesta}", es_nino=False)` (línea 754), añade:

```python
            # Auto-reproducción de la respuesta (si vino audio), a la vez que
            # aparece la burbuja. Si audio_base64 es None (voz off o TTS falló),
            # simplemente no suena: el texto sigue visible.
            audio_b64 = result.get("audio_base64")
            if audio_b64:
                _reproducir_respuesta(audio_b64)
```

- [ ] **Step 4: Verificar (compilación headless; audio en vivo diferido)**

El test audible completo (escribir una pregunta y oír la voz) necesita la clave de ElevenLabs y la GUI, así que se DIFIERE a una sesión interactiva del usuario. Lo verificable ahora, sin clave ni GUI, es que el fichero compila sin errores de sintaxis:
```powershell
python -m py_compile frontend/main.py
```
Expected: sin salida (éxito). Anota que el test audible queda diferido.

- [ ] **Step 5: Commit**

```powershell
git add frontend/main.py
git commit -m "feat(voz): auto-reproduccion de la respuesta con just_playback"
```

---

### Task 8: Frontend — grabar la pregunta por voz (micrófono, sounddevice)

> **Enfoque BYPASS (decidido en Task 5):** la grabación usa `sounddevice` (captura PCM del micro) + `soundfile` (escribe .wav), NO flet-audio. El dispositivo de entrada por defecto puede ser **-1** (ninguno): hay que elegir uno válido explícitamente. ElevenLabs Scribe acepta .wav.

**Files:**
- Modify: `requirements-frontend.txt` (añadir `numpy`), `frontend/main.py` (imports; controles del chat ~146-167; handlers del chat ~734-760)

**Interfaces:**
- Consumes: `api_client.transcribe` (Task 6), los imports/estado de la Task 7, el flujo `_run_ask` (Task 7).
- Produces: botón de micro con estado grabando/reposo, helpers `_iniciar_grabacion()`/`_detener_grabacion() -> str | None`, y el flujo voz→texto→respuesta.

- [ ] **Step 1: Declarar e instalar numpy**

En `requirements-frontend.txt`, bajo el bloque de voz (tras `just-playback`), añade:
```
numpy                     # Buffer PCM que devuelve sounddevice (modo array) para escribir el wav
```
Instala:
```powershell
.\.venv\Scripts\Activate.ps1
pip install numpy
```

- [ ] **Step 2: Imports en `frontend/main.py`**

Tras los imports de la Task 7, añade:

```python
import numpy as np
import sounddevice as sd
import soundfile as sf
```

- [ ] **Step 3: Estado de grabación + helpers (dentro de `main`, junto al `reproductor` de la Task 7)**

```python
    # Grabación del micrófono con sounddevice → wav. El dispositivo de entrada por
    # defecto puede ser -1 (ninguno): elegimos uno válido explícitamente.
    FS_GRAB = 16000
    grabacion = {"stream": None, "frames": []}

    def _micro_device():
        """Índice de un dispositivo de entrada válido, o None si no hay micro."""
        try:
            d = sd.default.device[0]
            if isinstance(d, int) and d >= 0 and sd.query_devices(d)["max_input_channels"] > 0:
                return d
        except Exception:
            pass
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                return i
        return None

    def _iniciar_grabacion():
        """Abre el stream del micro y empieza a acumular frames PCM."""
        grabacion["frames"] = []

        def _cb(indata, frames, time_info, status):
            grabacion["frames"].append(indata.copy())

        grabacion["stream"] = sd.InputStream(
            samplerate=FS_GRAB, channels=1, device=_micro_device(), callback=_cb
        )
        grabacion["stream"].start()

    def _detener_grabacion():
        """Cierra el stream, escribe los frames a un .wav y devuelve su ruta (o None)."""
        st = grabacion["stream"]
        grabacion["stream"] = None
        if st is not None:
            st.stop()
            st.close()
        if not grabacion["frames"]:
            return None
        audio = np.concatenate(grabacion["frames"], axis=0)
        ruta = os.path.join(tempfile.gettempdir(), f"pregunta_{int(time.time())}.wav")
        sf.write(ruta, audio, FS_GRAB)
        return ruta
```

- [ ] **Step 4: Crear el botón de micrófono**

Tras `preguntar_button = ...` (línea 155), añade:

```python
    mic_button = ft.IconButton(
        icon=ft.Icons.MIC,
        tooltip="Toca para hablar; toca otra vez para enviar",
        disabled=True,
        icon_color=ft.Colors.PURPLE_400,
    )
```

Y en el `ft.Row` del `chat_panel` (línea 164), añade `mic_button` entre el campo y el botón:

```python
            [chat_titulo, chat_column, ft.Row([pregunta_field, mic_button, preguntar_button])],
```

- [ ] **Step 5: Habilitar/deshabilitar el micro junto al campo de texto**

El micro sigue el mismo estado `disabled` que `pregunta_field`/`preguntar_button`. En el bloque donde se activa el chat para un personaje (donde `pregunta_field.disabled = False`, flujo de generación ~línea 706-712), añade:

```python
            mic_button.disabled = False
```

En `empezar_de_nuevo` (línea 778-779, donde se deshabilitan campo y botón), añade:

```python
        mic_button.disabled = True
```

- [ ] **Step 6: Handler de grabar/parar (toggle) + transcripción**

En la zona de handlers del chat, tras la función `preguntar` (línea 746), añade:

```python
    def _toggle_micro(_):
        pid = state["chat_personaje"]
        if not pid:
            return
        if grabacion["stream"] is None:
            # Empezar a grabar.
            try:
                _iniciar_grabacion()
            except Exception as exc:
                _add_burbuja(f"❌ No se pudo abrir el micrófono: {exc}", es_nino=False)
                page.update()
                return
            mic_button.icon = ft.Icons.STOP_CIRCLE
            mic_button.icon_color = ft.Colors.RED_400
            mic_button.tooltip = "Grabando... toca para enviar"
            page.update()
        else:
            # Parar, escribir el wav y transcribir.
            ruta = _detener_grabacion()
            mic_button.icon = ft.Icons.MIC
            mic_button.icon_color = ft.Colors.PURPLE_400
            mic_button.tooltip = "Toca para hablar; toca otra vez para enviar"
            mic_button.disabled = True
            pregunta_field.disabled = True
            preguntar_button.disabled = True
            page.update()
            if not ruta:
                # No se capturó nada: reactivar y salir.
                mic_button.disabled = False
                pregunta_field.disabled = False
                preguntar_button.disabled = False
                page.update()
                return
            threading.Thread(target=_run_transcribe, args=(pid, ruta), daemon=True).start()

    def _run_transcribe(pid: str, audio_path: str):
        try:
            texto = api_client.transcribe(audio_path).strip()
            if not texto:
                # No se entendió nada: reactivar y salir sin preguntar.
                return
            # La pregunta hablada entra al MISMO flujo que una escrita.
            _add_burbuja(f"🧒 {texto}", es_nino=True)
            pensando = ft.Text("🤔 Pensando...", size=13, italic=True)
            chat_column.controls.append(pensando)
            page.update()
            _run_ask(pid, texto, pensando)  # reutiliza el flujo de respuesta+voz
        except api_client.BackendError as exc:
            _add_burbuja(f"❌ {exc}", es_nino=False)
        finally:
            mic_button.disabled = False
            pregunta_field.disabled = False
            preguntar_button.disabled = False
            page.update()
```

- [ ] **Step 7: Conectar el handler al botón**

Junto a `preguntar_button.on_click = preguntar` (búscala), añade:

```python
    mic_button.on_click = _toggle_micro
```

> Nota: la grabación se distingue por `grabacion["stream"] is None` (None = en reposo). `_run_ask` (Task 7) ya reactiva `pregunta_field`/`preguntar_button` en su `finally`; `_run_transcribe` reactiva además `mic_button`.

- [ ] **Step 8: Verificar (compilación headless; micro en vivo diferido)**

La captura real de micro necesita la sesión de escritorio del usuario (con permiso de micro); en este contexto no hay acceso al micro. Lo verificable ahora es que compila:
```powershell
python -m py_compile frontend/main.py
```
Expected: sin salida (éxito). Anota que la prueba de grabación real, transcripción y voz end-to-end queda **diferida** a la sesión interactiva del usuario (que también necesita la `ELEVENLABS_API_KEY`).

- [ ] **Step 9: Commit**

```powershell
git add requirements-frontend.txt frontend/main.py
git commit -m "feat(voz): grabar la pregunta por microfono con sounddevice (tap start/stop)"
```

---

### Task 9: Documentación (README, CLAUDE.md, ARQUITECTURA.md)

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Create: `ARQUITECTURA.md`

**Interfaces:** ninguna (documentación).

- [ ] **Step 1: README — tabla del pipeline**

En `README.md`, sustituye la fila (línea 20):

```markdown
| Entrada por voz | Graba la pregunta con el micro y la transcribe a texto. | Whisper (Replicate) | ⏳ Pendiente |
```

por estas dos:

```markdown
| **Entrada por voz** | Graba la pregunta con el micro (toca para empezar / toca para parar) y la transcribe a texto en español. | **ElevenLabs Scribe** (STT) | ✅ **Implementado** |
| **Respuesta por voz** | La respuesta del personaje se sintetiza con una voz expresiva propia y se reproduce sola. | **ElevenLabs Flash** (TTS) | ✅ **Implementado** |
```

- [ ] **Step 2: README — diagrama de arquitectura**

En el diagrama (líneas 45-50), tras el bloque de `POST /api/ask`, añade una línea para transcribe y menciona el audio en la respuesta. Sustituye el bloque del chat por:

```
│   - Chatear con el       │   POST /api/transcribe      │   [Voz → texto (STT)]        │
│     personaje (texto     │   (audio del micro)         │   - ElevenLabs Scribe        │
│     o voz)               │  ─────────────────────────► │   - Devuelve el texto        │
│                          │   POST /api/ask             │   [Conversación / RAG]       │
│                          │   { personaje_id,           │   - ChromaDB recupera fichas │
│                          │     pregunta }              │   - LLM (Replicate) responde │
│                          │  ─────────────────────────► │   - TTS (ElevenLabs Flash)   │
│                          │  ◄───────────────────────── │   - Devuelve texto + audio   │
└─────────────────────────┘  respuesta (texto + audio)  └──────────────────────────────┘
```

- [ ] **Step 3: README — estructura del proyecto**

En el árbol de `backend/` (líneas 78-85), añade dentro de `services/`:

```
│   │   ├── voice_service.py        #   · voz → texto (Scribe) y texto → voz (Flash): ElevenLabs
```

y dentro de `routers/`:

```
│   │   ├── transcription.py  #   · POST /api/transcribe (voz → texto, ElevenLabs Scribe)
```

y en la línea de `personajes.py` (línea 67) actualiza el comentario:

```
│   ├── personajes.py         # Prompts + NOMBRES + VOCES (voz_id ElevenLabs) de cada personaje
```

- [ ] **Step 4: README — puesta en marcha (clave obligatoria para voz)**

Tras el párrafo de DeepL (línea 129), añade:

```markdown
**Obligatorio para la voz:** pega también tu clave de **ElevenLabs** en `ELEVENLABS_API_KEY`
(modalidad pago por uso). Se usa para transcribir la pregunta hablada del niño (Scribe) y dar
voz a la respuesta del personaje (Flash). Sin ella, la voz queda desactivada pero el chat de
**texto sigue funcionando**. Consigue una clave en [elevenlabs.io](https://elevenlabs.io).
```

Y en la comprobación de `/health` (línea 137-138), añade `"elevenlabs_ok": true` a lo que debe aparecer.

- [ ] **Step 5: README — sección DEBUG (trazas de voz)**

En la tabla de servicios trazados (tras la fila de DeepL, línea 348), añade:

```markdown
| **ElevenLabs — STT** | transcripción de la pregunta hablada (`/api/transcribe`) | `[VOZ] 🎙️ STT · <bytes> → "<texto>"` |
| **ElevenLabs — TTS** | síntesis de la respuesta del personaje (`/api/ask`) | `[VOZ] 🔊 TTS · voz=<voz_id> · <chars> · <personaje_id>` |
```

- [ ] **Step 6: README — decisión de diseño nº 6**

Tras la decisión 5 (línea 463), añade:

```markdown
### 6. Voz con ElevenLabs (Scribe STT + Flash TTS), pago por uso

**Decisión:** usar **ElevenLabs** para las dos mitades de la voz —transcribir la pregunta
hablada (**Scribe**) y dar voz a la respuesta (**Flash**)— con una **voz propia por personaje**
(`VOCES` en `backend/personajes.py`), en modalidad **pago por uso**.

**Por qué:**
- **Voz expresiva en español:** dar carácter a cada personaje (Sherlock grave, Da Vinci cálido)
  pide voces netamente mejores que las de un TTS genérico. El placeholder original preveía solo
  Whisper (Replicate) para STT; ElevenLabs cubre STT **y** TTS con una sola clave y SDK.
- **Latencia:** el modelo Flash responde rápido, importante para que un niño no espere.
- **Coherencia:** encaja con "todo lo pesado en la nube"; el backend solo hace una llamada HTTP más.

**Degradación:** un fallo de voz (o falta de clave) nunca rompe el chat: la respuesta de texto
se sirve igual y `audio_base64` viaja como `null`.

**Arquitectura:** STT es un endpoint aislado (`/api/transcribe`); el TTS viaja **acoplado** a la
respuesta de `/api/ask` (`audio_base64`), porque *toda* respuesta se habla (escrita o hablada).
```

- [ ] **Step 7: README — personalizar (voz de un personaje)**

En la sección "Personalizar" (línea 469), amplía el punto de añadir personajes:

```markdown
- **Añadir personajes:** edita `backend/personajes.py` (`PROMPTS`, `NOMBRES` y, si quieres que
  hable, `VOCES` con su `voz_id` de ElevenLabs) y `frontend/personajes.py` (la tarjeta), usando
  el **mismo `id`** en todos. Un personaje sin `voz_id` responde solo en texto.
```

- [ ] **Step 8: CLAUDE.md — invariantes y arquitectura**

En `CLAUDE.md`, en el bullet del invariante `personaje_id`, añade `VOCES` a los sitios de `backend/personajes.py` y menciona que `voz_id` es el 5º sitio para personajes que hablan. En la sección de arquitectura de RAG, añade una línea sobre voz:

```markdown
- **Voice (`services/voice_service.py`, `routers/transcription.py`)**: `POST /api/transcribe` (audio→texto, ElevenLabs Scribe) feeds the existing `/api/ask`; `/api/ask` now also returns `audio_base64` (the answer voiced by ElevenLabs Flash using the character's `voz_id` from `VOCES`). ElevenLabs is the third provider (with Replicate and DeepL). Voice failures degrade to text-only (`audio_base64: null`) and never break the chat.
```

Y actualiza la nota sobre `_future_phases.py` (ya no existe: Whisper se reemplazó por ElevenLabs, implementado).

- [ ] **Step 9: Crear `ARQUITECTURA.md`**

Crea `ARQUITECTURA.md` en la raíz:

```markdown
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

## Invariante `personaje_id`

Una misma clave conecta cinco sitios (los cuatro primeros para cualquier
personaje; el quinto solo si habla):

1. `backend/personajes.py` → `PROMPTS`, `NOMBRES`, `VOCES`
2. `frontend/personajes.py` → tarjeta visual
3. `backend/documentos/<personaje_id>/` → base de conocimiento

## Degradación y modo DEBUG

- **Degradación:** sin ElevenLabs (o si el TTS falla), `audio_base64` es `null` y el
  chat de texto sigue vivo. Sin DeepL, el chat responde con un error claro (la
  traducción es obligatoria para el RAG).
- **DEBUG (`config.DEBUG`):** trazas en la consola del backend: prompts al LLM/DeepL,
  origen RAG/GENERAL (`[CHAT] ...`) y voz (`[VOZ] 🎙️ STT ...`, `[VOZ] 🔊 TTS ...`).
```

- [ ] **Step 10: Verificar y commit**

Revisa que el README renderiza bien (tablas y bloque de diagrama) y que `ARQUITECTURA.md` existe.
```powershell
git add README.md CLAUDE.md ARQUITECTURA.md
git commit -m "docs(voz): README, CLAUDE.md y ARQUITECTURA.md para la fase de voz"
```

---

## Notas de ejecución

- **Orden:** Tasks 1→4 (backend) son independientes del frontend y se pueden verificar solas por HTTP. Task 5 (spike) desbloquea/ajusta la Task 8. Tasks 6→8 (frontend) dependen del backend ya funcionando. Task 9 (docs) al final.
- **Coste:** las verificaciones que llaman a ElevenLabs consumen algo de cuota (pago por uso). Son frases cortas; el gasto es mínimo.
- **API de flet-audio:** si el spike (Task 5) revela que la firma de `AudioRecorder.start_recording/stop_recording` difiere en la versión instalada, ajusta la Task 8 en consecuencia (o usa el fallback `sounddevice`), sin cambiar el resto del flujo.
