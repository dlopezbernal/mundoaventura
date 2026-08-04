# ADR-003 — Metodología de evaluación: métricas deterministas + retrieval congelado

- **Estado:** aceptada
- **Fecha:** 2026-08-01
- **Hito:** H3
- **Rama:** `feat/h3-banco-pruebas`

## Contexto

A partir de H4 hay que decidir cambios de retrieval, prompts y modelos. Sin una
forma objetiva de medir, esas decisiones son opinión. Hace falta un instrumento que
convierta "creo que mejoró" en una tabla comparable, ejecutable en cada cambio.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| A. Juicio humano ad-hoc por cambio | Barato al inicio | No reproducible, no comparable, no escala a decenas de cambios |
| B. Juez LLM que puntúa cada respuesta | Capta matices | Cuesta dinero por corrida, es no determinista, y él mismo hay que validarlo (H6) |
| C. Métricas DETERMINISTAS (legibilidad, idioma, recall@3, ruteo, roto de personaje) sobre un set dorado, con retrieval congelado para aislar el generador | Gratis, reproducible, ejecutable en cada commit; separa retriever de generador | No capta "calidad" subjetiva; el tacto se sigue juzgando a mano |

## Medición

Ver `docs/EVALUACION.md` para la línea base (100 preguntas × 3 reps). La decisión de
método no se "mide"; se justifica por reproducibilidad y coste: las métricas
deterministas dan el mismo número ante la misma entrada (test en `tests/test_evals.py`).

## Decisión

**Opción C.** Métricas deterministas sobre un set dorado en español infantil real,
con el runner ejecutando cada pregunta 3 veces a `temperature=0` (media ± σ) y un
**fixture de retrieval congelado** para comparar generadores sin ruido del retriever.
El juez LLM se pospone a H6 (y allí se validará contra humano antes de fiarse de él).

Detalles de implementación que son decisiones en sí mismas:
- **Legibilidad a mano (pyphen), no `textstat`:** textstat arrastra `nltk`/`regex`
  y no aporta sobre las dos fórmulas españolas (Szigriszt-Pazos/INFLESZ y Fernández
  Huerta); escribirlas explícitas es más transparente y más ligero.
- **El runner reutiliza `rag_service` sin tocarlo:** orquesta sus funciones en
  solo-lectura. H3 no puede cambiar el pipeline, y así la evaluación mide el sistema
  real, no una copia que podría divergir.
- **Acierto de RUTEO (RAG vs no-RAG), no del string exacto de origen:** el reparto
  GENERAL/SIN_INFO depende de un flag de config; ambos son "no fundamentado".

## Qué se descarta y por qué

- **Juez LLM ya (B):** introduce coste y no-determinismo en el instrumento base, y
  usar un juez sin validarlo es circular. Se deja para H6, con validación previa.
- **Recall a nivel de fragmento:** habría dado una métrica más fina, pero requiere
  verdad de referencia por chunk; con 1–2 ficheros por personaje el recall@3 a nivel
  de fichero sale ~100 % (poco discriminante). Se acepta como limitación declarada.
- **Objetivo de legibilidad INFLESZ ≥ 80** ("muy fácil", primaria): se fija como
  meta explícita para que "¿le habla bien a un niño?" sea un número, no una opinión.

## Consecuencias

- **Código:** paquete `evals/` (esquema, sets YAML, `metricas.py`, `runner.py`,
  fixture congelado). Dependencias nuevas: `lingua-language-detector` (idioma
  offline) y `pyphen` (sílabas). Tests deterministas en CI.
- **Configuración/`.env`:** sin cambios (el runner lee la config vigente y la archiva
  junto a cada corrida).
- **Deuda/limitación aceptada:** recall a nivel de fichero; el tacto se juzga a mano;
  determinismo sujeto al LLM alojado (por eso se reporta σ).
- **Revisar si:** se añaden muchos documentos por personaje (mejoraría el recall como
  métrica) o cuando H6 valide un juez LLM (añadiría una métrica de calidad subjetiva).
