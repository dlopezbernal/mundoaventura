# Medición — Bloqueo del event loop (H2, tarea 1)

**Qué se mide:** cuánto tarda `GET /health` mientras hay **2 peticiones largas a
`/api/ask` en vuelo**. Es la prueba de si el event loop de FastAPI se congela.

**Cómo:** `scripts/bench_concurrencia.py` levanta un uvicorn real sobre un puerto,
stubea `rag_service.responder` con un `time.sleep(3s)` determinista (simula la I/O
de red bloqueante de los SDKs, sin gastar crédito ni depender del jitter de red) y
aísla `/health` de la red. Un cliente HTTP independiente cronometra `/health` con
las dos asks en curso.

```
uv run python scripts/bench_concurrencia.py --sleep 3
```

> **Nota de método (una trampa que se cortó):** medir con un `httpx.Client` NUEVO
> por llamada añadía ~540 ms de establecimiento de conexión (en Windows) a cada
> muestra, enmascarando la latencia real del servidor. El benchmark reutiliza una
> única conexión para cronometrar `/health`, de modo que mide el servidor, no el
> cliente. El **máximo** es la métrica que manda (peor caso con las asks en vuelo);
> la mediana engaña porque, mientras la primera sonda espera al bloqueo, las asks
> terminan y las siguientes sondas ya vuelan.

## Resultados

Bloqueo simulado de 3 s por petición, 2 `/api/ask` en vuelo, mismo script para ambas filas.

| Escenario | Endpoints | `/health` **máximo** | mediana | Veredicto |
|---|---|---|---|---|
| **Antes** | `async def` llamando a código bloqueante | **5959 ms** | 1,6 ms | 🔴 BLOQUEADO |
| **Después** | `def` → threadpool de FastAPI | **2,2 ms** | 1,7 ms | 🟢 OK (< 200 ms) |

Muestras `/health` (ms):
- Antes: `[1.6, 1.5, 1.9, 1.6, 5958.9]` — la 1ª sonda espera ~6 s (las 2 asks serializadas en el loop).
- Después: `[1.7, 1.6, 2.0, 1.6, 2.2]` — el loop nunca se bloquea.

## Interpretación

Con los endpoints `async def`, la llamada síncrona bloqueante corre **en el event
loop**: las 2 asks se serializan (≈3 s + 3 s) y **congelan el servidor entero**,
por eso la primera sonda a un `/health` trivial espera ~6 s. Basta una pregunta
lenta para tumbar la responsividad de todo el backend.

El arreglo es declarar esos endpoints como `def`: FastAPI ejecuta las funciones
síncronas en su **threadpool**, el event loop queda libre y `/health` responde en
~2 ms aunque haya varias asks en curso — **2700× más rápido** en el peor caso, por
debajo del criterio de aceptación (< 200 ms). Los tres endpoints multipart
(subida de foto, audio y documentos) siguen siendo `async def` pero delegan su
trabajo bloqueante con `await run_in_threadpool(...)`, con el mismo efecto.
