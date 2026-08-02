# Arquitectura — Máquina del Tiempo en tu Habitación

Documento técnico de conjunto del pipeline completo (imagen + RAG + voz). El
README es la guía de uso; este documento es la referencia de arquitectura para la
memoria final del capstone.

## Visión general

App educativa (niños 8–12) cliente-servidor desacoplada:

- **Frontend (SPA React):** Vite + React 18 + TypeScript, en el navegador; asistente por
  pasos: catálogos (carrusel), escena y chat (texto + voz).
- **Backend (FastAPI):** routers finos → services → config. Sin GPU local.
- **Nube:** Replicate (imagen + LLM), DeepL (traducción), ElevenLabs (voz).

## Los tres proveedores

| Proveedor | Para qué | Dónde |
|-----------|----------|-------|
| **Replicate** | Generación de imagen (FLUX) y LLM del chat (Llama 3, por defecto) | `generation_service.py`, `llm_service.py` |
| **DeepL** | Traducción ES→EN de la pregunta (mejora el retrieval) | `translation_service.py` |
| **ElevenLabs** | Voz: transcripción (Scribe/STT) y síntesis (Flash/TTS) | `voice_service.py` |

> **Capa de LLM intercambiable (Hito 5):** el LLM del chat ya no está clavado a
> Replicate. `llm_service.py` despacha por `LLM_PROVIDER`: `replicate` (por defecto,
> reproduce la línea base) u `openai` (endpoint openai-compatible vía `LLM_BASE_URL`:
> Groq, Mistral, Ollama local…). Cambiar de proveedor es cambiar config, no código
> (habilita el estudio comparativo de H6).

## Flujo de una pregunta por voz (secuencia)

```
Niño (SPA React)   Backend (FastAPI)         Nube
   │  MediaRecorder      │                     │
   │  (webm/ogg opus)    │                     │
   │───/api/transcribe──►│──Scribe (STT)──────►│  ElevenLabs
   │◄──── texto ES ──────│◄────────────────────│
   │                     │                     │
   │───/api/ask─────────►│──DeepL ES→EN───────►│  DeepL
   │                     │──retrieval (ChromaDB, local CPU)
   │                     │──Evaluator (umbral/LLM)
   │                     │──LLM respuesta ES──►│  Replicate
   │                     │──Flash (TTS)───────►│  ElevenLabs
   │◄── texto + audio ───│◄────────────────────│
   │  (burbuja + auto-play con Audio())        │
```

Una pregunta **escrita** salta `/api/transcribe`: va directa a `/api/ask` y la
respuesta vuelve igualmente con `audio_base64` (toda respuesta se habla).

En el frontend, la voz usa las **APIs estándar del navegador**, sin librerías:
la pregunta se graba con **`MediaRecorder`** (`getUserMedia`), que produce
webm/opus en Chrome y ogg/opus en Firefox — ambos aceptados por Scribe, que
deduce el formato de los propios bytes —, y la respuesta se reproduce con
**`Audio()`** (`data:audio/mpeg;base64,...`). `getUserMedia` solo existe en
contextos seguros (https o localhost): fuera de ellos, o si se deniega el
permiso, el micro se deshabilita con un aviso claro y el chat de texto sigue
funcionando.

> *Nota histórica:* el primer frontend (de escritorio, en Flet) no podía usar
> `flet-audio` (un spike comprobó que no graba y que arrastraba una actualización
> de Flet que rompía la interfaz), así que grababa con `sounddevice` + `soundfile`.
> La migración a la SPA React eliminó esa fricción con las APIs nativas del navegador.

## Invariante `personaje_id`

Desde el Hito 4, el catálogo de personajes vive en la **tabla `personajes`**
(SQLite) y se lee a través de `personajes_service`; tanto el backend (generación
de imagen y chat) como el frontend (pantalla del niño y pestaña de configuración)
lo consumen por API (`GET /api/personajes`). Así, el `personaje_id` conecta:

1. Fila en la tabla `personajes` → `nombre`, `categoria`, `emoji`, `prompt_imagen`,
   `voz_id` (ElevenLabs, opcional: sin voz = solo texto), `activo`.
2. `backend/documentos/<personaje_id>/` → base de conocimiento del RAG (la carpeta
   se crea automáticamente al dar de alta un personaje).

`backend/personajes.py` pasa a ser solo la **fuente de "seeding"** (`PROMPTS`,
`NOMBRES`, `VOCES`, `CATEGORIAS`, `EMOJIS`, más el estilo global `STYLE_SUFFIX`/
`FRAMING`): en el primer arranque `seed.py` vuelca esos valores a la tabla (de
forma idempotente y con backfill de las columnas nuevas). Crear un personaje desde
la UI (`POST /api/personajes`) genera de golpe la fila y su carpeta de documentos,
hasta el tope `MAX_PERSONAJES` (`config.py`, 10 por defecto) — un límite de
despliegue fijo por `.env`, deliberadamente **fuera** de `settings_service` (no se
edita desde el menú); `personajes_service.crear` lo aplica y `GET /api/personajes`
lo expone como `limite` para que el frontend deshabilite el alta sin necesidad de
otra llamada.

Las **ubicaciones** (Hito 6) siguen el MISMO patrón: viven en la tabla `ubicaciones`
(`nombre`, `emoji`, `prompt`, `activo`), vía `ubicaciones_service`, y las consumen el
backend (generación) y el frontend por `GET /api/ubicaciones` (CRUD en
`POST/PUT/DELETE /api/ubicaciones`). `backend/ubicaciones.py` queda como fuente de
"seeding" (`UBICACIONES`/`NOMBRES`/`EMOJIS`); el antiguo catálogo estático del frontend
se ha eliminado.

## Capa de configuración (SQLite + `settings_service`)

Los parámetros del motor **ya no son constantes congeladas de `config.py`**: se leen a
través de `backend/services/settings_service.py`, que devuelve el valor **vigente** desde
**SQLite** (con caché en memoria e invalidación al guardar) y **cae al valor por defecto**
—el actual de `config.py`— si la base de datos está vacía. Así, un cambio hecho desde el
menú de configuración surte efecto en la **siguiente petición sin reiniciar**, y con la
BBDD vacía la app se comporta exactamente como antes (compatibilidad hacia atrás).

- **Qué vive en SQLite:** ajustes de IA (umbrales/modo del Evaluator, `RAG_TOP_K`,
  `PERMITIR_CONOCIMIENTO_GENERAL`), chunking, modelo/`max_tokens`/`temperature` del LLM,
  los **prompts de sistema** (externalizados desde `rag_service.py`, con variables
  `{nombre}`/`{fichas}`/`{pregunta}`, incluyendo el mensaje fijo `MENSAJE_SIN_INFORMACION`),
  opciones generales como `DEBUG`, los **catálogos de personajes y ubicaciones** (tablas
  `personajes`/`ubicaciones`, vía `personajes_service`/`ubicaciones_service`; CRUD por
  `GET/POST/PUT/DELETE /api/personajes` y `/api/ubicaciones`, y las voces de ElevenLabs
  por `GET /api/voices`) y los **metadatos de los documentos del RAG**
  (tabla `documentos`, vía `documentos_service`; subir uno o varios/URL/**ver/editar
  contenido**/**descargar**/**copiar a otro personaje**/borrar por `.../documentos`,
  reindexar por `.../reindex`, y el progreso del reindexado global sondeable en
  `GET /api/reindex/estado`). El idioma de cada documento se **detecta con DeepL**
  (auto, cualquier idioma) en vez de marcarlo a mano. Los ficheros del RAG siguen en
  disco (`backend/documentos/<id>/`) y ChromaDB en su carpeta; el reindexado es
  incremental por personaje (solo se reconstruyen sus chunks) con opción de
  reindexado global.
- **Qué vive en el `.env`:** solo los **secretos** (claves API). `secrets_service.py`
  los lee/escribe de forma atómica (fichero temporal + backup) pero **nunca** devuelve
  la clave completa al frontend (solo enmascarada); revelarla es una petición aparte.
- **Endpoints:** `GET /api/config` (ajustes + secretos enmascarados) y `PUT /api/config`
  (guarda y aplica en caliente; informa de qué cambios exigen reindexar ChromaDB).
- **Umbral del RAG:** se expone como **distancia coseno directa (0–2), sin conversión a
  porcentaje**, la misma métrica nativa de ChromaDB que usa el Evaluator (ver README,
  "Decisiones de diseño").
- **Acceso de adulto (Hito 7):** toda la zona de configuración va detrás de un **PIN**
  (`admin_service`): el PIN se guarda *hasheado* (PBKDF2) en la tabla `settings`, el login
  devuelve un token de sesión en memoria y la dependencia `requiere_admin` protege los
  endpoints sensibles (config, apis, documentos, y las escrituras de personajes/ubicaciones);
  los `GET` de catálogos y el flujo del niño (`/generate`, `/ask`, `/transcribe`, `/health`)
  siguen públicos. Incluye **import/export** JSON de la configuración (sin secretos) y una
  **copia de seguridad** del SQLite antes de importar.

## Degradación y modo DEBUG

- **Degradación:** sin ElevenLabs (o si el TTS falla), `audio_base64` es `null` y el
  chat de texto sigue vivo. Sin DeepL, el chat responde con un error claro (la
  traducción es obligatoria para el RAG **y** para gestionar documentos: la detección
  de idioma también pasa por DeepL). En el frontend, si no hay `getUserMedia`
  (contexto no seguro), micrófono o permiso, el micro se deshabilita y el chat de
  texto sigue disponible igualmente (la voz es un añadido, no un requisito del flujo).
- **Tercer camino del Evaluator (`SIN_INFO`):** cuando las fichas no sirven, el
  comportamiento por defecto es caer a GENERAL (conocimiento propio del LLM). Con
  `PERMITIR_CONOCIMIENTO_GENERAL` desactivado, `rag_service.responder` no llama a
  ningún LLM: devuelve el mensaje fijo `MENSAJE_SIN_INFORMACION` (`origen: SIN_INFO`).
  No es degradación por fallo, es una elección deliberada para un chat anclado
  estrictamente a los documentos subidos, sin coste de LLM en los huecos.
- **DEBUG:** ajuste editable (`settings_service`, con valor inicial de `config.DEBUG`), por
  lo que se puede activar/desactivar en caliente desde el menú. Enciende trazas en la
  consola del backend: prompts al LLM/DeepL, origen RAG/GENERAL/SIN_INFO (`[CHAT] ...`) y
  voz (`[VOZ] 🎙️ STT ...`, `[VOZ] 🔊 TTS ...`). **Único efecto visible al niño:** también
  activa, en el chat mismo, el desplegable "📚 ¿De dónde lo he sacado?" con las fichas de
  cada respuesta RAG (`rag_service.responder` solo incluye `fuentes` en la respuesta si
  `DEBUG` está activo) — por eso debe quedar en `false` en la build final, no solo por
  las trazas de consola.
