# H5 — Capa de proveedor de LLM

- **Rama:** `feat/h5-capa-llm`
- **Semana:** S4, días 1–2
- **Depende de:** H4 con OK
- **Prioridad que sirve:** #1 (desacoplamiento) — es el habilitador de H6

## Objetivo

Desacoplar el código del proveedor de LLM para poder comparar cinco candidatos
cambiando configuración, no código. **Sin esto, H6 es inviable.**

## El problema

`rag_service._llamar_llm` está acoplado al dialecto de Replicate:

```python
replicate.run(modelo, input={"prompt": user, "system_prompt": system, ...})
```

## Tareas

### 1. Cliente compatible con OpenAI

Reescribir `_llamar_llm` sobre el SDK `openai` con `base_url` configurable. Ese
protocolo lo hablan **Groq, Mistral, Gemini (endpoint compatible), OpenRouter,
Together, Cerebras y Ollama local**. Un solo camino de código, N proveedores,
cero dependencia de proveedor.

Nuevo módulo `backend/services/llm_service.py`:

```
llm_service.completar(system, user, max_tokens=None, temperature=None,
                      etiqueta="LLM") -> str
llm_service.completar_streaming(...) -> Iterator[str]   # lo usará H8
llm_service.info() -> dict   # proveedor, modelo, base_url (sin la clave)
```

Replicate se mantiene como **adaptador legacy** para poder reproducir la línea
base. No se borra.

### 2. Configuración

- `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL` en `settings_service` (editables
  en caliente desde el menú, como el resto).
- La clave de cada proveedor en `secrets_service` (`.env`), siguiendo el patrón
  existente. Ampliar `_PROVEEDORES` con los candidatos nuevos.
- La pestaña "APIs" del frontend debe reflejar los proveedores nuevos.

### 3. Partir `responder()`

Hace seis cosas en 60 líneas: traduce, recupera, evalúa, enruta, genera,
sintetiza y monta el diccionario. Es justo donde H8 va a meter el streaming.
Partir en funciones con responsabilidad única antes de tocarlo.

### 4. Sacar el TTS de `rag_service`

`_sintetizar_respuesta` no pinta ahí: el servicio de recuperación y generación
de texto no debería saber que existe ElevenLabs. Es la fuga de capas principal
del backend, y estorba directamente al streaming (H8 necesita el texto antes de
tener el audio). Subirlo al router o a un orquestador.

### 5. Deuda relacionada (aprovechando que se toca esta zona)

- **[HECHO] Unificar los dos clientes de ChromaDB.** `rag_service` y
  `documentos_service` creaban cada uno su `PersistentClient` sobre la misma ruta
  y duplicaban `_get_collection`. `services/vector_store.py` centraliza un cliente
  único; al no cachear el objeto-colección, se **eliminó `reiniciar_coleccion()`**
  y su clase de bug.
- **[HECHO] Enums en vez de cadenas mágicas**: `backend/enums.py` con `Origen`
  (RAG/GENERAL/SIN_INFO), `MetodoDecision` (umbral/llm/rerank), `ModoEvaluator`
  (umbral/llm/hibrido) y `OrigenDocumento` (subido/url). `StrEnum`: un miembro ES
  su string, así que las comparaciones y el JSON no cambian.
- **[HECHO] Tipar los retornos de los servicios.** `TypedDict` (cero coste en
  runtime): `RespuestaRAG` (rag_service), `RespuestaChat` (chat_service) e
  `InfoLLM` (llm_service.info). Los `-> dict` opacos pasan a contrato explícito.
- **[DIFERIDO] Generar `types.ts` desde el OpenAPI** con `openapi-typescript`.
  **Medido al abordarlo:** solo **2 de ~22** endpoints declaran `response_model`
  (`AskResponse`, `GenerateResponse`); el resto devuelve `dict` pelado, así que el
  OpenAPI no tiene schema para ellos y `openapi-typescript` los generaría como
  `unknown` — **destruyendo** el tipado hecho a mano que hoy sí existe. El autogen
  útil **exige antes** añadir `response_model` (≈20 schemas Pydantic de respuesta)
  a personajes/documentos/ubicaciones/config/etc., una tarea propia y con riesgo
  (la validación de `response_model` puede rechazar dicts que hoy pasan → 500).
  Se **difiere** a su propio trabajo (candidato a H10 o un hito de contrato de API).

## Criterios de aceptación (puerta) — H5 cerrado

- [x] Cambiar de proveedor es cambiar configuración, sin tocar código
      (`LLM_PROVIDER`/`LLM_BASE_URL`/`LLM_MODEL`, dispatch en `llm_service`).
- [~] Con Replicate + Llama 3 8B, el runner **reproduce la línea base**: garantizado
      por el **test de fijación** (pincha el `input` dict EXACTO de Replicate, sin
      gastar API) + tests de dispatch. La corrida *end-to-end* del runner la corre el
      usuario en su máquina (Replicate/DeepL rate-limitean).
- [~] Ollama local responde por la misma interfaz: la interfaz (`provider=openai` +
      `base_url`) está lista y unit-testeada; la demo live con Ollama la corre el
      usuario (no hay Ollama en el sandbox de desarrollo).
- [x] `rag_service` ya no importa `voice_service` (TTS movido a `chat_service`).
- [x] Un solo `PersistentClient` en todo el backend (`vector_store`, test que lo fija).
- [ ] `types.ts` se genera automáticamente: **DIFERIDO** (ver arriba — necesita
      cobertura de `response_model` primero). El `types.ts` a mano sigue vigente.
- [x] `pytest` en verde (114 tests); CI verde al abrir el PR a `dev`.

## Evidencia a entregar para el OK

1. Test de fijación + dispatch verdes (equivalencia con Replicate sin gastar API).
   La corrida end-to-end del runner y la demo con Ollama quedan para la máquina del
   usuario (APIs/servicios locales que el sandbox no tiene).
2. Informe de hito.

## Instrucción de arranque para Claude Code

> Lee `docs/PLAN.md` y `docs/plan/H5-capa-llm.md`. Este hito es **refactor puro**:
> el comportamiento con Replicate debe ser idéntico al de la línea base, y el
> runner lo tiene que demostrar. Escribe los tests **antes** del refactor. No
> cambies prompts ni modelos aquí. Dame el plan antes de escribir código.
