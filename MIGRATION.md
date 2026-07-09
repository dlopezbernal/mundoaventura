# MIGRATION.md — Migración del frontend a Vite + React 18 + TypeScript (SPA)

> **Documento de trabajo para Claude Code.** Este archivo define la migración del
> frontend actual (Flet 0.28.3, `frontend/main.py`) a una SPA con Vite + React 18 +
> TypeScript. El backend FastAPI **no se modifica** salvo lo indicado explícitamente
> en el Hito 6.

---

## REGLAS GLOBALES (leer antes de empezar cualquier hito)

1. **Trabajo por hitos con puerta de validación (gate).** Al terminar un hito:
   - Ejecuta tú mismo las verificaciones automatizables (build, lint, curl al backend).
   - Presenta al usuario la **checklist de validación** del hito con el estado de cada punto.
   - Haz `git commit` del hito con el mensaje indicado.
   - **DETENTE.** No empieces el siguiente hito hasta que el usuario confirme
     explícitamente con algo como "OK, continúa con el hito N".
2. **Si una verificación falla**, corrígela dentro del mismo hito. Nunca arrastres
   un fallo conocido al hito siguiente.
3. **El backend es intocable** (routers, services, schemas) excepto el ajuste de CORS
   y el montaje de estáticos del Hito 6. Si crees que necesitas tocar el backend antes,
   detente y pregunta al usuario.
4. **La app Flet en `legacy/` es la referencia funcional.** Ante cualquier duda de
   comportamiento (flujo, textos, degradación de errores), consulta
   `legacy/frontend-flet/main.py` y replica su comportamiento.
5. **Idioma:** toda la UI en español (público: niños de 8–12 años). Textos de error
   amables, sin jerga técnica de cara al niño.
6. **Convenciones técnicas** (decididas por el usuario; no cambiar sin preguntar):
   - Gestor de paquetes: **npm**.
   - Estilos: **CSS puro** (CSS Modules o archivos .css por componente). Sin Tailwind, sin MUI.
   - Estado: `useState` / `useReducer` en `App`. Sin Redux ni Zustand.
   - Cliente HTTP: `fetch` nativo. Sin axios.
7. **Contrato de API (referencia, extraído de `backend/schemas/`):**

   | Método | Endpoint | Entrada | Salida (campos clave) |
   |---|---|---|---|
   | GET | `/health` | — | JSON de estado (Replicate, DeepL, ElevenLabs) |
   | POST | `/api/generate` | JSON `{personaje_id, ubicacion_id}` | `{success, personaje_id, ubicacion_id, result_png_base64}` |
   | POST | `/api/generate-on-photo` | multipart: foto + `personaje_id` | igual que `/api/generate` |
   | POST | `/api/ask` | JSON `{personaje_id, pregunta}` | `{success, personaje_id, pregunta, respuesta, origen, metodo, pregunta_traducida, distancia, fuentes[], audio_base64\|null}` |
   | POST | `/api/transcribe` | multipart: `audio` | `{texto}` |

---

## HITO 0 — Rama, reestructuración y línea base

### Prompt para Claude Code

```
Lee MIGRATION.md entero antes de hacer nada y sigue sus REGLAS GLOBALES.

Ejecuta el Hito 0:

1. Verifica que el working tree está limpio (git status). Si hay cambios sin
   commitear, detente y pregúntame.
2. Crea la rama de migración desde main:
       git checkout -b migration
3. Mueve el frontend Flet actual a legacy/ conservando el historial:
       git mv frontend legacy/frontend-flet
       git mv requirements-frontend.txt legacy/requirements-frontend.txt
4. Añade en legacy/README.md una nota breve: "Frontend original en Flet 0.28.3,
   conservado como referencia durante la migración a React. Se arranca con:
   pip install -r legacy/requirements-frontend.txt && flet run legacy/frontend-flet/main.py"
5. Comprueba que el backend sigue arrancando sin errores:
       uvicorn backend.main:app
   y que GET /health responde 200 (curl).
6. Commit: "hito 0: rama migration + frontend Flet movido a legacy/"
7. Muéstrame la checklist de validación del Hito 0 y DETENTE hasta mi confirmación.
```

### Checklist de validación (Hito 0)
- [ ] Rama `migration` creada; `main` intacta (el Flet original sigue en `main`).
- [ ] `legacy/frontend-flet/` contiene `main.py`, `api_client.py`, `personajes.py`, `ubicaciones.py`.
- [ ] `git log --follow legacy/frontend-flet/main.py` conserva el historial.
- [ ] Backend arranca y `/health` devuelve 200.
- [ ] La app Flet sigue arrancando desde su nueva ruta (prueba manual del usuario).

🛑 **GATE:** esperar confirmación del usuario.

---

## HITO 1 — Esqueleto Vite + contrato de API tipado

### Prompt para Claude Code

```
Ejecuta el Hito 1 de MIGRATION.md:

1. Crea el proyecto:
       npm create vite@latest frontend-react -- --template react-ts
       cd frontend-react && npm install
2. Crea src/api/types.ts con interfaces TypeScript que repliquen EXACTAMENTE los
   schemas Pydantic de backend/schemas/ (GenerateRequest, GenerateResponse,
   AskRequest, AskResponse con distancia: number | null y audio_base64: string | null,
   TranscribeResponse {texto: string}). Copia las descripciones como comentarios JSDoc.
3. Crea src/api/client.ts replicando las 5 funciones de
   legacy/frontend-flet/api_client.py con fetch:
       checkHealth(), generate(), generateOnPhoto(), ask(), transcribe()
   - Misma semántica de errores: una clase BackendError con mensaje amigable,
     extrayendo "detail" del JSON de error si existe (mira cómo lo hace api_client.py).
   - Timeouts equivalentes con AbortController (120 s generate/ask, 60 s transcribe,
     10 s health).
   - URL base desde import.meta.env.VITE_BACKEND_URL con fallback a "" (mismo origen).
4. Crea frontend-react/.env.example con VITE_BACKEND_URL=http://127.0.0.1:8000
   y documenta que con Colab se pone la URL del túnel.
5. Configura en vite.config.ts un proxy de desarrollo: /api y /health hacia
   http://127.0.0.1:8000 (así en dev no hay CORS).
6. Crea src/data/personajes.ts y src/data/ubicaciones.ts portando los catálogos de
   legacy/frontend-flet/personajes.py y ubicaciones.py (mismos ids, labels, emojis,
   categorías y GRUPOS). Los ids DEBEN coincidir con backend/personajes.py y
   backend/ubicaciones.py — verifícalo comparando las claves.
7. Sustituye el App.tsx de ejemplo por una página mínima con el título del proyecto
   y un botón "Probar conexión" que llame a checkHealth() y pinte el JSON o el error.
8. Verifica: npm run build sin errores de TypeScript, y con el backend arrancado el
   botón muestra el JSON de /health.
9. Commit: "hito 1: esqueleto Vite + cliente API tipado + catálogos"
10. Checklist del Hito 1 y DETENTE hasta mi confirmación.
```

### Checklist de validación (Hito 1)
- [ ] `npm run dev` arranca; `npm run build` compila sin errores TS.
- [ ] Botón "Probar conexión" muestra el JSON de `/health` (backend arrancado).
- [ ] Con el backend apagado, muestra un error amable, no un crash.
- [ ] Los ids de `src/data/*` coinciden 1:1 con los de `backend/personajes.py` y `backend/ubicaciones.py`.
- [ ] `types.ts` refleja los schemas (incluidos los nullables).

🛑 **GATE:** esperar confirmación del usuario.

---

## HITO 2 — Flujo de imagen: pasos 1, 2 y escena

### Prompt para Claude Code

```
Ejecuta el Hito 2 de MIGRATION.md:

Implementa el asistente por pasos replicando el flujo de legacy/frontend-flet/main.py:
  Paso 1: elegir PERSONAJE (agrupado por GRUPOS: Prehistóricos, Históricos, Ficticios).
  Paso 2: elegir UBICACIÓN o "Usar mi foto" (input file, id especial "__foto__").
  Paso 3: escena generada.

1. Estado del asistente en App.tsx con useReducer:
   {paso, personajeId, ubicacionId, fotoFile, escenaBase64, cargando, error}.
2. Componentes (cada uno con su .css):
   - StepBar: barra de progreso de 3 pasos con el paso activo resaltado.
   - CardCarousel: carrusel reutilizable de tarjetas (personajes y ubicaciones).
     PRIMERA VERSIÓN: grid/lista simple de tarjetas grandes con emoji + label +
     categoría, navegable con clic. El efecto coverflow se hará en el Hito 5,
     no ahora.
   - SceneView: muestra la imagen (data:image/png;base64,...) con botones
     "Empezar de nuevo" y "Cambiar de lugar".
3. Generación: al confirmar paso 2, llama a generate() o a generateOnPhoto() si
   eligió su foto. Muestra un estado de carga claro (la generación tarda varios
   segundos) y los errores BackendError en un aviso amable con botón reintentar.
4. Estética base: cabecera con degradado morado (bgcolor #FBF7FF, semilla PURPLE,
   como la app Flet), botones grandes y redondeados. Sin perfeccionismo: la paridad
   visual fina es del Hito 5.
5. Verifica compilación y flujo completo contra el backend real.
6. Commit: "hito 2: asistente de 3 pasos + generación de escena (incl. mi foto)"
7. Checklist del Hito 2 y DETENTE hasta mi confirmación.
```

### Checklist de validación (Hito 2)
- [ ] Flujo completo: personaje → ubicación → escena visible en pantalla.
- [ ] Flujo "Mi foto": subir imagen → escena sobre la foto.
- [ ] Estado de carga visible durante la generación; error del backend se muestra amable y permite reintentar.
- [ ] "Empezar de nuevo" resetea el asistente correctamente.
- [ ] Comparación lado a lado con la app Flet (`legacy/`): mismo flujo y mismos catálogos.

🛑 **GATE:** esperar confirmación del usuario.

---

## HITO 3 — Chat de texto + reproducción de la voz de respuesta

### Prompt para Claude Code

```
Ejecuta el Hito 3 de MIGRATION.md:

1. Componente Chat en el paso 3, junto a la escena:
   - Historial de burbujas (niño a la derecha, personaje a la izquierda), con el
     nombre del personaje.
   - Input de texto + botón enviar (y enviar con Enter).
   - Llama a ask(personajeId, pregunta) y añade la respuesta al historial.
   - Indicador "el personaje está pensando..." mientras espera.
2. Voz de la respuesta: si audio_base64 no es null, reprodúcela automáticamente:
       new Audio("data:audio/mpeg;base64," + audio_base64).play()
   - Guarda la referencia para poder parar el audio anterior si llega otra respuesta.
   - Botón de re-reproducir en la burbuja del personaje si esa respuesta tiene audio.
   - Si audio_base64 es null, todo sigue funcionando solo con texto (degradación,
     igual que en la app Flet).
3. Fuentes: si fuentes[] no está vacío, muéstralas plegadas bajo la respuesta
   (un desplegable "¿De dónde lo he sacado?").
4. Manejo de errores del chat: burbuja de error amable, el input no se pierde.
5. Verifica compilación y prueba end-to-end contra el backend.
6. Commit: "hito 3: chat RAG por texto + auto-play de la voz de respuesta"
7. Checklist del Hito 3 y DETENTE hasta mi confirmación.
```

### Checklist de validación (Hito 3)
- [ ] Pregunta escrita → burbuja de respuesta del personaje.
- [ ] El audio de la respuesta suena solo al llegar; el botón de re-reproducir funciona.
- [ ] Con ElevenLabs sin configurar (`audio_base64: null`), el chat de texto sigue vivo.
- [ ] Las fuentes se ven en el desplegable cuando `origen == "RAG"`.
- [ ] Un error del backend no rompe el historial ni borra el input.

🛑 **GATE:** esperar confirmación del usuario.

---

## HITO 4 — Entrada por voz (micrófono) ⚠️ hito de mayor riesgo

### Prompt para Claude Code

```
Ejecuta el Hito 4 de MIGRATION.md:

FASE A — SPIKE OBLIGATORIO (antes de escribir UI):
1. Comprueba qué produce MediaRecorder en el navegador (normalmente audio/webm;
   codecs=opus) y verifica con un clip real que POST /api/transcribe lo acepta y
   devuelve texto correcto (el backend lo reenvía a ElevenLabs Scribe).
   Hazlo con una página/función de prueba mínima, grabando 3-4 segundos.
2. Si Scribe rechaza el webm: DETENTE y preséntame las opciones (convertir a wav
   en el cliente, o aceptar y convertir en el backend) con tu recomendación.
   No elijas por tu cuenta: el backend es intocable sin mi aprobación.

FASE B — IMPLEMENTACIÓN (solo si el spike pasa):
3. Botón de micrófono junto al input del chat:
   - Pulsar: pide permiso (getUserMedia), graba y muestra estado "grabando"
     (animación/color) con opción de cancelar.
   - Soltar/pulsar de nuevo: detiene, sube el blob a transcribe(), coloca el texto
     transcrito y lo envía por el MISMO flujo del Hito 3.
4. Degradación (como la app Flet): si no hay permiso de micro, no hay dispositivo,
   o el contexto no es seguro (getUserMedia solo existe en https o localhost),
   oculta o deshabilita el micro con un tooltip claro. El chat de texto nunca
   se ve afectado.
5. Prueba en Chrome y Firefox, en localhost.
6. Commit: "hito 4: pregunta por voz (MediaRecorder → /api/transcribe)"
7. Checklist del Hito 4 y DETENTE hasta mi confirmación.
```

### Checklist de validación (Hito 4)
- [ ] Spike documentado: formato producido por el navegador y confirmación de que Scribe lo transcribe.
- [ ] Flujo completo por voz: grabar → transcribir → respuesta con texto y audio.
- [ ] Probado en Chrome y Firefox (localhost).
- [ ] Probado a través del túnel https de Colab (verificación manual del usuario).
- [ ] Denegar el permiso del micro no rompe nada; el chat de texto sigue operativo.

🛑 **GATE:** esperar confirmación del usuario.

---

## HITO 5 — Responsive, coverflow y paridad visual

### Prompt para Claude Code

```
Ejecuta el Hito 5 de MIGRATION.md:

1. Responsive con breakpoint en 760px (mismo umbral que MOVIL_MAX en la app Flet):
   - Móvil: contenido a ancho completo, carrusel sin cartas vecinas, en el paso 3
     imagen y chat apilados en vertical.
   - Escritorio: diseño actual en dos columnas.
   Usa media queries CSS; evita medir el ancho en JS salvo necesidad real.
2. Evoluciona CardCarousel al efecto coverflow de la app Flet: carta central grande,
   vecinas asomando reducidas a los lados, flechas ‹ ›, puntitos de posición.
   Hazlo con CSS transforms + transition; sin librerías de carrusel.
3. Pulido de estados: skeleton/spinner durante la generación, deshabilitar botones
   mientras hay peticiones en vuelo, foco correcto en el input del chat.
4. Repasa TODOS los textos: español, tono amable para niños, sin tecnicismos.
5. Pasada de accesibilidad básica: alt en imágenes, aria-label en botones de icono,
   navegable con teclado en los carruseles.
6. Verifica en un viewport móvil (devtools) y compila.
7. Commit: "hito 5: responsive 760px + coverflow + pulido de estados"
8. Checklist del Hito 5 y DETENTE hasta mi confirmación.
```

### Checklist de validación (Hito 5)
- [ ] En < 760px: carrusel sin vecinas, imagen y chat apilados, sin scroll horizontal.
- [ ] Coverflow funcional con flechas y puntitos, comparable al de la app Flet.
- [ ] Ningún doble envío posible (botones deshabilitados durante peticiones).
- [ ] Probado por el usuario en un móvil o tablet real.
- [ ] Checklist de paridad funcional completa contra `legacy/frontend-flet` (todas las funciones de la app Flet existen en la SPA).

🛑 **GATE:** esperar confirmación del usuario.

---

## HITO 6 — Build de producción, CORS, documentación y cierre

### Prompt para Claude Code

```
Ejecuta el Hito 6 de MIGRATION.md:

1. npm run build y verifica que dist/ funciona servido en estático
   (npm run preview) contra el backend real.
2. ÚNICO cambio permitido en el backend (backend/main.py, middleware CORS):
   - allow_credentials=False (la combinación allow_origins=["*"] +
     allow_credentials=True la rechazan los navegadores si se usan credenciales).
   - Lee los orígenes de una variable de entorno CORS_ORIGINS (lista separada por
     comas) con fallback a ["*"] para desarrollo. Documéntalo en .env.example.
3. Opcional (pregúntame antes): montar dist/ en FastAPI con StaticFiles para servir
   frontend y backend desde el mismo origen.
4. Documentación:
   - README.md: sustituye las instrucciones de arranque del frontend Flet por las
     de la SPA (npm install, npm run dev, npm run build, variable VITE_BACKEND_URL),
     y añade una sección "Frontend legacy (Flet)" apuntando a legacy/.
   - ARQUITECTURA.md: actualiza el diagrama de secuencia y la sección de voz del
     frontend (MediaRecorder + <audio> sustituyen a sounddevice/soundfile/just-playback).
5. Limpieza: .gitignore para node_modules y dist; elimina restos del scaffold de
   Vite que no se usen (logos, css de ejemplo).
6. Commit: "hito 6: build de producción + CORS configurable + docs actualizadas"
7. Presenta la checklist final. El merge de migration a main lo decide y ejecuta
   el usuario (sugerir PR). NO hagas merge tú.
```

### Checklist de validación (Hito 6)
- [ ] `npm run build` limpio; `npm run preview` funciona end-to-end (imagen, chat, voz).
- [ ] CORS configurable por entorno; comportamiento en dev intacto.
- [ ] README y ARQUITECTURA.md reflejan el nuevo frontend.
- [ ] `git checkout main` sigue mostrando el proyecto Flet original intacto.
- [ ] Decisión del usuario: merge de `migration` → `main` (vía PR) y destino final de `legacy/` (mantener o eliminar en un commit posterior).

🛑 **GATE FINAL:** la migración se da por cerrada con la confirmación del usuario.

---

## Apéndice — Estimaciones y orden de riesgo

| Hito | Estimación | Riesgo |
|---|---|---|
| 0 | 30 min | Bajo |
| 1 | 2–4 h | Bajo |
| 2 | 6–10 h | Medio |
| 3 | 3–5 h | Bajo |
| 4 | 3–6 h | **Alto** (formato de audio + https) |
| 5 | 4–8 h | Medio |
| 6 | 2–3 h | Bajo |

Punto de corte digno si aprieta la fecha: **fin del Hito 3** (SPA completa sin
entrada por voz; la voz de respuesta ya funciona).
