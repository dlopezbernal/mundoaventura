# PLAN DE TRABAJO — 6 semanas hasta la entrega

Documento maestro. Cada hito tiene su propio fichero en `docs/plan/`.

> **Documento histórico: es el plan tal y como se declaró AL EMPEZAR, y se conserva sin
> reescribir.** Ese es justamente su valor metodológico: las prioridades del §0 se fijaron
> antes de conocer los resultados y no se reordenaron después para justificarlos. Por eso
> hay afirmaciones que hoy ya no describen el proyecto — la más visible, el §1, que dice que
> el despliegue es "un túnel puntual (Colab/ngrok)" y "**no** un despliegue permanente en
> internet": desde el 2026-08-05 la app corre en `chatmundoaventura.com`.
>
> Para el **estado final** ve a [`ARQUITECTURA.md`](ARQUITECTURA.md) (qué es hoy),
> [`EVALUACION.md`](EVALUACION.md) (qué se midió) y
> [`TRABAJO-FUTURO.md`](TRABAJO-FUTURO.md) (qué falta).

---

## 0. Prioridades declaradas (no cambian sin acuerdo explícito)

1. **Nota del capstone: buenas prácticas de ingeniería**
2. Calidad de las respuestas
3. Latencia percibida por el niño
4. Coste cero / free tiers

Estas prioridades son la regla de desempate cuando haya que recortar alcance.
Se declaran **antes** de empezar, y no se reordenan a posteriori para justificar
un resultado.

## 1. Contexto de ejecución

- **Hardware de desarrollo y demo:** Windows 11, 16 GB RAM, GPU 6 GB VRAM.
- **Despliegue:** túnel puntual (Colab / ngrok) para pruebas y defensa. **No** es
  un despliegue permanente en internet, pero **sí** es una URL pública mientras
  está levantada: se protege como tal (ver H2).
- **Escalado futuro:** si el proyecto crece, servidor en la nube. El diseño no
  debe impedirlo, pero **no se optimiza para ello ahora**.

## 2. Regla arquitectónica que gobierna todas las decisiones de IA

> **Los modelos pequeños de percepción y recuperación van en local. Los modelos
> generativos grandes van en la nube.**

| Pieza | Dónde | Motivo |
|---|---|---|
| Embeddings | Local (CPU, ONNX) | 120M–570M par.; calidad equivalente a API; sin torch |
| Reranker | Local (CPU, ONNX) | 568M par.; quita una llamada de red del camino crítico |
| STT | Local (GPU, ~1,5 GB VRAM) | Gratis, rápido, y **la voz del niño no sale del PC** |
| LLM | Nube | Un 4B cuantizado (lo que cabe en 6 GB) no da la calidad necesaria |
| TTS | Nube (ElevenLabs) | Local en español es notablemente peor; es el producto |
| Imagen | Nube (Replicate) | Generar en 6 GB es lento e inviable para demo |

Efecto secundario clave para la memoria: **toda la voz y todo el historial de
preguntas del menor se procesan localmente**. Eso es el eje del capítulo de
privacidad/RGPD, no una nota al pie.

---

## 3. Calendario

| Semana | Hitos | Rama(s) |
|---|---|---|
| **S1** | H1 Andamiaje · H2 Blindaje operativo | `feat/h1-andamiaje`, `feat/h2-blindaje` |
| **S2** | H3 Banco de pruebas + línea base | `feat/h3-banco-pruebas` |
| **S3** | H4 Retrieval (4 sub-hitos medidos) | `feat/h4-retrieval-*` |
| **S4** | H5 Capa de proveedor · H6 Estudio comparativo de LLMs | `feat/h5-capa-llm`, `feat/h6-estudio-llm` |
| **S5** | H7 STT local · H8 Streaming · H9 Seguridad infantil | `feat/h7-stt-local`, `feat/h8-streaming`, `feat/h9-seguridad-infantil` |
| **S6** | **CONGELACIÓN** · H10 Documentación, ADRs, memoria, ensayo | `docs/h10-memoria` |

**Congelación de código: final de S5.** En S6 no se toca `backend/` ni
`frontend-react/src/`. Sólo documentación. Esta regla no se negocia: un refactor
a medias la víspera puntúa peor que el sistema anterior con evidencia.

---

## 4. Reglas de trabajo

### Ramas
- Una rama por hito: `feat/hN-nombre`. Se parte siempre de `dev` actualizada.
- **No se abre la rama del hito N+1 hasta que el hito N tiene el OK explícito.**
- Merge a `dev` sólo tras el OK. Nunca merge directo a `main`.
- Los sub-hitos de H4 son ramas propias que se mergean a `feat/h4-retrieval`.

### Commits
- Convención: `tipo(ámbito): descripción` — `feat`, `fix`, `refactor`, `test`,
  `docs`, `chore`, `perf`.
- Un commit por unidad lógica. Nada de "varios cambios".
- Cualquier commit que cambie comportamiento de IA lleva su ADR asociado.

### Definición de HECHO (aplica a todos los hitos)
Un hito está hecho cuando **todo** esto es cierto:
1. Los criterios de aceptación del fichero del hito se cumplen y son verificables.
2. `ruff check` y `ruff format --check` pasan sin errores.
3. `pytest` pasa en verde y la cobertura no baja respecto a la rama anterior.
4. El CI de GitHub Actions está verde.
5. La documentación afectada está actualizada (incluido `CLAUDE.md`).
6. No quedan comentarios obsoletos ni `TODO` sin ticket en el código tocado.

### Protocolo de puerta (OK del responsable)
Al terminar un hito, Claude Code produce un **INFORME DE HITO** con esta forma:

```
## Informe de hito HN — <nombre>
- Rama: feat/hN-...
- Commits: <n>, ficheros tocados: <n>
- Criterios de aceptación: [tabla criterio → cumplido sí/no → evidencia]
- Mediciones antes/después: [tabla, si aplica]
- Decisiones tomadas y ADRs generados: [lista]
- Desviaciones respecto al plan y por qué: [lista]
- Riesgos abiertos / deuda introducida: [lista]
- Qué NO se ha hecho y queda para otro hito: [lista]
```

**Sin ese informe y sin el OK escrito, no se empieza el siguiente hito.**

---

## 5. Cómo usar esto con Claude Code

### Protocolo de sesión
1. Una sesión = un hito (o un sub-hito). Nunca dos.
2. Abrir la sesión con: *"Lee `docs/plan/HN-....md` y `docs/PLAN.md`. Trabaja
   sólo en el alcance de ese fichero. Antes de escribir código, devuélveme el
   plan de ejecución paso a paso y espera mi confirmación."*
3. Exigir **el plan antes que el código**. Si el plan se sale del alcance del
   hito, corregirlo ahí, no después.
4. Al terminar: pedir el INFORME DE HITO en el formato de arriba.

### Reglas que se le dan a Claude Code
- **No tocar ficheros fuera del alcance declarado del hito.** Si cree que hace
  falta, lo propone y espera; no lo hace por su cuenta.
- **Tests primero** en todo lo que sea refactor. El criterio de "terminado" debe
  ser objetivo (tests en verde), no la aprobación subjetiva del humano.
- **No introducir dependencias nuevas** sin justificarlo y anotarlo en el ADR.
- **No reescribir el frontend**, no migrar de base vectorial, no meter LangGraph,
  no añadir orquestación de contenedores. Ver §6.
- Mantener el estilo de comentarios didácticos existente, **pero verificando que
  lo que dicen es cierto** (hay comentarios obsoletos hoy en el repo).

### Mantenimiento de `CLAUDE.md`
`CLAUDE.md` describe la arquitectura **actual**. Cada hito que cambie la
arquitectura debe actualizarlo en el mismo commit. Un `CLAUDE.md` desactualizado
hace que Claude Code trabaje contra un mapa equivocado, y es la causa número uno
de refactores que se van de madre.

---

## 6. Fuera de alcance (decisión consciente, se documenta como tal)

No se hace, aunque sea tentador:

- Reescribir el frontend React. Funciona y no es donde se evalúa el proyecto.
- Migrar de ChromaDB a Qdrant/pgvector. Chroma sobra para este volumen.
- Introducir LangGraph. El Evaluator se escribió a mano **a propósito** y está
  documentado; eso es criterio, se defiende, no se deshace.
- Docker Compose / Kubernetes. Un `Dockerfile` simple para reproducibilidad, sí;
  orquestación, no.
- Perseguir el modelo más nuevo del mes. Lo que puntúa es el **método** de
  elección, no el nombre del modelo.
- Generación de imágenes en local.

---

## 7. Riesgos y planes B

| Riesgo | Señal temprana | Plan B |
|---|---|---|
| H4 (retrieval) se alarga | No hay mejora medida al final de S3 | Congelar en el mejor sub-hito logrado, documentar el resto como trabajo futuro |
| `faster-whisper` no arranca en Windows (cuBLAS/cuDNN) | Más de medio día peleando DLLs | Caer a `int8` en CPU (más lento pero funciona) o a STT en nube; documentar |
| El juez LLM no valida (<85% acuerdo con humano) | Fase de validación de H6 | Prescindir del juez, ampliar el test ciego humano y declararlo como limitación |
| Free tier devuelve 429 durante la defensa | 429 en pruebas de S4 | **Claves de pago mínimas para la defensa.** ~10 € compran tranquilidad |
| Se llega a S5 con H6 sin cerrar | Fin de S4 sin ganador | Elegir por criterios deterministas (sin test ciego) y documentar la limitación |
| El streaming (H8) se complica | Mitad de S5 sin primer token | Recortar a streaming de texto solamente; TTS por frases como trabajo futuro |

---

## 8. Estructura documental objetivo

Ver `docs/plan/REORGANIZACION-DOCS.md`. Resumen:

```
README.md              → cómo se usa y cómo se instala (sólo eso)
docs/ARQUITECTURA.md   → diseño del sistema actual
docs/DECISIONES.md     → índice de ADRs
docs/decisiones/       → un ADR por decisión relevante
docs/EVALUACION.md     → metodología y resultados de las mediciones
docs/ANEXO-DIDACTICO.md→ el material explicativo actual (qué es RAG, etc.)
CLAUDE.md              → contexto operativo para Claude Code
docs/PLAN.md + plan/   → este plan (se archiva tras la entrega)
```
