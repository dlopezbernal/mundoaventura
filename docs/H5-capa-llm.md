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

- **Unificar los dos clientes de ChromaDB.** `rag_service` y
  `documentos_service` crean cada uno su `PersistentClient` sobre la misma ruta
  y duplican `_get_collection`. Un módulo `vector_store.py` con un cliente único
  elimina la clase de bug que hoy obliga a existir a `reiniciar_coleccion()`.
- **Enums en vez de cadenas mágicas**: `RAG`/`GENERAL`/`SIN_INFO`,
  `umbral`/`llm`/`hibrido`, `subido`/`url`. `StrEnum` en Python.
- **Tipar los retornos de los servicios.** Hay 28 firmas `-> dict`. Pasar a
  modelos Pydantic o dataclasses al menos en `rag_service` y `llm_service`.
- **Generar `types.ts` desde el OpenAPI** con `openapi-typescript`. Hoy está
  escrito a mano y su propia cabecera admite que hay que mantenerlo sincronizado
  a mano — una promesa que se rompe sola. Añadir el paso al script de build.

## Criterios de aceptación (puerta)

- [ ] Cambiar de proveedor es cambiar configuración, sin tocar código.
- [ ] Con Replicate + Llama 3 8B configurado, el runner **reproduce la línea
      base** (prueba de que el refactor no cambió comportamiento).
- [ ] Ollama local responde correctamente a través de la misma interfaz.
- [ ] `rag_service` ya no importa `voice_service`.
- [ ] Un solo `PersistentClient` en todo el backend.
- [ ] `types.ts` se genera automáticamente y el frontend compila.
- [ ] `pytest` en verde, CI verde, cobertura no baja.

## Evidencia a entregar para el OK

1. Salida del runner con Replicate demostrando que reproduce la línea base.
2. Captura de la app funcionando con Ollama local.
3. Informe de hito.

## Instrucción de arranque para Claude Code

> Lee `docs/PLAN.md` y `docs/plan/H5-capa-llm.md`. Este hito es **refactor puro**:
> el comportamiento con Replicate debe ser idéntico al de la línea base, y el
> runner lo tiene que demostrar. Escribe los tests **antes** del refactor. No
> cambies prompts ni modelos aquí. Dame el plan antes de escribir código.
