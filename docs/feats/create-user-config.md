# Configuración de la aplicación desde un menú de ajustes — Plan por hitos

> **Objetivo del proyecto**
> Que **cualquier persona** (un adulto sin conocimientos de programación) pueda poner en marcha y
> personalizar por completo la *Máquina del Tiempo en tu Habitación* **sin tocar el código**:
> dándose de alta en las plataformas de IA, pegando sus claves y ajustando personajes, ubicaciones,
> prompts, umbrales del RAG y parámetros generales desde una interfaz de configuración.

Este documento es el **plan de trabajo** (hitos, decisiones técnicas y criterios de aceptación).
No cambia código todavía: fija el rumbo para hacerlo por fases.

---

## 1. Alcance y punto de partida

Hoy toda la configuración está **dispersa y en código / `.env`**. Para lograr el objetivo hay que
mover esa configuración a un sitio **editable en tiempo de ejecución** desde una UI, protegiendo lo
sensible (claves) y sin romper el flujo del niño.

### 1.1. Inventario de lo que hoy está "en código" y debería ser configurable

| Categoría | Dónde vive hoy | Qué es |
|-----------|----------------|--------|
| **Claves API** | `.env` (`REPLICATE_API_TOKEN`, `DEEPL_API_KEY`, `ELEVENLABS_API_KEY`) | Credenciales de los 3 proveedores |
| **Modelos IA** | `config.py` (`REPLICATE_MODEL`, `REPLICATE_EDIT_MODEL`, `REPLICATE_LLM_MODEL`, `ELEVENLABS_STT_MODEL`, `ELEVENLABS_TTS_MODEL`) | Qué modelo se usa en cada fase |
| **Imagen** | `config.py` (`IMG_ASPECT_RATIO`, `IMG_OUTPUT_FORMAT`, `IMG_NUM_STEPS`, `CLIP_TOKEN_LIMIT`) + `personajes.py` (`STYLE_SUFFIX`, `FRAMING`) | Estilo, encuadre y formato de la escena |
| **RAG / Evaluator** | `config.py` (`EVALUATOR_MODE`, `EVALUATOR_UMBRAL_BAJO`, `EVALUATOR_UMBRAL_ALTO`, `RAG_TOP_K`, `LLM_MAX_TOKENS`) | Umbrales de acierto y comportamiento del chat |
| **Chunking** | `config.py` (`CHUNK_SIZE`, `CHUNK_OVERLAP`, `CHROMA_COLLECTION`, rutas) | Troceado e indexado de documentos |
| **Prompts de sistema** | *Hardcodeados en inglés* en `rag_service.py` (`_construir_prompt`, `_construir_prompt_general`, `_evaluar_relevancia`) | Rol y reglas del personaje (RAG, GENERAL y juez) |
| **Voz** | `config.py` (`TTS_OUTPUT_FORMAT`, `STT_LANG`) + `personajes.py` (`VOCES`) | Formato de audio, idioma STT y voz por personaje |
| **Personajes** | `personajes.py` (`PROMPTS`/`NOMBRES`/`VOCES`) + `data/personajes.ts` + carpeta `documentos/<id>/` | Definición completa de un personaje (5 sitios) |
| **Ubicaciones** | `ubicaciones.py` + `data/ubicaciones.ts` | Definición de un lugar (2 sitios) |
| **General** | `config.py` (`DEBUG`), `main.py` (`CORS_ORIGINS`), `frontend/.env` (`VITE_DEBUG`, `VITE_BACKEND_URL`) | Modo desarrollo, orígenes, URL backend |

> **Nota sobre `Settings.tsx`**: ya existe una plantilla visual de ajustes, pero es puramente
> presentacional (guarda estado en memoria y tiene un `// TODO: persistir`). Sirve como base de
> estilo "Arcade Holo", pero la mayoría de sus campos actuales (volumen, brillo, scanlines…) **no**
> son la configuración que pide este proyecto; se reaprovecha el chasis, no el contenido.

---

## 2. Decisión de almacenamiento (best practices)

Planteaste tres opciones: **BBDD tipo MariaDB/MySQL**, **ficheros JSON** o **editar el `.env`
directamente**. La respuesta correcta no es una sola: cada tipo de dato tiene su sitio óptimo. La
recomendación es un **enfoque en capas**.

### 2.1. Recomendación: `.env` (secretos) + **SQLite** (ajustes y catálogo) + ficheros (documentos)

| Tipo de dato | Dónde guardarlo | Por qué |
|--------------|-----------------|---------|
| **Claves API** (Replicate, DeepL, ElevenLabs) | **`.env`** (fuera de git, editable desde la UI de "APIs") | Los secretos **no** deben ir en una BBDD en texto plano ni versionarse. El `.env` ya es el patrón del proyecto; la UI lo lee/escribe pero **nunca** devuelve la clave completa al navegador (solo `configurado: true` + valor enmascarado). |
| **Ajustes de app** (umbrales RAG, chunking, modelos, prompts de sistema, DEBUG, imagen, voz) | **SQLite** | Se editan en caliente, necesitan validación y aplicarse sin reiniciar. Una tabla de ajustes tipada da atomicidad e historial. |
| **Catálogo** (personajes, ubicaciones, voces, metadatos de documentos) | **SQLite** | Son datos semi-relacionales (un personaje tiene N documentos). SQLite da consultas, integridad y migraciones. |
| **Documentos del RAG** (los `.pdf/.txt/.md`) | **Sistema de ficheros** en `backend/documentos/<id>/` (como ahora) + **metadatos en SQLite** | Los binarios/textos van en disco; la BBDD guarda "qué archivo, de qué personaje, idioma, fecha, origen (subido/URL)". |
| **Índice vectorial** | **ChromaDB** (como ahora) | Sin cambios; solo mejoramos el reindexado (ver Hito 5). |

### 2.2. ¿Por qué **SQLite** y no MariaDB/MySQL ni JSON?

- **Frente a MariaDB/MySQL**: la filosofía declarada del proyecto es "**ligero, corre en cualquier
  ordenador, sin dependencias pesadas**" (por eso la IA se movió a la nube). Montar un servidor
  MySQL/MariaDB contradice eso: exige instalar y administrar un servicio aparte, con usuario,
  contraseña y puerto. **SQLite es un único fichero**, sin servidor, sin configuración, ya incluido
  en Python (`sqlite3`). Para una app de un solo equipo y baja concurrencia (un adulto edita ajustes
  de vez en cuando) es la elección de manual. *MariaDB/MySQL solo tendría sentido si algún día se
  despliega multiusuario en la nube; queda como camino de crecimiento, no como punto de partida.*
- **Frente a JSON suelto**: JSON es tentador por lo legible, pero a medida que crece el catálogo
  aparecen problemas: sin transacciones (una escritura a medias corrompe el archivo), sin
  validación de tipos, sin consultas ("dame los personajes con voz"), y condiciones de carrera si
  dos peticiones escriben a la vez. SQLite resuelve todo eso y **sigue siendo un solo fichero** que
  puedes copiar como backup. JSON se puede ofrecer como **formato de import/export** (ver Hito 7),
  que es donde brilla.
- **Frente a editar el `.env` directamente**: el `.env` es perfecto para **secretos y arranque**,
  pero **malo para ajustes que cambian en caliente**: obliga a reiniciar el backend en cada cambio,
  no valida nada y mezcla credenciales con preferencias. Lo reservamos solo para claves y un par de
  variables de bootstrap (qué BBDD, rutas).

### 2.3. Herramientas sugeridas (encajan con el stack actual)

- **SQLModel** (de los autores de FastAPI) o **SQLAlchemy** sobre SQLite: modelos = Pydantic +
  tabla, muy natural con los `schemas/` que ya usa el proyecto.
- **Alembic** para migraciones de esquema (opcional al principio, recomendable en cuanto el modelo
  se estabilice).
- Mantener **`python-dotenv`** para el `.env` de secretos.

### 2.4. Consecuencia arquitectónica importante

Hoy `config.py` lee el `.env` **una vez al importar** y el resto del código usa esas constantes
congeladas (`config.EVALUATOR_UMBRAL_BAJO`, etc.). Para tener ajustes **editables sin reiniciar** hay
que introducir un **servicio de configuración** (`settings_service`) que:

1. Lea el valor **vigente** desde SQLite (con caché en memoria e invalidación al guardar).
2. Caiga a un **valor por defecto** (los actuales de `config.py`) si aún no hay nada en BBDD.
3. Exponga los valores a los `services/` **por función** (`settings.get("EVALUATOR_UMBRAL_BAJO")`)
   en lugar de constantes de módulo.

Esta refactorización es el corazón del Hito 1 y desbloquea todo lo demás.

---

## 3. Seguridad y control de acceso (requisito transversal)

El menú de configuración es **potente y peligroso** (contiene claves API y prompts). La app la usan
**niños de 8–12 años**: la configuración **no puede** quedar al alcance de un niño.

- **Puerta de acceso (parental/admin)**: proteger toda el área de ajustes tras un PIN/contraseña de
  administrador (o una pantalla "solo para adultos"). Sin ella, un niño podría borrar personajes o
  ver/gastar claves API.
- **Nunca exponer secretos al frontend**: los endpoints devuelven las claves **enmascaradas**
  (`sk-••••••1234`) + un flag `configurado`. El "ojo" para revelar (ver Hito 2) hace una petición
  aparte, autorizada, y solo entonces se muestra el valor.
- **Escritura del `.env` con cuidado**: validar formato, hacer copia previa, escritura atómica
  (fichero temporal + `rename`) para no corromperlo.
- **Auditar cambios sensibles** (opcional): registrar quién/cuándo cambió una clave o borró un
  personaje.

---

## 4. Hitos

Cada hito es **incremental y entregable por separado**. El orden respeta las dependencias.

### Hito 0 — Descubrimiento y decisiones (0,5–1 sem)

**Objetivo**: cerrar las decisiones de este documento con el equipo y preparar el terreno.

- Validar el enfoque de almacenamiento (`.env` + SQLite + ficheros) y el modelo de acceso admin.
- Congelar el **inventario** (tabla §1.1) como fuente de verdad de "qué se configura".
- Definir el **contrato de API** de configuración (endpoints y formas de datos).

**Entregables**: este documento aprobado + esquema de datos y lista de endpoints acordados.
**Criterio de aceptación**: hay consenso sobre dónde vive cada dato y cómo se accede.

---

### Hito 1 — Cimiento de configuración (BBDD + servicio de settings) (1–1,5 sem)

**Objetivo**: infraestructura para leer/escribir configuración en caliente, **compatible hacia
atrás** (si la BBDD está vacía, se comporta exactamente como hoy).

- Añadir **SQLite + SQLModel**; crear las tablas base: `settings` (clave/valor tipado),
  `personajes`, `ubicaciones`, `documentos`, `voces` (o embebidas), y opcional `admin`/`audit`.
- **Seeding**: al arrancar por primera vez, volcar los valores actuales de `config.py`,
  `personajes.py` y `ubicaciones.py` a la BBDD (migración de datos "de código a datos").
- Crear `settings_service` con caché + invalidación; **refactorizar** los `services/` para leer a
  través de él en vez de constantes de módulo.
- Endpoints base: `GET /api/config` (lee ajustes, secretos enmascarados) y `PUT /api/config`
  (guarda y aplica en caliente).
- **Aplicar sin reiniciar**: los cambios de ajuste surten efecto en la siguiente petición; solo los
  que afecten al índice (chunking) requieren reindexar (aviso explícito).

**Entregables**: BBDD funcionando, servicio de settings, endpoints `GET/PUT /api/config`.
**Criterio de aceptación**: cambiar un umbral desde la API cambia el comportamiento del chat **sin
reiniciar** el backend; con BBDD vacía, la app funciona igual que hoy.

---

### Hito 2 — Pestaña "APIs" (credenciales de proveedores) (1 sem)

**Objetivo**: que cualquiera configure las claves sin abrir el `.env`. *(Corresponde a tu apartado
"Configuración de APIS".)*

- Pantalla que **lista los 3 proveedores** (Replicate, DeepL, ElevenLabs) con: estado
  (`configurado / falta`), y campo de clave.
- **Contraseñas enmascaradas con `•••`** y **icono de ojo 👁** para revelar al pulsar (petición
  autorizada aparte; nunca se envía la clave completa "por si acaso").
- Botón **"Probar conexión"** por proveedor (reutiliza la lógica de `/health` y las funciones
  `estado()` de `translation_service` y `voice_service`; para Replicate, una llamada ligera).
- Guardar → escribir en `.env` de forma **atómica y validada** + refrescar los singletons de cliente
  (DeepL/ElevenLabs se crean "perezosamente"; invalidarlos para que tomen la clave nueva).
- Enlaces de ayuda a cada plataforma para darse de alta y crear el token.

**Entregables**: pantalla de APIs con máscara + ojo + test de conexión + guardado seguro.
**Criterio de aceptación**: un usuario nuevo pega sus 3 claves desde la UI, pulsa "Probar conexión"
y ve ✅ en los tres, sin haber tocado ningún fichero.

---

### Hito 3 — Pestañas "IA" y "General" (ajustes del motor) (1–1,5 sem)

**Objetivo**: exponer los parámetros del RAG, el chunking, los prompts generales y el modo DEBUG.
*(Corresponde a tus apartados "Configuración de la IA" y "Configuración general".)*

**Configuración de la IA**
- **Umbral de acierto del RAG**: exponer `EVALUATOR_UMBRAL_BAJO`/`ALTO` y `EVALUATOR_MODE`.
  - ✅ **Decisión: valor coseno directo (0–2), SIN conversión a %**. Los umbrales se configuran tal
    cual son en el motor: la **distancia coseno de ChromaDB** (0 = idéntico … 2 = opuesto). Se
    exponen como campos numéricos con rango **0.00–2.00** (paso 0.01): `EVALUATOR_UMBRAL_BAJO`
    (≤ ⇒ RAG seguro), `EVALUATOR_UMBRAL_ALTO` (≥ ⇒ GENERAL), y entre ambos ⇒ zona dudosa. Nada de
    "% de similitud" ni fórmulas de conversión.
  - **Por qué 0–2 y no %**: (1) es la **métrica nativa** de ChromaDB, así lo que el usuario configura
    es exactamente lo que usa el motor (honestidad); (2) **simplifica el código** al no añadir una
    capa de conversión; (3) **facilita la calibración**, porque el valor configurado se compara
    directamente con la distancia real `d=...` que ya se muestra (en la UI y en consola con DEBUG).
  - **Validación**: `0 ≤ BAJO ≤ ALTO ≤ 2`. Mostrar en la pantalla la **última distancia medida**
    (`AskResponse.distancia`, ya calculada) como ayuda a la calibración, en solo lectura.
- **Chunking y recuperación**: `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RAG_TOP_K`. Avisar de que cambiar
  chunking **requiere reindexar** (botón "Reindexar ahora", ver Hito 5).
- **Modelo y longitud del LLM**: `REPLICATE_LLM_MODEL`, `LLM_MAX_TOKENS`, y (extra sugerido)
  `temperature`.
- **Prompts de sistema generales para todos los personajes**: sacar de código a BBDD los tres
  prompts hardcodeados en `rag_service.py` (RAG, GENERAL y Evaluator/juez), con **plantillas y
  variables** (`{nombre}`, `{fichas}`, `{pregunta}`). Editar el "carácter común" (tono, edad 8–12,
  "responde en español", "no inventes") sin tocar Python. *(Cubre "prompts de sistema general" y
  "otros prompts generales".)*

**Configuración general**
- **DEBUG on/off** (`config.DEBUG`): toggle que activa las trazas del backend. *(Cubre "seleccionar
  si DEBUG está activo".)*
- (Extra) `CORS_ORIGINS`, `VITE_DEBUG` y URL del backend, agrupados como "avanzado".

**Entregables**: pestañas IA y General con guardado en caliente + editor de prompts de sistema.
**Criterio de aceptación**: cambiar el umbral, el modo del Evaluator o el prompt de sistema desde la
UI cambia la respuesta del chat en la siguiente pregunta, sin editar código.

---

### Hito 4 — Pestaña "Personajes": alta/edición sin código (1,5–2 sem)

**Objetivo**: que un usuario avanzado **cree y edite personajes** sin tocar Python ni TS. *(Cubre el
primer punto de tu apartado "Pestaña personajes".)*

- Mover los personajes de código (`PROMPTS`/`NOMBRES`/`VOCES` + `data/personajes.ts`) a la tabla
  `personajes` (con seeding en Hito 1). El backend y el frontend leen el catálogo desde la API
  (`GET /api/personajes`) en vez de ficheros estáticos.
- **CRUD completo**: crear, editar, duplicar, activar/desactivar y borrar. Campos: `id` (slug),
  nombre visible, categoría, emoji/imagen, **prompt de imagen**, y (opcional) overrides de estilo.
- **Respetar el invariante `personaje_id`**: al crear uno, el sistema genera de golpe las 5 "piezas"
  (prompt, nombre, voz, tarjeta y carpeta de documentos) para que no queden a medias.
- **Selección de voz por lista desplegable**: nuevo endpoint `GET /api/voices` que **consulta la API
  de ElevenLabs** (`/v1/voices`) y devuelve las voces disponibles; el desplegable las muestra y
  guarda el `voz_id`. Botón "escuchar muestra" (opcional). *(Cubre "configurar el tipo de voz
  asociada al personaje consultando la API de la IA de voz".)*
- Validación: `id` único y sin espacios; avisar si falta la voz (el personaje respondería solo en
  texto, que es una degradación válida).

**Entregables**: pestaña de personajes con CRUD + desplegable de voces desde ElevenLabs.
**Criterio de aceptación**: crear un personaje nuevo entero desde la UI (nombre, prompt, voz) y verlo
aparecer en el carrusel del niño y poder chatear con él, sin tocar código.

---

### Hito 5 — RAG por personaje: subir documentos / URL + traducción (1,5–2 sem)

**Objetivo**: ampliar el conocimiento de cada personaje desde la UI. *(Cubre el tercer punto de tu
apartado "Pestaña personajes".)*

- **Subida de documentos**: endpoint de upload que guarda `.pdf/.txt/.md` en
  `backend/documentos/<id>/` y registra el metadato en la tabla `documentos`. Lista de documentos por
  personaje con borrar/descargar.
- **Ingesta desde URL (tipo Wikipedia)**: envolver el `fetch_wikipedia.py` existente en un servicio +
  endpoint (`POST /api/personajes/{id}/documentos/url`). El usuario pega la URL, el backend descarga
  el texto limpio y lo guarda. *(Ya filtra secciones irrelevantes; reaprovechable casi tal cual.)*
- **Traducción ES→EN al guardar**: si el contenido está en castellano, traducirlo a inglés con DeepL
  **en el momento de guardarlo** (los embeddings rinden mucho mejor en inglés — es una invariante del
  proyecto). Mostrar al usuario el **aviso**: *"Siempre es mejor adjuntar el material en inglés para
  que la IA lo entienda mejor"*. *(Cubre exactamente "si la información es en castellano, se traduce
  al inglés al guardar" + el aviso.)*
  - ⚠️ **Caveat de cuota**: DeepL Free son 500.000 caracteres/mes; un artículo largo puede consumir
    mucho. Avisar del tamaño estimado antes de traducir, o permitir marcar "ya está en inglés, no
    traducir".
- **Reindexado inteligente**: hoy `ingest.py` **borra y reconstruye TODO** el índice. Mejora: al
  cambiar documentos de **un** personaje, borrar solo sus chunks (Chroma soporta `delete` por
  `where={personaje_id}`) y re-indexar ese personaje. Botón "Reindexar" (por personaje y global) +
  aviso de cuándo hace falta.

**Entregables**: gestor de documentos por personaje (subida + URL + traducción + reindex).
**Criterio de aceptación**: subir un PDF en español a un personaje, ver que se traduce y se indexa, y
que el chat responde citando ese nuevo contenido (`origen: RAG`).

---

### Hito 6 — Pestaña "Ubicaciones": alta/edición sin código (0,5–1 sem)

**Objetivo**: mismo patrón que personajes, para los lugares.

- Mover `ubicaciones.py` + `data/ubicaciones.ts` a la tabla `ubicaciones` (seeding en Hito 1).
- CRUD: `id`, nombre visible, emoji/imagen y **prompt de la ubicación**.
- Frontend lee el catálogo desde `GET /api/ubicaciones`.

**Entregables**: pestaña de ubicaciones con CRUD.
**Criterio de aceptación**: crear una ubicación nueva desde la UI y usarla al generar una escena.

---

### Hito 7 — Endurecimiento, calidad y despliegue (1–1,5 sem)

**Objetivo**: dejar la configuración robusta y a prueba de usuarios no técnicos.

- **Control de acceso admin** (§3): PIN/contraseña para el área de ajustes (si no se hizo ya en Hito 2).
- **Validación y mensajes claros** en todos los formularios (rangos de umbrales, ids únicos, formatos).
- **Import/Export** de la configuración completa en **JSON** (backup, compartir "packs" de
  personajes) — aquí es donde JSON aporta valor.
- **Copia de seguridad** del fichero SQLite y del `.env` antes de cambios destructivos.
- **Aplicar imagen/voz sin reiniciar**: verificar que cambiar modelos o formato surte efecto en la
  siguiente generación.
- **Pruebas manuales guiadas** (no hay suite automática en el proyecto): checklist de humo por
  pantalla + verificación de `/health`.
- **Documentación para el usuario final**: mini-guía "de cero a jugar" (crear cuentas, pegar claves,
  crear tu primer personaje).

**Entregables**: acceso protegido, import/export, backups, guía de usuario.
**Criterio de aceptación**: una persona sin conocimientos técnicos, siguiendo solo la guía, deja la
app lista y crea un personaje propio con su documento y su voz.

---

## 5. Configuraciones adicionales sugeridas (no estaban en el encargo)

Al revisar el código aparecen ajustes que conviene exponer para cumplir de verdad el "todo
configurable sin tocar código":

- **Estilo e imagen**: `STYLE_SUFFIX` y `FRAMING` (hoy en `personajes.py`), `IMG_ASPECT_RATIO`,
  `IMG_OUTPUT_FORMAT`, `IMG_NUM_STEPS`, `CLIP_TOKEN_LIMIT`, `REPLICATE_MODEL`, `REPLICATE_EDIT_MODEL`.
  Son la palanca para el "look" de las escenas.
- **Voz (global)**: `ELEVENLABS_STT_MODEL`, `ELEVENLABS_TTS_MODEL`, `TTS_OUTPUT_FORMAT`, `STT_LANG`,
  además del `voz_id` por personaje (Hito 4).
- **Idioma de traducción**: hoy fijo ES→EN; dejarlo configurable prepara el terreno para otros
  idiomas de interfaz.
- **Overrides de prompt por personaje** (avanzado): permitir que un personaje afine su prompt de
  sistema sobre la plantilla general.
- **Gestión de acceso admin** y **auditoría** de cambios sensibles.
- **Import/Export** de packs de configuración (personajes + ubicaciones + ajustes).
- **Aviso de "reindexar necesario"** siempre que se toque chunking o documentos.

---

## 6. Riesgos y consideraciones

- **Refactor de `config.py`**: pasar de constantes de módulo a un servicio con caché es el cambio de
  mayor calado (Hito 1). Hacerlo con **compatibilidad hacia atrás** (defaults = valores actuales)
  evita romper nada.
- **Secretos**: no filtrar claves al frontend jamás; escritura del `.env` atómica; considerar cifrado
  en reposo si algún día se despliega fuera del equipo local.
- **Umbral del RAG**: se configura como **valor coseno directo (0–2), sin conversión a %** (ver
  Hito 3). Documentar en el proyecto el cambio y su porqué (métrica nativa, simplicidad, calibración
  contra la `d=...` real). Mostrar la última distancia medida ayuda a que el usuario lo ajuste.
- **Cuota de DeepL** al traducir documentos largos (Hito 5): avisar y permitir saltarse la traducción.
- **Reindexado**: mientras no exista el reindex incremental, cualquier cambio de documentos obliga a
  reconstruir todo el índice (lento con muchos documentos).
- **Seguridad infantil**: la puerta de acceso admin no es opcional; el menú contiene claves y borrado
  de contenido.

---

## 7. Anexos

### 7.1. Esquema de datos SQLite propuesto (borrador)

```
settings(clave TEXT PK, valor TEXT, tipo TEXT, actualizado_en DATETIME)
    -- clave/valor tipado para todos los ajustes de §1.1 (excepto secretos)

personajes(id TEXT PK, nombre TEXT, categoria TEXT, emoji TEXT,
           prompt_imagen TEXT, voz_id TEXT, activo BOOL,
           prompt_sistema_override TEXT NULL, creado_en DATETIME)

ubicaciones(id TEXT PK, nombre TEXT, emoji TEXT, prompt TEXT,
            activo BOOL, creado_en DATETIME)

documentos(id INTEGER PK, personaje_id TEXT FK, nombre_archivo TEXT,
           origen TEXT,        -- 'subido' | 'url'
           url_origen TEXT NULL, idioma_original TEXT, traducido BOOL,
           creado_en DATETIME)

admin(id INTEGER PK, pin_hash TEXT)          -- acceso al área de ajustes
audit(id INTEGER PK, accion TEXT, detalle TEXT, cuando DATETIME)  -- opcional
```

*(Los secretos —claves API— **no** van en SQLite: siguen en `.env`.)*

### 7.2. Endpoints de configuración propuestos (borrador)

```
GET    /api/config                     -> ajustes vigentes (secretos enmascarados)
PUT    /api/config                     -> guarda ajustes (aplica en caliente)

GET    /api/apis                       -> estado de los 3 proveedores (enmascarado)
PUT    /api/apis                       -> guarda claves en .env (atómico, validado)
POST   /api/apis/{proveedor}/test      -> probar conexión

GET    /api/voices                     -> voces de ElevenLabs (para el desplegable)

GET    /api/personajes                 -> catálogo (lo consume también el niño)
POST   /api/personajes                 -> crear
PUT    /api/personajes/{id}            -> editar
DELETE /api/personajes/{id}            -> borrar
POST   /api/personajes/{id}/documentos -> subir documento (multipart)
POST   /api/personajes/{id}/documentos/url -> ingerir desde URL (Wikipedia)
POST   /api/personajes/{id}/reindex    -> reindexar solo este personaje

GET    /api/ubicaciones                -> catálogo
POST   /api/ubicaciones                -> crear
PUT    /api/ubicaciones/{id}           -> editar
DELETE /api/ubicaciones/{id}           -> borrar

POST   /api/reindex                    -> reindexado global
POST   /api/config/export | import     -> backup / restore en JSON
```

### 7.3. Resumen de cobertura del encargo

| Pediste | Hito |
|---------|------|
| Menú de configuración para "cualquier persona" | Todos (0–7) |
| Documento `create-user-config.md` con hitos | **este documento** |
| Mejores prácticas de almacenamiento | §2 (`.env` + SQLite + ficheros) |
| Personajes: introducir por UI lo que hoy está en código | Hito 4 |
| Personajes: voz por desplegable (API de la IA de voz) | Hito 4 (`GET /api/voices`) |
| Personajes: RAG por documentos / URL + traducción ES→EN + aviso | Hito 5 |
| IA: umbral de acierto del RAG | Hito 3 (valor coseno 0–2, **sin** conversión a %) |
| IA: chunking, solapamiento y demás generales | Hito 3 |
| IA: prompts de sistema generales + otros prompts | Hito 3 |
| General: activar/desactivar DEBUG | Hito 3 |
| APIs: pantalla con proveedores + credenciales | Hito 2 |
| APIs: contraseñas con `•••` + icono de ojo 👁 | Hito 2 |
| Ubicaciones sin tocar código *(implícito)* | Hito 6 |
