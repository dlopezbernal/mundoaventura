# ADR-002 — Endpoints síncronos (`def`) para no bloquear el event loop

- **Estado:** aceptada
- **Fecha:** 2026-08-01
- **Hito:** H2
- **Rama:** `feat/h2-blindaje`

## Contexto

Los endpoints del backend eran `async def` pero por dentro llamaban a SDKs
**síncronos** con I/O de red (`replicate.run`, DeepL, ElevenLabs, ChromaDB). En
FastAPI, un `async def` corre en el **event loop**: si dentro se ejecuta código
bloqueante, congela el proceso entero hasta que termina. Una sola pregunta lenta
dejaba al resto de peticiones (incluido un `GET /health` trivial) esperando detrás.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| A. Dejar `async def` + envolver todo en `run_in_threadpool` | Explícito | Ruido en cada endpoint; fácil olvidarse de uno |
| B. Declarar los endpoints `def` (FastAPI los manda a su threadpool) | Idiomático, una línea, difícil de equivocar | Hay que entender el modelo de FastAPI |
| C. Hacer async de verdad (clientes async de cada SDK) | "Puro" async | Reescritura grande; los SDKs usados son síncronos; fuera de alcance de H2 |

## Medición

`scripts/bench_concurrencia.py` (uvicorn real + cliente independiente, bloqueo
determinista de 3 s, 2 `/api/ask` en vuelo). Detalle en
`docs/mediciones/H2-concurrencia.md`.

| Escenario | `/health` máximo | Veredicto |
|---|---|---|
| Antes (`async def` + bloqueante) | **5959 ms** | 🔴 loop congelado |
| Después (`def` → threadpool) | **2,2 ms** | 🟢 loop libre (< 200 ms) |

~2700× mejor en el peor caso.

## Decisión

**Opción B.** Los endpoints JSON (`/api/ask`, `/api/generate`) pasan a `def`; los
tres multipart (foto, audio, documentos) siguen `async def` para leer el fichero,
pero delegan el trabajo bloqueante con `await run_in_threadpool(...)`.

## Qué se descarta y por qué

- **A (todo `run_in_threadpool`):** para los endpoints sin fichero es ruido
  innecesario; `def` consigue lo mismo con menos código y menos margen de error.
- **C (async de verdad):** los SDKs de Replicate/DeepL/ElevenLabs que usamos son
  síncronos; reescribir a clientes async es una obra mayor, fuera del alcance de H2
  (blindaje operativo), y no aporta sobre el threadpool para este volumen.

## Consecuencias

- **Código:** `async def`→`def` en `conversacion.py` y `generation.py` (generate);
  `run_in_threadpool` en `generate_on_photo`, `transcribe` y la subida de documentos.
- **Configuración/`.env`:** sin cambios.
- **Deuda/limitación aceptada:** el threadpool por defecto de anyio tiene 40 hilos;
  suficiente para este uso (unos pocos niños), pero es el techo de concurrencia real
  de las llamadas bloqueantes.
- **Revisar si:** el volumen creciera mucho o se migrara a SDKs async → entonces sí
  compensaría el async de verdad (opción C).
