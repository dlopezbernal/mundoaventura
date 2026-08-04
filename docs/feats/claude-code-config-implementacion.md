# Encargo para Claude Code — Menú de configuración de la aplicación

> **Cómo usar este documento**: es un brief ejecutable para Claude Code. Implementa la
> configuración por **fases** (una por sesión si prefieres). El plan completo con la justificación
> está en `create-user-config.md`; **este documento manda** donde haya discrepancia, sobre todo en
> el tratamiento del **umbral del RAG** (ver §2, es la corrección clave respecto al plan).

---

## 0. Contexto del proyecto (leer antes de tocar nada)

App educativa (niños 8–12) que genera una escena (ubicación + personaje) y deja **chatear** con el
personaje mediante un pipeline **RAG**. Cliente-servidor desacoplado: **SPA React** (Vite +
TypeScript) ↔ **FastAPI**. Toda la IA pesada corre en la nube (Replicate, DeepL, ElevenLabs); el
backend es ligero. El índice vectorial (ChromaDB) corre en local sobre CPU.

**Convenciones que DEBES respetar:**

- **Comentarios, docstrings y documentación en español** (el proyecto ya es así).
- **Backend en capas**: `routers/` (finos) → `services/` (lógica) → `config.py` (ajustes).
  Los routers mapean `ValueError` → HTTP 400 y el resto → 500.
- **Invariante `personaje_id`**: la misma clave conecta `backend/personajes.py`
  (`PROMPTS`/`NOMBRES`/`VOCES`), `frontend-react/src/data/personajes.ts` y la carpeta
  `backend/documentos/<personaje_id>/`. No lo rompas.
- **"Inglés dentro, español fuera"**: la base de conocimiento, el retrieval y los prompts al LLM van
  en inglés; solo la pregunta del niño se traduce ES→EN (DeepL) y la respuesta se genera en español.
- **No romper el flujo del niño**: la interfaz principal (personaje → mundo → escena → chat) debe
  seguir intacta. La configuración es un área aparte.
- **Compatibilidad hacia atrás**: si la nueva base de datos está vacía, la app debe comportarse
  **exactamente como hoy** (los valores por defecto son los actuales de `config.py`).
- **No hay suite de tests automáticos**: verifica manualmente vía `/health`, `/docs` y la UI.

---

## 1. Objetivo

Que **cualquier persona sin conocimientos de programación** ponga en marcha y personalice la app
**sin tocar código**: pegar claves API, crear personajes y ubicaciones, subir documentos al RAG y
ajustar los parámetros de la IA, todo desde una pantalla de configuración.

---

## 2. ⚠️ CORRECCIÓN CLAVE — Umbral del RAG como valor coseno 0–2 (SIN conversión a %)

Esto **cambia** lo que decía `create-user-config.md`. **NO implementes ninguna conversión a
porcentaje ni "% de similitud".**

**Qué hacer:**

- Exponer en la pestaña de IA los umbrales **tal cual son**: la **distancia coseno de ChromaDB**,
  un número decimal entre **0.0 y 2.0** (0 = idéntico, 2 = opuesto):
  - `EVALUATOR_UMBRAL_BAJO` (por defecto **0.75**) → distancia **≤ BAJO** ⇒ RAG seguro.
  - `EVALUATOR_UMBRAL_ALTO` (por defecto **0.95**) → distancia **≥ ALTO** ⇒ GENERAL.
  - Entre ambos ⇒ zona **dudosa** (en modo híbrido la desempata el LLM-juez).
- Controles: dos campos numéricos (o sliders) con **rango 0.00–2.00, paso 0.01**, mostrando el valor
  numérico exacto. Selector para `EVALUATOR_MODE` (`umbral` / `llm` / `hibrido`).
- **Validación**: `0 ≤ BAJO ≤ ALTO ≤ 2`. Si el usuario los cruza, avisar y no guardar.
- Texto de ayuda en español llano junto a cada control (p. ej.: *"Distancia coseno: 0 = idéntico,
  2 = opuesto. Cuanto más BAJO, más estricto para usar los documentos."*).
- **Ayuda a la calibración (recomendado)**: mostrar en la pantalla la **última distancia medida**
  (`d=...`). Ese dato ya viaja en la respuesta de `POST /api/ask` (`AskResponse.distancia`) y ya se
  imprime en consola con `DEBUG`. Enséñalo (solo lectura) para que el usuario ajuste los umbrales
  observando valores reales. **No** lo conviertas a %.

**Qué NO hacer:**

- ❌ No añadas fórmulas tipo `(1 − distancia/2) × 100`.
- ❌ No muestres "%" en ninguna etiqueta del umbral.
- ❌ No guardes internamente un porcentaje: se persiste y se usa el **float 0–2** directamente.

**Por qué** (esto va también a la documentación, ver §7): usar la **métrica nativa** del modelo, sin
maquillarla, mantiene el sistema honesto y hace que lo que el usuario configura sea exactamente lo
que el motor usa; además simplifica el código (sin capa de conversión) y facilita calibrar
comparando con la `d=...` real.

---

## 3. Almacenamiento (recordatorio del plan)

- **`.env`** → SOLO secretos: `REPLICATE_API_TOKEN`, `DEEPL_API_KEY`, `ELEVENLABS_API_KEY`.
  La UI los lee/escribe pero **nunca** devuelve la clave completa al frontend (solo enmascarada +
  flag `configurado`). Escritura del `.env` **atómica** (temporal + `rename`) y validada.
- **SQLite** (usa **SQLModel**, encaja con los `schemas/` Pydantic) → todo lo demás: ajustes de IA,
  chunking, prompts de sistema, catálogo de personajes/ubicaciones, metadatos de documentos.
- **Sistema de ficheros** → documentos del RAG en `backend/documentos/<id>/` (como ahora) + ChromaDB.

No uses MariaDB/MySQL (contradice el "ligero, corre en cualquier PC"). JSON solo para import/export.

---

## 4. Refactor base obligatorio (hazlo primero)

Hoy `config.py` lee el `.env` al importar y el resto del código usa constantes de módulo congeladas.
Para tener ajustes editables **sin reiniciar**:

1. Crea `backend/services/settings_service.py`: lee el valor **vigente** desde SQLite, con **caché en
   memoria** e **invalidación al guardar**, y **cae al valor por defecto** (los actuales de
   `config.py`) si no hay nada en BBDD.
2. Sustituye los accesos a constantes en los `services/` por `settings_service.get(...)`
   (p. ej. `EVALUATOR_UMBRAL_BAJO`, `CHUNK_SIZE`, `EVALUATOR_MODE`, modelos, etc.).
3. **Seeding**: al primer arranque, vuelca los valores actuales de `config.py`, `personajes.py` y
   `ubicaciones.py` a SQLite.
4. Endpoints base: `GET /api/config` (ajustes vigentes, secretos enmascarados) y `PUT /api/config`
   (guarda y aplica en caliente).

**Criterio de aceptación**: cambiar un umbral por la API cambia el chat en la siguiente pregunta sin
reiniciar; con BBDD vacía, la app funciona igual que hoy.

---

## 5. Fases de implementación

Implementa en este orden. Cada fase es entregable por separado.

### Fase 1 — Cimiento (SQLite + `settings_service` + endpoints base)
Ver §4. Es la base de todo.

### Fase 2 — Pestaña "APIs" (credenciales)
- Lista los 3 proveedores con estado (`configurado`/`falta`).
- Contraseñas enmascaradas con `•••` + **icono de ojo 👁** para revelar (petición autorizada aparte;
  no se manda la clave completa "por si acaso").
- Botón **"Probar conexión"** por proveedor (reutiliza `/health` y las funciones `estado()` de
  `translation_service` y `voice_service`).
- Guardar → escribir en `.env` (atómico/validado) + invalidar los singletons de cliente DeepL/
  ElevenLabs para que tomen la clave nueva.

### Fase 3 — Pestañas "IA" y "General"
**IA:**
- **Umbrales del RAG según §2** (0–2 coseno, sin %). `EVALUATOR_MODE`, `RAG_TOP_K`.
- Chunking: `CHUNK_SIZE`, `CHUNK_OVERLAP` (avisar de que cambiarlos exige **reindexar**).
- LLM: `REPLICATE_LLM_MODEL`, `LLM_MAX_TOKENS` (y opcional `temperature`).
- **Prompts de sistema generales**: saca de código a BBDD los tres prompts hardcodeados en
  `rag_service.py` (`_construir_prompt`, `_construir_prompt_general`, `_evaluar_relevancia`), con
  variables (`{nombre}`, `{fichas}`, `{pregunta}`). Editar tono/reglas sin tocar Python.

**General:**
- **DEBUG on/off** (`config.DEBUG`).
- Avanzado: `CORS_ORIGINS`, `VITE_DEBUG`, URL del backend.

### Fase 4 — Pestaña "Personajes" (CRUD sin código)
- Mueve los personajes de código a la tabla `personajes` (seeding en Fase 1). Backend y frontend leen
  el catálogo por API (`GET /api/personajes`).
- CRUD completo; al crear uno, genera de golpe las piezas del invariante (prompt, nombre, voz,
  tarjeta, carpeta de documentos).
- **Voz por desplegable**: nuevo `GET /api/voices` que consulta la API de ElevenLabs (`/v1/voices`)
  y rellena la lista; guarda el `voz_id`. Personaje sin voz = solo texto (degradación válida).

### Fase 5 — RAG por personaje (documentos + URL + traducción)
- **Subida** de `.pdf/.txt/.md` a `backend/documentos/<id>/` + metadato en tabla `documentos`.
- **Ingesta desde URL** (tipo Wikipedia): envuelve `backend/fetch_wikipedia.py` en un servicio +
  endpoint. Ya filtra secciones irrelevantes; reaprovéchalo.
- **Traducción ES→EN al guardar** con DeepL si el contenido está en castellano, y **muestra el
  aviso**: *"Siempre es mejor adjuntar el material en inglés para que la IA lo entienda mejor."*
  Avisa del posible consumo de cuota de DeepL en documentos largos; permite marcar "ya está en inglés".
- **Reindexado inteligente**: en vez del borrado total de `ingest.py`, borra solo los chunks del
  personaje (`collection.delete(where={"personaje_id": id})`) y re-indexa ese personaje. Botón
  "Reindexar" por personaje y global.

### Fase 6 — Pestaña "Ubicaciones" (CRUD sin código)
Mismo patrón que personajes: tabla `ubicaciones`, `GET /api/ubicaciones`, CRUD.

### Fase 7 — Endurecimiento
- **Acceso admin** (PIN/contraseña) para toda el área de ajustes: contiene claves y borrado de
  contenido, y la app la usan niños. **No es opcional.**
- Validaciones y mensajes claros; **import/export** JSON de la configuración; backup del `.env` y del
  SQLite antes de cambios destructivos.

---

## 6. Endpoints propuestos (guía)

```
GET/PUT  /api/config                          ajustes (secretos enmascarados / guardar en caliente)
GET/PUT  /api/apis                            estado y guardado de claves (.env)
POST     /api/apis/{proveedor}/test           probar conexión
GET      /api/voices                          voces de ElevenLabs (desplegable)
GET/POST/PUT/DELETE  /api/personajes[/{id}]   CRUD de personajes
POST     /api/personajes/{id}/documentos      subir documento (multipart)
POST     /api/personajes/{id}/documentos/url  ingerir desde URL (Wikipedia)
POST     /api/personajes/{id}/reindex         reindexar solo este personaje
GET/POST/PUT/DELETE  /api/ubicaciones[/{id}]  CRUD de ubicaciones
POST     /api/reindex                         reindexado global
POST     /api/config/export | import          backup / restore JSON
```

---

## 7. 📄 TAREA OBLIGATORIA — Documentar el cambio y su porqué (para los profesores)

Esto es una **práctica de entrega de un curso de IA**. Además del código, **debes actualizar la
documentación del proyecto** para dejar constancia del cambio del umbral y, sobre todo, del **motivo
de la pantalla de configuración**, de forma que los profesores lo entiendan.

**Dónde escribirlo:**
- `README.md` → añade una entrada nueva en la sección **"🧭 Decisiones de diseño"**.
- `ARQUITECTURA.md` → nota breve sobre la capa de configuración (SQLite + `settings_service`).
- `CLAUDE.md` → nota para futuros agentes: los ajustes ya no son constantes de `config.py`, se leen
  del `settings_service` (BBDD), y el umbral es coseno 0–2 sin conversión.

**Contenido que debe quedar reflejado (redáctalo en español, con tu propio estilo, cubriendo estos
puntos):**

1. **Qué cambió en el umbral**: los umbrales del Evaluator (`EVALUATOR_UMBRAL_BAJO`/`ALTO`) se
   configuran desde la UI como **distancia coseno directa (0–2)**, sin convertir a porcentaje.

2. **Por qué existe la pantalla de configuración** — deja claros los **dos motivos**:
   - **(1) Democratizar el uso**: permite que una persona **sin conocimientos de IA** ponga en marcha
     y personalice la aplicación (claves, personajes, ubicaciones, documentos, parámetros) **sin
     tocar el código**. Basta con darse de alta en las plataformas de IA e introducir las claves.
   - **(2) Facilitar el testeo/calibración**: hace **muy fácil cambiar la configuración para probar y
     comparar resultados** (umbrales, modo del Evaluator, chunking, prompts) en caliente, sin
     reiniciar ni editar ficheros. Esto convierte la app en un banco de pruebas del pipeline RAG.

3. **Por qué el umbral se deja en 0–2 coseno y no en %**: es la **métrica nativa** de ChromaDB; no
   convertirla (a) mantiene el sistema honesto (lo que se configura es lo que el motor usa), (b)
   simplifica el código al eliminar una capa de conversión, y (c) facilita la calibración, porque el
   valor configurado se compara directamente con la distancia real `d=...` que ya se muestra (en la
   UI y en la consola con `DEBUG`).

> Sugerencia de encuadre para los profesores: la pantalla de configuración **evidencia el dominio del
> pipeline** (qué parámetros lo gobiernan y cómo afectan al resultado) y habilita una **calibración
> empírica** de los umbrales observando las distancias medidas — justo el tipo de razonamiento que se
> espera demostrar en el capstone.

---

## 8. Criterios de aceptación globales

- [ ] Con la BBDD vacía, la app se comporta igual que antes del cambio (compatibilidad hacia atrás).
- [ ] Los umbrales se configuran y persisten como **float 0–2**; **no** aparece ningún "%".
- [ ] Cambiar umbral / modo / prompt de sistema desde la UI afecta al chat **sin reiniciar**.
- [ ] Las claves API se configuran desde la UI, se guardan en `.env` de forma segura y **nunca** se
      envían completas al frontend (máscara + ojo).
- [ ] Se pueden crear personajes y ubicaciones nuevos desde la UI y usarlos en el flujo del niño.
- [ ] Se pueden subir documentos / URLs al RAG, se traducen ES→EN al guardar (con aviso) y el chat
      responde citándolos (`origen: RAG`).
- [ ] `README.md`, `ARQUITECTURA.md` y `CLAUDE.md` reflejan el cambio del umbral y los **dos motivos**
      de la pantalla de configuración (§7).
- [ ] Verificación manual: `GET /health` muestra los tres proveedores OK; el flujo del niño sigue
      intacto; `/docs` levanta.

---

## 9. Restricciones (resumen)

- Comentarios y docs **en español**; respeta el estilo del repo.
- Respeta el **invariante `personaje_id`** y el principio **"inglés dentro, español fuera"**.
- **Nada de conversión a %** en el umbral (§2).
- **No** metas dependencias pesadas ni un servidor de BBDD externo (usa SQLite).
- No filtres secretos al frontend. Escritura de `.env` atómica.
- No rompas el flujo del niño; la configuración va tras una **puerta de acceso admin**.
