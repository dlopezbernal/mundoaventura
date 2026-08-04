# H2 — Blindaje operativo y del túnel

- **Rama:** `feat/h2-blindaje`
- **Semana:** S1, días 4–5
- **Depende de:** H1 (necesita los tests y el logging ya montados)
- **Prioridad que sirve:** #1 y #3

## Objetivo

Arreglar los fallos operativos que hoy hacen que el sistema se bloquee, se
quede colgado, o pueda vaciar el crédito de las APIs desde una URL pública.

## Por qué es urgente

El despliegue previsto es un túnel ngrok/Colab. **Una URL de túnel se escanea
sola en horas.** `POST /api/generate-on-photo` sin autenticación es una tarjeta
de crédito abierta a internet.

## Alcance

### SÍ
- Concurrencia, timeouts, límites de tamaño, candado del túnel, endurecimiento
  del PIN, saneado de errores, `datetime` deprecado.

### NO
- Ningún cambio de proveedor ni de modelo.
- Nada de retrieval ni de prompts.

## Tareas

### 1. Desbloquear el event loop (medido)
Los 5 endpoints son `async def` pero llaman a código síncrono con I/O de red
(`replicate.run`, DeepL, ElevenLabs, ChromaDB). **Una pregunta congela el
servidor entero** durante todo el pipeline.

Endpoints afectados: `routers/conversacion.py:20`, `routers/generation.py:21`
y `:39`, `routers/transcription.py:20`, `routers/documentos.py:49`.

**Antes de arreglarlo, medir**: script que lance 2 peticiones concurrentes a
`/api/ask` y un `GET /health` en paralelo, y registre cuánto tarda el `/health`.
Guardar el número.

Arreglo: cambiar `async def` por `def` (FastAPI ejecuta las síncronas en su
threadpool automáticamente). Alternativa explícita: `await run_in_threadpool(...)`.

**Volver a medir.** Esa tabla antes/después va a la memoria: demuestra que se
entiende el modelo de concurrencia de FastAPI, que es diferenciador.

### 2. Timeouts y reintentos
No hay ni un `timeout=` ni un reintento en todo el backend.

- `timeout` explícito en los clientes de Replicate, DeepL y ElevenLabs.
- Reintento con **backoff exponencial y jitter** para 429 y 5xx. Máximo 3
  intentos. Los free tiers devuelven 429 constantemente; sin backoff la app
  simplemente falla.
- El reintento se registra con `logger.warning` (ya hay logging desde H1).

### 3. Límites de tamaño en subidas
Hoy `await audio.read()`, `await image.read()` y la subida de documentos cargan
el fichero entero en RAM sin comprobar nada.

- Comprobar `Content-Length` antes de leer y cortar la lectura por encima del
  máximo (lectura por trozos, no `read()` de golpe).
- Máximos sugeridos: imagen 10 MB, audio 5 MB, documento 20 MB. Configurables.
- Devolver **413** con mensaje claro, no 500.

### 4. Validación de entrada
- `AskRequest.pregunta`: añadir `max_length=500`. Hoy no tiene tope: se pueden
  mandar 2 MB de texto al LLM.
- Revisar el resto de schemas por el mismo patrón.

### 5. Candado del túnel
Los endpoints del niño son públicos **por diseño correcto** (no puede haber PIN
delante de un niño de 9 años). La protección va en otra capa:

- **Código de acceso compartido**: cabecera `X-Access-Code` comparada con
  `hmac.compare_digest` contra una variable del `.env`. El frontend lo lleva en
  su `.env`. No es autenticación fuerte; es un candado contra escaneo.
- **Rate limit por IP** (`slowapi`): distinto para `/api/ask` (generoso) y para
  `/api/generate*` (restrictivo).
- **Tope diario de generaciones de imagen** en SQLite, configurable.
- Cuando se agote el cupo: que **el personaje conteste en personaje** ("necesito
  descansar un ratito antes de la próxima aventura"). Un 429 crudo en la cara de un
  niño es un fallo de producto.

### 6. Endurecer el PIN
`admin_service` usa PBKDF2 con 200k iteraciones y sal — bien hecho. Pero un PIN
de 4 dígitos sin límite de intentos son ~10.000 peticiones: minutos.

- Contador de fallos por IP con espera creciente.
- `time.sleep(0.5)` en el camino de login (sube mucho el coste del ataque a
  cambio de nada perceptible para el adulto).
- Registrar los intentos fallidos con `logger.warning`.

### 7. Saneado de errores
`HTTPException(500, detail=f"Error al generar la respuesta: {exc}")` manda el
mensaje interno del SDK al cliente, que puede incluir URLs y fragmentos de
configuración.

- Loguear el detalle completo en servidor con un `error_id` (uuid4).
- Devolver al cliente mensaje genérico + `error_id`.
- Aplicar en los 5 routers.

### 8. Deuda menor
- `datetime.utcnow()` → `datetime.now(timezone.utc)` (10 usos).
- Quitar los comentarios obsoletos que dicen que el control de acceso admin
  "llega en el Hito 7" (`routers/apis.py`, `services/secrets_service.py`): ya
  está implementado.

## Criterios de aceptación (puerta)

- [ ] Test de concurrencia: con 2 peticiones largas en vuelo, `GET /health`
      responde en < 200 ms. **Con la medición previa documentada.**
- [ ] Todas las llamadas externas tienen `timeout`. Verificable por inspección.
- [ ] Test: subida por encima del límite → 413, y el proceso no crece en memoria.
- [ ] Test: `pregunta` de 1000 caracteres → 422.
- [ ] Test: petición sin `X-Access-Code` → 401 en los endpoints del niño.
- [ ] Test: superar el rate limit → respuesta en personaje, no traza de error.
- [ ] Test: 10 intentos de PIN fallidos → bloqueo temporal.
- [ ] Test: un error interno devuelve mensaje genérico + `error_id`, y **nada**
      del mensaje del SDK aparece en el cuerpo de la respuesta.
- [ ] `grep -rn "utcnow" backend/` devuelve 0.

## Evidencia a entregar para el OK

1. Tabla antes/después de la medición de concurrencia.
2. `pytest` en verde con los tests nuevos.
3. Informe de hito.

## Instrucción de arranque para Claude Code

> Lee `docs/PLAN.md` y `docs/plan/H2-blindaje.md`. Trabaja **sólo** en el alcance
> de H2. Empieza por el paso 1 y **mide antes de arreglar**: necesito la tabla
> antes/después. No toques nada de retrieval, prompts ni proveedores. Dame el
> plan antes de escribir código, y el INFORME DE HITO al terminar.
