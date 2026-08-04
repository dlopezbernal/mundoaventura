# H10 — Congelación, documentación y defensa

- **Rama:** `docs/h10-memoria`
- **Semana:** S6 (semana completa)
- **Depende de:** todos los anteriores
- **Prioridad que sirve:** #1

## Regla de la semana

> **No se toca `backend/` ni `frontend-react/src/`. Sólo documentación.**

Esta regla no se negocia. Un refactor a medias la víspera puntúa peor que el
sistema anterior con evidencia. Si aparece un bug crítico, se documenta como
limitación conocida; sólo se arregla si impide la demo.

## Tareas

### 1. Reorganización documental
Ejecutar `docs/plan/REORGANIZACION-DOCS.md` por completo.

### 2. Cierre de ADRs
Revisar que existe un ADR por cada decisión relevante, y que todos tienen su
sección de "qué se descartó y por qué". Un ADR sin alternativas descartadas no
es un ADR: es una descripción.

ADRs mínimos esperados al final del proyecto:

| # | Decisión | Hito |
|---|---|---|
| 001 | Arquitectura híbrida: percepción local, generación en nube | H0/H4 |
| 002 | Embeddings multilingües con fastembed (y no sentence-transformers) | H4.1 |
| 003 | Troceado por encabezados de Markdown | H4.2 |
| 004 | Reranker en lugar del Evaluator LLM | H4.3 |
| 005 | Retirada de DeepL del camino crítico | H4.4 |
| 006 | Capa de proveedor compatible con OpenAI | H5 |
| 007 | Elección del LLM (el grande) | H6 |
| 008 | STT local con faster-whisper | H7 |
| 009 | Mantener ElevenLabs para TTS | H7/H8 |
| 010 | Streaming SSE frase a frase | H8 |

### 3. `docs/EVALUACION.md` final
Metodología completa, línea base, progresión medida hito a hito, tabla del
estudio de LLMs, resultados del test ciego, y **limitaciones reconocidas**.

El apartado de limitaciones no es una debilidad: un tribunal valora mucho más
"sabemos qué no hemos podido demostrar y por qué" que un informe sin fisuras.

### 4. Verificación de veracidad de los comentarios
El repo tiene comentarios didácticos extensos, y hoy **hay comentarios
obsoletos** (p. ej. los que dicen que el control de acceso admin "llega en el
Hito 7" cuando ya está puesto). Pasada completa: un comentario que miente es
peor que no tenerlo, y hace dudar del resto.

### 5. Ensayo de la defensa
- Guion de demo de 5 minutos, con el orden exacto de clics.
- **Plan B para cada paso**: sin internet (Ollama + Kokoro), sin GPU (STT en
  CPU), sin cuota (claves de pago listas).
- **Ensayo completo con el túnel levantado**, no en localhost.
- Preguntas previsibles del tribunal y su respuesta preparada:
  - ¿Por qué ese LLM y no otro? → ADR 007
  - ¿Cómo sabéis que ha mejorado? → línea base + tabla de progresión
  - ¿Qué pasa con los datos de los niños? → `docs/PRIVACIDAD.md`
  - ¿Por qué no usasteis un framework de agentes? → decisión consciente, §6 del PLAN
  - ¿Qué haríais con más tiempo? → sección de trabajo futuro

### 6. Trabajo futuro
Sección honesta: lo que se recortó (con el motivo), lo que se descartó
conscientemente, y lo que se haría en un despliegue en servidor.

## Criterios de aceptación

- [ ] Estructura documental final aplicada.
- [ ] Todos los ADRs escritos y enlazados desde `docs/DECISIONES.md`.
- [ ] `docs/EVALUACION.md` completo, con limitaciones.
- [ ] Cero comentarios obsoletos en el código.
- [ ] Demo ensayada ≥ 2 veces con el túnel, con plan B probado.
- [ ] `README.md` permite a un tercero clonar y arrancar sin ayuda.
