# Arquitectura — MundoAventura

Documento técnico de conjunto del pipeline completo (imagen + RAG + voz). El
README es la guía de uso; este documento es la referencia de arquitectura para la
memoria final del capstone.

## Visión general

App educativa (niños 8–12) cliente-servidor desacoplada:

- **Frontend (SPA React):** Vite 8 + React 19 + TypeScript 6, en el navegador; asistente por
  pasos: catálogos (carrusel), escena y chat (texto + voz). **Instalable como app** (PWA) y
  utilizable en móvil, tablet y PC. Dos dependencias de producción: `react` y `react-dom`.
- **Backend (FastAPI):** routers finos → services → config. Sin GPU local. **21 dependencias
  de producción** (`pyproject.toml`), ninguna de ellas `torch`; `faster-whisper` va aparte como
  extra opcional (`stt-local`).
- **Nube:** Replicate (imagen + LLM), DeepL (traducción), ElevenLabs (voz).
- **Producción:** VPS propio con Caddy (TLS) + systemd, despliegue continuo desde `main`.

## Los tres proveedores

| Proveedor | Para qué | Dónde |
|-----------|----------|-------|
| **Replicate** | Generación de imagen (FLUX) y LLM del chat (Llama 3, por defecto) | `generation_service.py`, `llm_service.py` |
| **DeepL** | Traducción ES→EN de la pregunta (mejora el retrieval) | `translation_service.py` |
| **ElevenLabs** | Voz: transcripción (Scribe/STT, opcional) y síntesis (Flash/TTS) | `voice_service.py`, `stt_service.py` |

> **Capa de LLM intercambiable (Hito 5):** el LLM del chat ya no está clavado a
> Replicate. `llm_service.py` despacha por `LLM_PROVIDER`: `replicate` (por defecto,
> reproduce la línea base) u `openai` (endpoint openai-compatible vía `LLM_BASE_URL`:
> Groq, Mistral, Ollama local…). Cambiar de proveedor es cambiar config, no código
> (habilita el estudio comparativo de H6).

> **Capa de STT intercambiable (Hito 7):** la transcripción tampoco está clavada a
> ElevenLabs. `stt_service.py` despacha por `STT_PROVIDER`: `elevenlabs` (por defecto,
> Scribe en nube) | `local` (**faster-whisper**, CTranslate2 sin torch, la voz del niño
> NO sale del PC — motivación de RGPD; dependencia opcional `stt-local`) | `groq`
> (Whisper en Groq). Si el STT local no carga (DLLs de cuBLAS/cuDNN), **cae solo a la
> nube** (nunca se queda muda). `voice_service.transcribir` delega en `stt_service`.

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

> **Streaming de la respuesta (Hito 8):** junto al `/api/ask` JSON (de una vez, que
> el runner sigue usando) hay `POST /api/ask/stream` (**SSE**), que emite `fuentes` →
> `token` (texto según lo genera el LLM) → `audio_chunk` (voz **por frases**, en cuanto
> cierra cada una) → `fin`. Así el niño empieza a leer/oír a ~1–2 s en vez de esperar
> ~7–12 s en blanco. `rag_service` cede el texto (`responder_streaming`), `chat_service`
> orquesta el TTS por frases con **caché en disco** (`audio_cache`), y `Chat.tsx` pinta
> incremental con una cola de audio. Un fallo de TTS degrada a solo-texto.

En el frontend, la voz usa las **APIs estándar del navegador**, sin librerías:
la pregunta se graba con **`MediaRecorder`** (`getUserMedia`), que produce
webm/opus en Chrome y ogg/opus en Firefox — ambos aceptados por Scribe, que
deduce el formato de los propios bytes —, y la respuesta se reproduce con
**`Audio()`** (`data:audio/mpeg;base64,...`). `getUserMedia` solo existe en
contextos seguros (https o localhost): fuera de ellos, o si se deniega el
permiso, el micro se deshabilita con un aviso claro y el chat de texto sigue
funcionando.

> *Nota histórica:* el primer frontend fue de escritorio (Flet) y no podía grabar con
> `flet-audio`; la migración a la SPA React eliminó esa fricción con las APIs nativas del
> navegador. Documentos de aquella etapa en [`historico/`](historico/).

## Capa de presentación (frontend)

El frontend no es un detalle de implementación: la mitad de las decisiones defendibles del
proyecto están en cómo se le presenta el sistema a un niño de 8 a 12 años.

**Estructura.** `screens/` (una por pantalla del flujo y de la zona de adulto) ·
`components/` (reutilizables: `Coverflow`, `Chat`, `SceneView`, `HoloCard`, `Console`,
`Hud`, `Modal`…) · `state/useFlow.ts` (máquina de estados de los 3 pasos, `useReducer`) ·
`api/client.ts` (única puerta al backend; tokens y SSE) · `audio/sfx.ts` · `pwa/instalar.ts`
· `styles/tokens.css` (paleta y tipografías) + CSS Modules por componente.

**Sin librerías de UI, de estado ni de router.** Solo `react` y `react-dom` en producción.
El tema "Arcade Holo" es CSS propio sobre tokens; el carrusel 3D, el streaming incremental
y los efectos de sonido están escritos a mano. Es una decisión de alcance: menos superficie
que mantener y nada que explicar que no sea del proyecto.

**Responsive (móvil · tablet · PC).** Tres tramos con cortes en **641 px** y **960 px**. El
problema que resolvió no era estético: en pantalla estrecha el chat estiraba la página y el
campo de escribir la pregunta quedaba fuera de la vista. Hoy `.holo-wrap` es una columna
flex a altura de pantalla, la escena se recoge en una barra mini con visor, y el historial
hace su propio scroll con el input siempre abajo. Todo con `@media`, **sin JavaScript de
layout**; el único estado añadido es la apertura del visor de la escena.

**App instalable (PWA).** `manifest.webmanifest` + iconos (con variante *maskable*) + un
service worker escrito a mano. El service worker **solo intercepta lo que entiende**:
navegación (red primero, para que un despliegue nuevo no se quede congelado) y `/assets/`
(caché primero, porque el nombre lleva el hash del contenido). **Nunca toca `/api/`**, donde
viven el SSE del chat y las subidas. Desde el login se ofrece instalarla. El empaquetado como
APK (TWA) está documentado y sin ejecutar: [`APK-ANDROID.md`](APK-ANDROID.md).

**Efectos de sonido.** Sintetizados con la Web Audio API (`audio/sfx.ts`): sin ficheros de
audio ni dependencias. Un solo `AudioContext`, despertado por el primer gesto del usuario
(política de autoplay). Es independiente de la voz del personaje, que es el mp3 de
ElevenLabs. Interruptor 🔊/🔇 en el HUD, persistido en `localStorage`.

## Blindaje operativo (Hito 2)

El despliegue es una URL pública, así que los endpoints del niño se protegen sin añadirle
fricción. Cinco piezas, todas con tests:

| Pieza | Dónde | Qué hace |
|---|---|---|
| **Concurrencia** | endpoints `def` (no `async def`) | FastAPI los ejecuta en su threadpool: un SDK bloqueante no congela el event loop ([ADR-002](decisiones/ADR-002-concurrencia.md)) |
| **Timeouts + reintentos** | `services/resiliencia.py` | Backoff exponencial con jitter ante 429/5xx/timeout. DeepL queda fuera a propósito: su SDK ya lo hace |
| **Límites de subida** | `routers/limites.py` | Corta por trozos → **413** (imagen 10 MB, audio 5 MB, documento 20 MB) |
| **Rate limit + cupo** | `ratelimit.py`, `services/cuota_service.py` | Por IP; y un tope diario de imágenes en SQLite. Al superarlo, el chat responde **en personaje**, nunca un 429 crudo al niño |
| **Saneado de errores** | `routers/errores.py` | Los 500 no filtran el mensaje del SDK: se registra el detalle con un `error_id` y al cliente le llega un texto genérico + ese id |

## Topología de producción

```
   Internet ──HTTPS(443)──►  Caddy  ──► /api, /health ──► uvicorn (systemd, 127.0.0.1)
                              │                              │
                              └── SPA estática (dist/)        └── SQLite · ChromaDB · documentos · caché TTS
```

SPA y API **comparten origen**, así que no hay CORS que configurar. El backend no se expone:
escucha solo en local. La activación por **socket de systemd** hace que un despliegue no
corte las conexiones (medido: 10 % de 502 → 0 %). Un `merge` a `main` dispara el despliegue,
con comprobación de humo y **vuelta atrás automática** si `/health` no responde.
Procedimiento completo en [`DESPLIEGUE.md`](DESPLIEGUE.md).

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

- **Tablas del SQLite:** `settings` (ajustes en caliente + claves reservadas de admin y 2FA,
  que nunca se exportan), `personajes`, `ubicaciones`, `documentos`, `familias`,
  `sesiones_familia` (solo el hash del token), `uso_diario` (cupo de imágenes) y `auditoria`.
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
  porcentaje**, la misma métrica nativa de ChromaDB que usa el Evaluator (ver
  [`DECISIONES.md`](DECISIONES.md)).
- **Auditoría de uso:** tabla `auditoria` (`auditoria_service`, pestaña 🛡️ Admin → Auditoría):
  registra alta/login/logout de familia, generación de escena y preguntas, con filtros,
  export CSV y **purga por retención** (`AUDITORIA_RETENCION_DIAS`). Guardar el *contenido*
  de las preguntas es un toggle aparte (`AUDITORIA_CONTENIDO`), porque es texto de un menor.
  Registrar **nunca** puede romper el flujo del niño: todo va en `try/except` best-effort.
  Al borrar una cuenta, sus eventos se borran en cascada.
- **Dos niveles de acceso (Hito 7 → Hito 9.2):** la app dejó de ser anónima. Hay **dos zonas
  de adulto**, con dos botones en el HUD:
  - **⚙️ Configuración** — autoservicio de la **familia**. Cada familia es una cuenta con email
    del adulto + contraseña (PBKDF2) + nombre; alta autoservicio, sesión **persistente** (en
    SQLite solo el hash SHA-256 del token; el token real vive en `localStorage`). La app va
    detrás de esta sesión (`GET /api/familias/me`, cabecera `X-Family-Token`). Multi-perfil de
    niños (`{nombre, sexo}`); el perfil activo personaliza el prompt del chat. Un **PIN de
    familia** (4 dígitos, hasheado) protege el consentimiento de la foto y la edición del perfil.
    Verificación de correo por OTP **opcional** (`EMAIL_VERIFICACION`, por defecto OFF).
    `familias_service`, `routers/familias.py`, tablas `familias`/`sesiones_familia`.
  - **🛡️ Admin** — configuración global compartida. Credencial de **contraseña ≥ 8 caracteres**
    con **2FA TOTP opcional** (toggle por defecto OFF; `pyotp`/`segno`). `admin_service`: la
    dependencia `requiere_admin` protege los endpoints sensibles (config, apis, documentos,
    auditoría, y las escrituras de personajes/ubicaciones). El login está endurecido contra
    fuerza bruta (retardo + bloqueo por IP → 429). Incluye **import/export** JSON de la
    configuración (sin secretos) y una **copia de seguridad** del SQLite antes de importar.

  Flujos de datos y checklist RGPD (incluido el email del adulto como dato personal) en
  [`PRIVACIDAD.md`](PRIVACIDAD.md).

### Quién puede llamar a cada endpoint

`requiere_admin` **no** es la única barrera, y conviene no confundir "no es de admin" con
"es público". Los endpoints que cuestan dinero llevan **dos** dependencias encadenadas
(`_caros = _acceso + _familia` en `main.py`):

| Grupo | Endpoints | Quién puede |
|---|---|---|
| **Informativos** | `GET /`, `GET /health` | Cualquiera |
| **Catálogos (lectura)** | `GET /api/personajes`, `/api/ubicaciones`, sus `/avatar` | Cualquiera — los necesita la SPA antes de tener sesión. **Salvo `?todos=1`**, que incluye los elementos desactivados y exige `X-Admin-Token` |
| **Cuenta de familia** | `signup`, `login`, `verificar`, `reenviar`, `me`, `estado` | Cualquiera (son la puerta); login y OTP con bloqueo por IP → 429 |
| **Perfil de familia** | `PUT /api/familias/perfil`\|`pin`, `DELETE /api/familias/cuenta` | Sesión de familia (`X-Family-Token`) |
| **Flujo del niño (caros)** | `POST /api/generate`, `/api/generate-on-photo`, `/api/ask`, `/api/ask/stream`, `/api/transcribe` | **Candado (`X-Access-Code`) + sesión de familia**, más rate limit y cupo diario |
| **Administración** | config, apis, documentos, auditoría, escrituras de catálogos, voces | `X-Admin-Token` (contraseña + 2FA opcional) |

La segunda barrera del flujo del niño es deliberada y se gobierna con
`EXIGIR_SESION_FAMILIA` (**por defecto `true`**): el candado `ACCESS_CODE` viaja dentro del
bundle de la SPA, así que es **público de facto** y no sirve como autenticación. Sin la
sesión de familia, cualquiera podría gastar el saldo de Replicate con un `curl`. Ese toggle
es de despliegue (`.env`) y **no** se expone en el menú de configuración: la autenticación
no se apaga desde la interfaz.

## Retrieval: reranker opcional (Hito 4.3)

Entre el retrieval y el Evaluator hay un paso opcional. Con `RERANKER != off`,
`rag_service._recuperar_contexto` recupera `RERANK_CANDIDATOS` candidatos y un
**cross-encoder** (`jina-reranker-v2`, vía `fastembed`, ONNX/CPU, sin torch) los
**reordena por relevancia** leyendo pregunta+ficha juntas (más fino que el coseno), y se
queda con `RAG_TOP_K`. Reordena **en consulta**, así que se activa en caliente sin
reindexar. Con reranker activo, el **ruteo lo decide su puntuación** (`rerank_score ≥
RERANK_UMBRAL ⇒ RAG`) y el LLM-juez ya no se llama. Ver el
[ADR-006](decisiones/ADR-006-reranker.md).

## Seguridad infantil (Hito 9)

Tres barreras que no se deben quitar (ver el
[ADR-010](decisiones/ADR-010-seguridad-infantil.md)):

1. **Anti-inyección** — las fichas del RAG entran **delimitadas** con `<documento>…</documento>`
   y el prompt de sistema las trata como **datos, nunca órdenes**: un documento que diga "ignora
   tus instrucciones" no reescribe al personaje.
2. **Filtro de salida** (`safety_service.filtrar_salida`: idioma español + longitud + lista
   mínima de términos inapropiados) — se aplica **solo a la vía GENERAL** (texto no fundamentado);
   si no pasa, se entrega `MENSAJE_SIN_INFORMACION`. Con streaming, la vía GENERAL se genera
   **completa y se filtra antes** de entregarse; solo la vía RAG se streamea palabra a palabra.
3. **Consentimiento parental** — subir la foto pasa por `ConsentModal` (PIN de familia o casilla);
   la **foto no se persiste** (`generation_service.generar_en_foto` la procesa solo en memoria).

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
  voz (`[VOZ] 🎙️ STT ...`, `[VOZ] 🔊 TTS ...`). No tiene ningún efecto visible para el niño.
- **MOSTRAR_FUENTES** (flag aparte, desde el Hito 4.2): controla si el chat muestra al niño el
  desplegable "📚 ¿De dónde lo he sacado?" con las fichas de cada respuesta RAG
  (`rag_service.responder` solo incluye `fuentes` si `MOSTRAR_FUENTES` está activo). Es
  **pedagogía**, no depuración — por eso se separó de `DEBUG`. Si un doc o comentario antiguo
  dice que `DEBUG` enseña las fuentes, está obsoleto.
