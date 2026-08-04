# Guion de defensa — demo de 5 minutos

Orden exacto de clics para la demostración, con un **plan B por cada paso** y las
**preguntas previsibles del tribunal** con su respuesta preparada. El trabajo futuro está en
[`TRABAJO-FUTURO.md`](TRABAJO-FUTURO.md).

> **Regla de oro del ensayo:** ensayar **con el túnel levantado** (ngrok/Colab), no en
> localhost. Lo que funciona en `localhost:5173` puede fallar por CORS, contexto no seguro
> (micro), o el candado del túnel. Ensayar ≥ 2 veces de principio a fin **antes** de la defensa.

## Preparación (antes de entrar en la sala)

- [ ] Backend arrancado y `GET /health` en verde: `token_configurado: true`, `deepl_ok: true`,
      `elevenlabs_ok: true`.
- [ ] Índice del RAG construido (`uv run python -m backend.ingest`) — sin esto, el chat no
      responde.
- [ ] Túnel levantado; `VITE_BACKEND_URL` (y `VITE_ACCESS_CODE` si hay candado) apuntando a él.
- [ ] Una cuenta de familia ya creada y un perfil de niño (para no gastar tiempo en el alta).
- [ ] Escena de reserva ya generada por si la generación de imagen tarda o falla.
- [ ] **Claves de pago mínimas cargadas** (Replicate/ElevenLabs) para no depender del free tier
      durante la defensa (~10 € de saldo compran tranquilidad).
- [ ] Plan B "sin internet" probado al menos una vez (Ollama + Kokoro + STT local arrancan).

## El guion (5 minutos)

| # | Acción (clic exacto) | Qué se enseña | Tiempo |
|---|---|---|---|
| 1 | Abrir la URL del túnel → **login de familia** (email + contraseña) | La app va detrás de una cuenta; no es anónima (RGPD) | 0:20 |
| 2 | Pantalla **"¿Quién juega?"** → elegir un perfil de niño | Multi-perfil; el chat se personaliza por nombre/sexo | 0:20 |
| 3 | **Elegir un personaje** en el carrusel (p. ej. T-Rex) | Catálogo desde la BBDD; UI de niño | 0:20 |
| 4 | **Elegir un lugar** (p. ej. laboratorio) → **Siguiente** | Combinación libre lugar × personaje | 0:20 |
| 5 | Ver cómo **la escena se genera sola** (animación "Creando…") | Generación de imagen en la nube (Replicate/FLUX) | 0:40 |
| 6 | Escribir una pregunta **fundamentada** ("¿qué comías?") | Respuesta **RAG en streaming**, palabra a palabra + voz | 0:50 |
| 7 | Hacer una pregunta **fuera de dominio** ("¿cuánto es 2+2?") | El personaje no alucina anclado: RAG vs GENERAL/SIN_INFO | 0:30 |
| 8 | Usar el **micrófono** → hablar → confirmar "¿has dicho esto?" | Entrada por voz (STT) + paso de confirmación | 0:40 |
| 9 | (Opcional) 🛡️ **Admin** → Personajes → Documentos | Configuración sin código; base de conocimiento del RAG | 0:40 |

**Cierre (20 s):** "Todo lo pesado corre en la nube; lo que toca los datos del menor —voz,
preguntas— puede correr en local. Cada mejora está medida contra una línea base."

## Plan B por paso

| Si falla… | Síntoma | Plan B |
|---|---|---|
| **Internet / la nube** | El LLM o el TTS no responden | **Modo local total:** `LLM_PROVIDER=openai` + `LLM_BASE_URL=http://localhost:11434/v1` (**Ollama**), TTS local (**Kokoro**), `STT_PROVIDER=local`. Se cambia en 🛡️ Admin → Sistema, sin reiniciar |
| **GPU** (STT local no arranca) | Error de DLL cuBLAS/cuDNN al transcribir | `STT_LOCAL_DEVICE=cpu` (con `int8`) — más lento pero funciona; o `STT_PROVIDER=elevenlabs` (nube). El **fallback a nube ya es automático** |
| **Cuota / free tier** | 429 de Replicate/ElevenLabs | **Claves de pago** ya cargadas en el `.env`. El rate limit responde "en personaje", nunca un 429 crudo al niño |
| **Generación de imagen** | La escena tarda demasiado o falla | Usar la **escena de reserva** ya generada; seguir con el chat (el chat no depende de la imagen) |
| **Micrófono** | `getUserMedia` no disponible / permiso denegado | El micro se deshabilita solo con aviso; **seguir por texto** (el chat de texto es equivalente) |
| **DeepL** | El chat devuelve error de traducción | Verificar `DEEPL_API_KEY` en `/health` antes de empezar; sin plan B en caliente (es obligatorio) → por eso está en el checklist de preparación |

## Preguntas previsibles del tribunal

**¿Por qué ese LLM y no otro?**
→ Se eligió con método, no por moda: **puertas primero** (seguridad 0 fallos, idioma, legibilidad,
latencia), **pesos después** (calidad 50 / latencia 30 / coste 20), y un **test ciego humano**
para desempatar finalistas. Ganó `groq-llama70b`. Detalle en el
[ADR-007](decisiones/ADR-007-eleccion-llm.md) y [`EVALUACION.md §9–10`](EVALUACION.md).

**¿Cómo sabéis que ha mejorado?**
→ Hay una **línea base inmutable** (`BASELINE.csv`) y cada cambio se compara contra ella. El
retrieval subió de **78,2 % a 90,9 %** de recall de chunk y el ruteo de **66,7 % a 82,2 %**.
Tabla de progresión en [`EVALUACION.md §8, §11`](EVALUACION.md).

**¿Qué pasa con los datos de los niños?**
→ Arquitectura híbrida: **la voz y las preguntas del menor pueden procesarse en local** (STT
local, embeddings y reranker en CPU); la foto **no se persiste** (solo memoria). Cuentas de
familia con consentimiento parental. Todo en [`PRIVACIDAD.md`](PRIVACIDAD.md) y el
[ADR-011](decisiones/ADR-011-arquitectura-hibrida.md).

**¿Por qué no usasteis un framework de agentes (LangGraph, etc.)?**
→ Decisión **consciente**: el Evaluator se escribió a mano, es simple, está medido y se defiende.
Un framework de orquestación añadiría dependencia y opacidad sin resolver un problema que
tenemos. Ver `PLAN.md §6` (fuera de alcance).

**¿Qué haríais con más tiempo?**
→ [`TRABAJO-FUTURO.md`](TRABAJO-FUTURO.md): verdad de referencia a nivel de chunk más rica,
validar el juez LLM (hoy limitación declarada), corpus en español (reabriría la retirada de
DeepL, [ADR-014](decisiones/ADR-014-retirada-deepl.md)), TTS local de calidad.

**¿Y si os preguntan por una limitación?**
→ No esconderla. El **juez LLM no se validó** (< 85 % de acuerdo), así que el desempate lo hizo
el **test ciego humano**; el **recall a nivel de fichero está saturado**, por eso gobierna el de
chunk. Reconocerlas puntúa más que un informe sin fisuras. Lista completa en
[`EVALUACION.md §12`](EVALUACION.md).
