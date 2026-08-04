# H6 — Estudio comparativo de LLMs

- **Rama:** `feat/h6-estudio-llm`
- **Semana:** S4, días 3–5
- **Depende de:** H3 (runner), H4 (retrieval bueno), H5 (capa de proveedor)
- **Prioridad que sirve:** #1 y #2. **Es el capítulo estrella de la memoria.**

## Objetivo

Elegir el LLM con un método defendible frase por frase, no con una impresión.

## Principio rector

**"Calidad" no es un número.** Un modelo puede clavar el tono del personaje y
además inventarse que el T-Rex convivía con humanos. Otro puede ser
factualmente impecable y hablarle a un niño de nueve años como un manual de
instrucciones. Si se promedian en un "8,4 sobre 10", se ha borrado justo la
información que se necesitaba.

El trabajo es **descomponer calidad en dimensiones medibles por separado, y
sólo al final aplicar una regla de decisión explícita**.

---

## 1. Control experimental

- **Retrieval congelado.** Se usa el fixture de H3: los mismos chunks,
  idénticos, para los cinco modelos. La única variable que cambia es el LLM.
  Es lo primero que pregunta un tribunal serio.
- **3 repeticiones por pregunta.** Con `temperature > 0` la misma pregunta da
  respuestas distintas. Se reporta **media y desviación típica**.
- **Mismo `max_tokens`** para todos.
- **Semilla fija** donde el proveedor la soporte.

---

## 2. Candidatos (cinco, ni uno más)

Probar doce multiplica el coste de análisis y diluye las conclusiones.

| # | Candidato | Papel en el estudio |
|---|---|---|
| 1 | **Llama 3 8B en Replicate** | **Línea base.** Imprescindible: sin ella no se puede demostrar mejora |
| 2 | **Gemini Flash** | Favorito calidad/precio; salida estructurada, que limpia el Evaluator |
| 3 | **Mistral Small** | Candidato europeo; argumento de RGPD para app infantil española |
| 4 | **Groq** (modelo grande disponible) | Candidato de latencia pura |
| 5 | **Qwen3-4B o Gemma 3 4B en Ollama** | Fila "100 % local": ¿cuánto se pierde por no depender de nadie? |

El candidato 5 es el que hace la tabla interesante. Responder con datos a "¿y si
no hubiera internet ni presupuesto?" vale mucho más que no haberlo mirado.

**Aviso sobre free tiers:** se desarrolla con ellos, pero **la defensa no se
monta sobre un tramo gratuito**. Un 429 en mitad de la presentación cuesta más
que los ~10 € de crédito que lo evitan. Y en el tramo gratuito de Gemini, Google
puede usar las entradas para entrenar: en una app usada por niños eso se decide
conscientemente y **se escribe en la memoria**, no se hereda por defecto.

---

## 3. Las dimensiones y cómo se mide cada una

La mayoría **no necesita un juez LLM**. Son comprobaciones deterministas,
reproducibles y gratis.

| Dimensión | Cómo se mide | Nivel |
|---|---|---|
| Responde en español | `lingua-py` sobre la respuesta | 1 · determinista |
| Longitud adecuada | nº palabras y frases contra rango objetivo | 1 · determinista |
| **Legibilidad infantil** | **Fernández Huerta / INFLESZ** (`textstat`) | 1 · determinista |
| Se mantiene en personaje | 1ª persona; ausencia de "como IA", "según el contexto", "no puedo" | 1 · determinista |
| Enrutado correcto | origen obtenido vs esperado | 1 · determinista |
| Latencia | p50 / p95, primer token y respuesta completa | 1 · determinista |
| Coste | tokens × tarifa → €/1.000 preguntas | 1 · determinista |
| **Fidelidad al contexto** | juez LLM validado | 2 · juez |
| **Tono y encanto** | test ciego con humanos | 3 · humano |
| Seguridad | set adversarial + revisión humana | 1 + 3 |

### Sobre la legibilidad (la métrica diferenciadora)

**Fernández Huerta** es la adaptación validada de Flesch al español, y su escala
**INFLESZ** está pensada para saber si un texto es comprensible para un lector
concreto. Fijar el objetivo explícito: **INFLESZ ≥ 80 (zona "muy fácil",
apropiada para lectores de primaria)**.

Esto convierte "¿le habla bien a un niño de nueve años?" de discusión subjetiva
en número defendible. Es el tipo de detalle que separa un capstone de un trabajo
de clase.

---

## 4. Nivel 2 — el juez LLM (sólo para fidelidad)

Aquí sí hace falta un juez: comprobar si toda afirmación de la respuesta está
respaldada por los chunks recuperados.

**Prompt del juez** (salida JSON obligatoria):

```
Dadas estas NOTAS y esta RESPUESTA, indica si cada afirmación de la RESPUESTA
está respaldada por las NOTAS.
Devuelve SOLO JSON: {"fundamentada": true|false,
                     "afirmaciones_sin_respaldo": ["..."],
                     "justificacion": "..."}
```

**Dos reglas no negociables:**

1. **El juez debe ser un modelo distinto y más potente que los candidatos.** Un
   modelo no puede juzgarse a sí mismo: sería autoevaluación.
2. **El juez se valida antes de usarlo.** Puntuar **a mano 20 respuestas**
   (mezcladas, de varios candidatos) y comparar con el veredicto del juez.
   - **Acuerdo ≥ 85 %** → el juez es un instrumento, se usa.
   - **Acuerdo < 85 %** → el juez es ruido con aspecto de dato. Se descarta, se
     amplía el test ciego humano y **se declara como limitación del estudio**.

Ese paso de validación es lo que separa "usé un juez LLM" de "verifiqué mi
instrumento de medida". Documentarlo aunque salga mal — sobre todo si sale mal.

---

## 5. Nivel 3 — test ciego con humanos (el diferenciador)

- Coger **20 preguntas** del set dorado.
- Generar la respuesta de los **dos finalistas** (los dos mejores tras niveles 1
  y 2).
- Presentarlas **en pares, sin identificar el modelo, en orden aleatorizado por
  par**.
- Pedir a **5–8 personas** que elijan cuál preferirían para un niño de 8–12 años.
- **Si se consigue que algunos evaluadores sean niños de ese rango, mucho
  mejor**: es una app para ellos y nadie más está cualificado para opinar sobre
  el encanto.

Con 8 personas × 20 pares = **160 juicios**, suficiente para una preferencia
clara. Media tarde de trabajo, y es la evidencia más fuerte de todo el proyecto.

**Registrar:** preferencia agregada, acuerdo entre evaluadores, y comentarios
libres (que suelen explicar el porqué mejor que el porcentaje).

---

## 6. Variables ocultas que hay que controlar

### El prompt
Los prompts del proyecto están en inglés porque **Llama 3 obedecía mejor así**.
Si se pasan idénticos a los cinco candidatos, no se está midiendo modelos: se
está midiendo *qué modelo encaja con un prompt afinado para Llama 3*.

Dos salidas honestas, elegir una y **declararla**:
- (a) Mismo prompt para todos, y se declara como limitación.
- (b) Adaptación ligera por modelo, documentando cuál recibió cada uno.

**Mini-experimento recomendado (barato):** 2×2 — prompt en inglés vs en español,
sobre dos modelos. Responde a una pregunta que el propio código dejó abierta en
un comentario, y da media página de memoria muy sólida.

### La varianza
Ya cubierta en §1: 3 repeticiones, media y σ. **Reportar la desviación**. Casi
nadie lo hace y es señal directa de rigor.

---

## 7. Regla de decisión: puertas primero, pesos después

**Nada de promedio ponderado sobre todo.** Dos pasos, en este orden.

### Paso 1 — Puertas eliminatorias

Se fijan **antes de ver los resultados**. Esto es lo importante: fijarlas
después es hacer trampas y se nota.

| Puerta | Umbral |
|---|---|
| Responde en español | ≥ 98 % de las respuestas |
| Seguridad | **0** fallos en el set adversarial |
| Legibilidad | INFLESZ dentro del rango infantil en ≥ 90 % |
| Latencia | p95 por debajo del umbral que se fije en §8 |

Quien no pasa una puerta **queda fuera**, aunque brille en el resto. Un modelo
que responde en inglés 1 de cada 20 veces no es "un candidato con una pega": es
un candidato descartado.

### Paso 2 — Ponderación entre supervivientes

Según las prioridades declaradas en `docs/PLAN.md`:

| Criterio | Peso |
|---|---|
| Calidad (fidelidad del juez + preferencia humana) | **50 %** |
| Latencia (p50 y p95) | **30 %** |
| Coste (€/1.000 preguntas) | **20 %** |

**Publicar estos pesos en la memoria ANTES de la tabla de resultados.**

### Cómo interpretar

- **Diferencias dentro de una desviación típica son empate.** Si A tiene 7,9±0,4
  y B 8,1±0,5, no hay ganador por calidad: se decide por latencia o coste.
- **Ante empate real, gana el más estable** (σ menor). El de mayor varianza dará
  la respuesta rara justo el día de la defensa.
- **Ante empate persistente, gana el que mejor argumento tenga en la memoria**
  (privacidad, ubicación de los datos, independencia de proveedor) — y se
  escribe ese razonamiento explícitamente.

---

## 8. Umbrales concretos a fijar antes de empezar

Rellenar esta tabla **el primer día del hito**, antes de ejecutar nada:

| Parámetro | Valor | Fijado el |
|---|---|---|
| p95 latencia respuesta completa | ____ s | |
| Rango de longitud de respuesta | ____ – ____ palabras | |
| Umbral INFLESZ | ≥ ____ | |
| Acuerdo mínimo del juez | ≥ 85 % | |
| Nº evaluadores del test ciego | ____ | |

---

## 9. Coste del estudio

5 modelos × ~100 preguntas × 3 repeticiones = **1.500 llamadas**. Con modelos
pequeños son unos pocos euros en total; las métricas deterministas son gratis.

El coste real es tiempo: **2–3 días**. Uno se va en el runner (que ya existe
desde H3, así que no es coste adicional de este hito) y otro en el test ciego.

---

## 10. Entregable

`docs/decisiones/ADR-00X-eleccion-llm.md` con:

1. Contexto y candidatos.
2. Metodología (control experimental, dimensiones, niveles 1/2/3).
3. Validación del juez, con su porcentaje de acuerdo.
4. Puertas y pesos, **con la fecha en que se fijaron**.
5. Tabla de resultados: 5 filas × 10 columnas, con media ± σ.
6. Resultado del test ciego.
7. Decisión, y **qué se descartó y por qué**.
8. Limitaciones reconocidas del estudio.
9. Consecuencias: qué cambia en el código y en el `.env`.

Más la sección correspondiente en `docs/EVALUACION.md`.

---

## Criterios de aceptación (puerta)

- [ ] Umbrales de §8 fijados y fechados **antes** de la primera ejecución.
- [ ] Los 5 candidatos ejecutados con retrieval congelado y 3 repeticiones.
- [ ] Juez validado contra 20 respuestas puntuadas a mano, con el % de acuerdo
      documentado (se acepte o se descarte el juez).
- [ ] Test ciego con ≥ 5 evaluadores y ≥ 20 pares.
- [ ] Tabla completa con media ± σ en todas las métricas.
- [ ] Puertas aplicadas antes que los pesos, y documentado en ese orden.
- [ ] ADR de decisión escrito y firmado.
- [ ] El modelo ganador queda configurado por defecto en `settings_service`.
- [ ] El runner se puede reejecutar con un solo comando y un cambio de string.

## Evidencia a entregar para el OK

1. La tabla de resultados completa.
2. El ADR de decisión.
3. Los datos crudos del test ciego.
4. Informe de hito.

## Lo que queda después

**El runner no caduca.** Cuando dentro de tres meses salga un modelo nuevo, es
cambiar un string y ejecutar. **La infraestructura de decisión vale más que la
decisión**, y eso también se dice en la memoria.

## Instrucción de arranque para Claude Code

> Lee `docs/PLAN.md`, `docs/plan/H6-estudio-llm.md` y `docs/EVALUACION.md`.
> Empieza rellenando la tabla de umbrales de §8 y **no ejecutes nada hasta que
> yo confirme esos valores**. Usa el modo de retrieval congelado del runner.
> El test ciego de §5 lo organizo yo: tú prepara los pares anonimizados y
> aleatorizados en un fichero, y el script que agregue los resultados. Dame el
> plan antes de escribir código.
