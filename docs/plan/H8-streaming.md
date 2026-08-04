# H8 — Streaming y latencia percibida

- **Rama:** `feat/h8-streaming`
- **Semana:** S5, días 3–4
- **Depende de:** H5 (`completar_streaming`), H7
- **Prioridad que sirve:** #3

## Objetivo

Que el personaje **empiece a hablar mientras sigue pensando**, en vez de que el
niño espere en blanco a que termine todo.

## El problema

Hoy la cadena es estrictamente secuencial y el niño no oye nada hasta el final:
LLM completo → TTS completo → base64 (+33 % de tamaño) → JSON → reproducir.

| Etapa | Hoy | Objetivo |
|---|---|---|
| STT | 1–2 s (Scribe) | ~0,3 s (local, H7) |
| Traducción | 0,2–0,4 s | eliminada (H4) |
| Retrieval + Evaluator | 0,1 s + 1–2 s (juez LLM) | ~0,1 s (reranker, H4) |
| LLM | 2–5 s + arranque en frío | primer token ~0,3 s |
| TTS | 1–2 s (audio completo) | primera frase ~0,5 s |
| **Percibida** | **~7–12 s** | **~1,5–2 s** |

Ese salto sale casi entero de **quitar etapas serializadas**, no de pagar más.

## Tareas

### 1. SSE en `/api/ask`
- Endpoint que emita eventos: `token`, `fuentes`, `audio_chunk`, `fin`.
- Mantener el endpoint JSON actual para compatibilidad y para el runner.

### 2. Streaming de tokens del LLM
Usar `llm_service.completar_streaming()` (creado en H5).

### 3. TTS por frases
- Acumular tokens hasta cerrar frase (`.`, `?`, `!`).
- Lanzar el TTS de esa frase mientras el LLM sigue generando.
- Enviar el audio por el mismo canal SSE.
- Reproducir en el frontend encolando los fragmentos.

### 4. Caché de audio en disco
`(voz_id, modelo_tts, texto) → mp3` en disco, con hash como clave.

Los niños repiten preguntas, y las frases fijas (`MENSAJE_SIN_INFORMACION`,
`FRASE_PRUEBA_VOZ`) se re-sintetizan enteras cada vez. Es dinero regalado.

### 5. Frontend
- Renderizado incremental del texto en `Chat.tsx`.
- Cola de reproducción de audio.
- Indicador de "pensando" que desaparece con el primer token.

### 6. Imagen (mejora aparte, barata)
`result_png_base64` con PNG 16:9 son varios MB, +33 % por base64, dentro de un
JSON. Cambiar `IMG_OUTPUT_FORMAT` a `webp` por defecto, y valorar devolver una
URL servida por el backend en vez de incrustar los bytes.

## Criterios de aceptación (puerta)

- [ ] Primer token en pantalla en **< 1 s** desde el envío.
- [ ] Primera sílaba de audio en **< 1,5 s**.
- [ ] Tabla p50/p95 antes y después, medida con el runner.
- [ ] La caché de TTS reduce el coste medido en preguntas repetidas.
- [ ] El endpoint JSON antiguo sigue funcionando (el runner lo usa).
- [ ] Degradación elegante: si el TTS falla a media respuesta, el texto sigue.

## Riesgo y plan B

Si a mitad de S5 no hay primer token funcionando: **recortar a streaming de
texto solamente** (lo más visible y lo más barato) y dejar el TTS por frases
documentado como trabajo futuro. No arrastrar esto a la semana de congelación.

## Instrucción de arranque para Claude Code

> Lee `docs/PLAN.md` y `docs/plan/H8-streaming.md`. Implementa en el orden de
> §1→§5. **No rompas el endpoint JSON existente**: el runner depende de él.
> Mide con el runner antes y después. Dame el plan antes de escribir código.
