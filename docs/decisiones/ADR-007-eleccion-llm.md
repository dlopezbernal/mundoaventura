# ADR-007 — Elección del LLM generador (estudio comparativo)

- **Estado:** propuesta — **metodología y umbrales CONGELADOS (2026-08-02)**; tablas de
  resultados y decisión final **pendientes de ejecución** en la máquina del usuario
  (claves de pago, Ollama local y test ciego humano no disponibles en el sandbox).
- **Fecha:** 2026-08-02
- **Hito:** H6 (`feat/h6-estudio-llm`)
- **Depende de:** H3 (runner + línea base), H4 (retrieval bueno y congelable),
  H5 (`llm_service`: cambiar de proveedor es cambiar config, no código).

## Contexto

Hay que elegir el LLM generador con un **método defendible**, no con una impresión.
"Calidad" no es un número: un modelo puede clavar el tono y a la vez inventarse hechos;
otro ser impecable y hablar como un manual. Promediarlos en un "8,4/10" borra justo la
información que se necesita. Por eso se **descompone la calidad en dimensiones medibles
por separado** y solo al final se aplica una regla de decisión explícita
(**puertas primero, pesos después**).

La infraestructura de H5 hace esto barato: el retrieval se congela (fixture de H3, los
mismos chunks para los cinco modelos) y la única variable que cambia es el LLM.

## Candidatos (cinco, ni uno más)

Declarados en `evals/candidatos.yaml`.

| # | Candidato | Papel | Config |
|---|---|---|---|
| 1 | **Llama 3 8B (Replicate)** | Línea base imprescindible | `replicate` · `meta/meta-llama-3-8b-instruct` |
| 2 | **Gemini 2.0 Flash** | Favorito calidad/precio | `openai` · endpoint compat. de Google |
| 3 | **Mistral Small** | Candidato europeo (RGPD) | `openai` · `api.mistral.ai` |
| 4 | **Groq Llama-3.3-70B** | Latencia pura (LPU) | `openai` · `api.groq.com` |
| 5 | **Qwen3-4B / Gemma3-4B (Ollama)** | Fila 100 % local | `openai` · `localhost:11434` |

El candidato 5 es el que hace la tabla interesante: responde con datos a "¿y si no
hubiera internet ni presupuesto?".

**Aviso free tier (se decide conscientemente, doc H6 §2):** la defensa **no** se monta
sobre un tramo gratuito (un 429 en la presentación cuesta más que ~10 € de crédito). Y
en el tramo gratuito de Gemini, **Google puede usar las entradas para entrenar**: en una
app usada por niños eso se declara aquí y no se hereda por defecto.

## Metodología

### Control experimental (doc H6 §1)
- **Retrieval congelado:** fixture de H3, chunks idénticos para los cinco.
- **3 repeticiones/pregunta** a `temperature=0`; se reporta **media ± σ** (la σ mide el
  ruido residual del modelo alojado). **Reportar la σ** es señal directa de rigor.
- **Mismo `max_tokens`** para todos (`LLM_MAX_TOKENS`, no se toca entre corridas).

### Dimensiones y nivel de medida (doc H6 §3)
- **Nivel 1 · determinista** (gratis, en `evals/metricas.py`, ya existente): idioma
  (`lingua`), longitud, **legibilidad INFLESZ/Fernández Huerta**, roto de personaje,
  ruteo, latencia, coste. Las calcula el runner y las agrega `evals/comparar.py`.
- **Nivel 2 · juez LLM** (solo fidelidad al contexto): `evals/juez.py` (ver abajo).
- **Nivel 3 · test ciego humano** (tono y encanto): `evals/test_ciego.py`.

### El juez (Nivel 2, doc H6 §4)
Comprueba si **cada afirmación** de la respuesta está respaldada por los chunks. Dos
reglas no negociables, implementadas en `evals/juez.py`:
1. **Modelo distinto y más potente** que los candidatos (`juez:` en `candidatos.yaml`,
   por defecto `gemini-2.5-pro`) — un modelo no se juzga a sí mismo.
2. **Se valida antes de usarlo:** se puntúan **20 respuestas a mano** y se compara con su
   veredicto. **Acuerdo ≥ 85 %** ⇒ es un instrumento, se usa. **< 85 %** ⇒ es ruido con
   aspecto de dato: se descarta, se amplía el test ciego y **se declara como limitación**.
   (`juez.validar` calcula el acuerdo; el resultado va a `resultados_h6.yaml`.)

### Test ciego (Nivel 3, doc H6 §5)
20 preguntas del set dorado × los **2 finalistas**, en pares **anonimizados y con orden
aleatorizado por par** (`test_ciego.py generar` → papeleta + clave secreta). 5–8
evaluadores (**a poder ser niños de 8–12**) eligen la que preferirían para un niño.
`test_ciego.py agregar` des-anonimiza con la clave y calcula preferencia + acuerdo
inter-evaluador. Con 8×20 = **160 juicios**, suficiente para una preferencia clara.

## Puertas y pesos — **fijados el 2026-08-02, antes de ejecutar** (§7/§8)

Congelados como constante en `evals/comparar.py` (`UMBRALES`/`PESOS`, `FECHA_UMBRALES`).
Fijarlos en el código antes de ver resultados es justo lo que evita hacer trampas.

### Paso 1 — Puertas eliminatorias (quien no pasa, queda fuera)

| Puerta | Umbral | Nota |
|---|---|---|
| Responde en español | ≥ 98 % | determinista |
| Seguridad | **0** fallos en set adversarial | revisión humana del tacto |
| **Legibilidad** | **INFLESZ media ≥ 68** | ⚠️ **calibrado**, ver abajo |
| Longitud | media dentro de 15–90 palabras | determinista |
| Latencia | p95 respuesta completa ≤ 8 s | margen para Ollama local en CPU |
| Acuerdo del juez | ≥ 85 % (si no, el juez se descarta) | condiciona el Nivel 2 |
| Evaluadores del ciego | ≥ 5 (≥ 20 pares) | condiciona el Nivel 3 |

**Calibración de la puerta INFLESZ (decisión con dato, como en ADR-004/006).** El doc H6
§7 proponía "INFLESZ ≥ 80 en ≥ 90 % de respuestas". Pero la **línea base real** (Llama 3,
300 respuestas de `BASELINE.csv`) solo llega a ≥ 80 en el **25 %**, con **media 69,9**.
Aplicar la puerta literal **eliminaría a la propia línea base** (y casi con seguridad a
los cinco), dejando el estudio sin candidatos: una puerta mal calibrada, no un resultado.
Se baja la **puerta** a **media ≥ 68** (mínimo que la referencia cumple con margen) y el
**≥ 80 se conserva como OBJETIVO de mérito**, no eliminatorio: entra como columna
"% muy fácil" que **puntúa a favor** del que lee mejor en la fase de pesos. Honesto y
defendible: la puerta es el mínimo aceptable; el ideal, criterio de mérito.

### Paso 2 — Pesos entre supervivientes (según prioridades de `PLAN.md`)

| Criterio | Peso |
|---|---|
| Calidad (fidelidad del juez + preferencia humana) | **50 %** |
| Latencia (p50/p95) | **30 %** |
| Coste (€/1.000 preguntas) | **20 %** |

**Cómo se interpreta:** diferencias dentro de una σ son **empate** (entonces gana el más
estable, σ menor; y en empate persistente, el de mejor argumento de memoria —privacidad,
soberanía del dato, independencia—). Entre supervivientes, el peso elige los **2
finalistas**; el **test ciego** decide entre ellos.

## Variable oculta controlada: el prompt (mini-experimento EN vs ES, doc H6 §6)

Los prompts del proyecto están en **inglés** porque Llama 3 obedecía mejor así
(invariante "entra en inglés, sale en español"). Pasarlos idénticos a los cinco mide
"qué modelo encaja con un prompt afinado para Llama 3", no los modelos. Salida honesta
elegida: **(a) mismo prompt (inglés) para todos, declarado como limitación**, más un
**mini-experimento 2×2** que acota el sesgo: prompt EN vs ES × 2 modelos (la línea base
y un candidato fuerte). Procedimiento (sin código nuevo; el runner ya lee los prompts de
`settings_service`):

1. Corrida con los prompts EN por defecto (ya se tiene de las corridas de candidatos).
2. Traducir a español los ajustes `RAG_SYSTEM_PROMPT`/`RAG_USER_PROMPT` en la pantalla de
   config y **reindexar no hace falta** (el prompt es de generación, no de retrieval).
3. Re-correr esos 2 modelos con etiqueta `h6-<id>-promptES` y comparar INFLESZ/fidelidad.
4. Restaurar los prompts EN. Anotar la fila resultante en `docs/EVALUACION.md`.

## Tabla de resultados (5 filas × métricas, media ± σ) — **A RELLENAR tras ejecutar**

La genera `uv run python -m evals.comparar` a partir de los CSV de las 5 corridas + los
inputs de juicio de `resultados_h6.yaml`. Pegar aquí la tabla resultante.

| Candidato | esp % | INFLESZ (μ±σ) | % muy fácil | palabras (μ±σ) | ruteo % | p50/p95 (s) | €/1k | seg. | fidelidad juez % | ¿pasa puertas? |
|---|---|---|---|---|---|---|---|---|---|---|
| llama3-replicate | | | | | | | | | | |
| gemini-flash | | | | | | | | | | |
| mistral-small | | | | | | | | | | |
| groq-llama70b | | | | | | | | | | |
| ollama-local | | | | | | | | | | |

- **Validación del juez:** acuerdo ___ % (n=20) → ¿se usa? ___.
- **Test ciego:** finalistas ___ vs ___; preferencia ___ % de ___ juicios; acuerdo
  inter-evaluador ___.

## Decisión — **PENDIENTE**

Se rellena cuando estén los datos: **ganador**, y **qué se descarta y por qué** (cada
eliminado, por qué puerta o por qué peso). Regla ya fijada arriba, no se toca a posteriori.

## Limitaciones reconocidas

- **Prompt afinado para Llama 3** (inglés) igual para todos; el mini-experimento 2×2 acota
  el sesgo pero no lo elimina.
- **Coste estimado** con `tokens ≈ caracteres/4` y tarifas orientativas de
  `candidatos.yaml`; sirve para ordenar, no para facturar.
- **Semilla:** el runner fija `temperature=0`, pero no todos los proveedores garantizan
  determinismo total; de ahí las 3 repeticiones y la σ.
- Si el **juez no valida** (< 85 %), la calidad se decide solo con el test ciego humano.

## Consecuencias

- **Código:** paquete `evals/` ampliado — `candidatos.yaml` (los 5 + el juez),
  `comparar.py` (puertas→pesos), `juez.py` (fidelidad + validación), `test_ciego.py`
  (pares + agregación), `resultados_h6.yaml` (inputs de juicio). **Sin dependencia nueva**
  (`openai` ya entró en H5; `yaml`/`pyphen`/`lingua` ya estaban). No se toca `backend/`.
- **Operativa (clave única):** el secreto del endpoint openai-compatible es **uno**
  (`LLM_API_KEY`). Comparar proveedores de pago exige **cambiar la clave en el `.env`
  antes de cada corrida** (Replicate usa su propio `REPLICATE_API_TOKEN`; Ollama no pide
  clave). Documentado en la cabecera de `candidatos.yaml`.
- **`.env`:** el modelo ganador quedará como `LLM_PROVIDER`/`LLM_MODEL` por defecto en
  `settings_service` (un ajuste en caliente), y su clave en el `.env`.
- **El runner no caduca:** cuando salga un modelo nuevo, es añadir una fila a
  `candidatos.yaml`, correr y `comparar`. **La infraestructura de decisión vale más que la
  decisión** — y por eso es el entregable congelado de este hito.
