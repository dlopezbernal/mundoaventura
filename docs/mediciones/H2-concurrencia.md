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

## Resultados

| Escenario | Endpoints | `/health` mediana | `/health` máximo | Veredicto |
|---|---|---|---|---|
| **Antes** (commit 1) | `async def` llamando a código bloqueante | **567 ms** | **6424 ms** | 🔴 BLOQUEADO |
| **Después** (commit 2) | `def` (FastAPI → threadpool) | _(pendiente)_ | _(pendiente)_ | _(pendiente)_ |

## Interpretación

Con los endpoints `async def`, la llamada síncrona bloqueante corre **en el event
loop**: las 2 asks se serializan (≈3 s + 3 s) y **congelan el servidor entero**,
por eso un `/health` trivial llega a esperar ~6,4 s. Basta una pregunta lenta para
tumbar la responsividad de todo el backend.

El arreglo (commit 2) es declarar esos endpoints como `def`: FastAPI ejecuta las
funciones síncronas en su **threadpool**, el event loop queda libre y `/health`
responde en milisegundos aunque haya varias asks en curso. La cifra "después"
confirmará que baja por debajo del criterio de aceptación (< 200 ms).
