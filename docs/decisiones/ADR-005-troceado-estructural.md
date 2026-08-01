# ADR-005 — Troceado por estructura de Markdown (sección sí, prefijo no)

- **Estado:** aceptada
- **Fecha:** 2026-08-02
- **Hito:** H4.2 (`feat/h4-retrieval-chunking`)
- **Rama madre:** `feat/h4-retrieval`

## Contexto

El troceado era `RecursiveCharacterTextSplitter(800, 120)` sobre artículos Markdown,
que parte por tamaño y **tira los encabezados**. La hipótesis del plan: trocear por
secciones y **prefijar cada chunk con su ruta de encabezados** daría contexto al
embedding y procedencia real al desplegable "¿de dónde lo he sacado?".

## Opciones consideradas y medición

Backend fijo `multi-minilm`, umbral 0,80; se aísla la variable "troceado". Métrica:
recall@3 a nivel de chunk (retrieval-only, determinista).

| Troceado | chunk-recall@3 | Nota |
|---|---|---|
| recursivo (H4.1) | 81,8 % | por tamaño; sin secciones |
| estructura **con prefijo** en el texto | 80,0 % | el prefijo repetido ("Tyrannosaurus: …") DILUYE el embedding |
| estructura **sin prefijo** (ruta al metadato) | **83,6 %** | secciones limpias; ruta solo en `header_path` |

## Decisión

**Troceado por secciones de Markdown, con la ruta de encabezados en el METADATO
(`header_path`), NO prefijada en el texto embebido.** Ajuste `CHUNKING`
(`recursivo`|`estructura`, `requires_reindex`); `recursivo` reproduce H4.1/baseline.

Los límites por sección mejoran el retrieval (+1,8 pp sobre recursivo). La ruta de
encabezados NO va en el texto: alimenta la **procedencia** del chat (el chat antepone
`[Sección] …` a la fuente al mostrarla), no el embedding.

### Extra: `MOSTRAR_FUENTES` desacoplado de `DEBUG`

Enseñar al niño los fragmentos usados (desplegable "¿de dónde lo he sacado?") era un
efecto de `DEBUG`. Se separa en un flag propio `MOSTRAR_FUENTES`: mostrar la
procedencia es **pedagogía**, no depuración. Con el troceado estructural, la fuente
mostrada lleva su sección real.

## Qué se descarta y por qué

- **Prefijar el texto con la ruta (como pedía el plan):** MEDIDO peor (-1,8 pp). El
  prefijo repetido en cada chunk acerca los embeddings entre sí (todos empiezan
  igual) y resta discriminación. Se sigue la data, no la hipótesis.
- **Troceado estructural para `.txt`:** los libros de Peter Pan no tienen
  encabezados Markdown; caen al recursivo. La mejora estructural aplica a los `.md`.

## Consecuencias

- **Código:** `documentos_service._trocear` (elige recursivo/estructura por
  `CHUNKING` y extensión); `header_path` en los metadatos del chunk;
  `rag_service._recuperar_contexto` devuelve también metadatos y
  `_formatear_fuente` antepone la sección a la fuente mostrada.
- **Configuración:** ajustes `CHUNKING` y `MOSTRAR_FUENTES` (seleccionables en
  caliente; `CHUNKING` exige reindexar). `recursivo` + `minilm-en` reproduce baseline.
- **Deuda/limitación aceptada:** la mejora es modesta (+1,8 pp) y solo en `.md`; el
  valor añadido durable es la **procedencia real** en el chat.
- **Revisar en:** H4.3 (reranker) y H4.4 (sin DeepL).

## Tabla acumulada

| Métrica | Baseline | H4.1 +embeddings | H4.2 +chunking |
|---|---|---|---|
| recall@3 chunk | 78,2 % | 81,8 % | **83,6 %** |
| ruteo | 66,7 % | 70,0 % | 71,1 % |
| lat. retrieval | 191,7 ms | 27,3 ms | ~8 ms |
