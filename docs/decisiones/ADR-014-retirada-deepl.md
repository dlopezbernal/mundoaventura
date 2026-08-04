# ADR-014 — Retirar DeepL del camino crítico — DESCARTADA con datos

- **Estado:** **descartada** (la hipótesis se midió y se rechazó; DeepL se mantiene)
- **Fecha:** 2026-08-02
- **Hito:** H4.4 (`feat/h4-retrieval`)
- **Rama:** `feat/h4-retrieval`

## Contexto

DeepL es una **dependencia obligatoria**: cada pregunta se traduce ES→EN antes del retrieval, y
gestionar documentos también pasa por su API (detección de idioma). Tras montar la pila
multilingüe del Hito 4 (embeddings multilingües [ADR-004](ADR-004-embeddings-multilingues.md) +
reranker [ADR-006](ADR-006-reranker.md)), surge una hipótesis razonable: quizá esos modelos
**embeben el español directamente** lo bastante bien como para **consultar en español** y
**eliminar DeepL** del camino crítico — una dependencia externa menos, una llamada de red menos.
Antes de asumirlo, se mide.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| **A. Quitar DeepL, consultar en español directo** | Una dependencia y una llamada de red menos | **Hay que medir** que el retrieval no empeora |
| **B. Mantener DeepL (traducir la pregunta ES→EN)** | Es la línea base ya medida y buena | Dependencia externa obligatoria, coste de cuota |

## Medición

Corrida **retrieval-only**, misma colección y mismo reranker, cambiando solo la vía de consulta
(español directo vs. traducir a inglés):

| Métrica | Con DeepL (ES→EN) | Español directo | Δ |
|---|---|---|---|
| Recall de chunk | **90,9 %** | 85,5 % | **−5,4** |
| Acierto de ruteo | **82,2 %** | 71,1 % | **−11,1** |

El español directo **regresa** el retrieval de forma clara. Motivo: el corpus es inglés
(Wikipedia), así que traducir la pregunta la mantiene **monolingüe EN-EN** (casa mejor que un
emparejamiento cross-lingual ES→EN), y DeepL además **normaliza las faltas** del español
infantil real. El argumento de latencia tampoco sostiene la retirada: con el reranker activo
(~665 ms) dominando el retrieval, la llamada a DeepL (~150 ms) es ruido a su lado.

## Decisión

**Se mantiene DeepL.** La hipótesis de retirarlo queda **descartada por los datos**. H4 se
congela en H4.3 (reranker), sin H4.4.

## Qué se descarta y por qué

Se descarta **la retirada de DeepL**, no DeepL. El dato manda por encima de la intuición de
"menos dependencias es mejor": aquí, menos dependencias significaba **−5,4 recall y −11,1
ruteo**, un precio que ninguna simplificación arquitectónica justifica en la prioridad #2
(calidad de las respuestas) del proyecto.

## Consecuencias

- El pipeline sigue con la invariante **"entra en inglés, sale en español"**: se traduce la
  pregunta ES→EN y la base de conocimiento permanece en inglés.
- DeepL sigue siendo un requisito duro, tanto para el chat como para gestionar documentos.
- **A revisar si:** el corpus pasara a estar **en español** (retrieval monolingüe ES-ES). En ese
  escenario, consultar en español directo sí podría igualar o superar, y la retirada de DeepL
  volvería a estar sobre la mesa. Es **trabajo futuro**, no deuda.
