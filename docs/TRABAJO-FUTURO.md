# Trabajo futuro

Sección honesta: lo que se **recortó** (con el motivo), lo que se **descartó conscientemente**, y
lo que falta por hacer. No es una lista de deseos: es el mapa de lo que sabemos que falta y por
qué no está.

> **Deuda técnica declarada: ninguna pendiente de anotar.** Una búsqueda de `TODO`, `FIXME`,
> `XXX` y `HACK` en `backend/`, `frontend-react/src/`, `evals/`, `scripts/`, `deploy/` y
> `.github/` no devuelve **ni un solo marcador real** (los aciertos son la palabra española
> "TODOS" en comentarios y los `retrieval_XXXX.json` de plantilla). Lo que falta está en este
> documento, no escondido en el código.

## Lo que se recortó por tiempo/alcance (con motivo)

| Recorte | Motivo | Qué haría falta para retomarlo |
|---|---|---|
| **Verdad de referencia a nivel de chunk** más rica | Con 1–2 ficheros por personaje, el recall@fichero satura al 100 % y es poco discriminante; se midió con recall de **chunk** como proxy | Anotar a mano el chunk esperado de cada pregunta sobre un corpus más grande |
| **Validar el juez LLM** (H6) | Ningún juez llegó al ≥ 85 % de acuerdo con el humano; se usó como señal indicativa y desempató el test ciego | Un juez más potente o un prompt de juicio mejor calibrado para roleplay en 1ª persona |
| **Tabla WER del STT local** | **No depende de la GPU** (esa parte se verificó, ver [`mediciones/H7-stt-gpu.md`](mediciones/H7-stt-gpu.md)): depende de tener ~20 clips reales, idealmente con **voces infantiles**, que solo puede grabar quien tenga acceso a ellas. Declarado fuera de alcance de la entrega | Grabar el corpus de clips y pasar el arnés ya escrito (`evals/stt.py`, `evals/stt_clips/manifest.yaml`) |
| **Test ciego con más evaluadores** | n=5 basta para desempatar dos finalistas, no para robustez estadística | Más evaluadores y un diseño con potencia estadística declarada |

> La **latencia p50/p95 del streaming ya no está en esta lista**: se midió el 2026-08-03
> (TTFT p50 **0,92 s**, p95 1,18 s; n=15) y está en
> [`mediciones/H8-latencia-streaming.md`](mediciones/H8-latencia-streaming.md).

## Lo que se descartó conscientemente (no es deuda, es criterio)

- **Retirar DeepL del camino crítico.** Se **midió** y empeoraba el retrieval (−5,4 recall,
  −11,1 ruteo) porque el corpus es inglés. Se mantiene. Reabrir esta decisión solo tiene sentido
  con un **corpus en español** (retrieval monolingüe ES-ES). [ADR-014](decisiones/ADR-014-retirada-deepl.md).
- **Framework de agentes (LangGraph y similares).** El Evaluator a mano es simple, medido y
  defendible; un orquestador añadiría dependencia y opacidad sin resolver un problema real.
  `PLAN.md §6`.
- **Migrar de ChromaDB** a Qdrant/pgvector. Chroma sobra para este volumen de datos.
- **Generación de imágenes en local** y **TTS local**. La primera es inviable en 6 GB para una
  demo; el segundo, en español, está un escalón por debajo de ElevenLabs, y la voz **es** el
  producto ([ADR-013](decisiones/ADR-013-tts-elevenlabs.md)). El TTS local (Kokoro) queda como
  **plan B "sin internet"** de la defensa, no como opción por defecto.

## Lo que se haría en un despliegue en servidor

Durante el desarrollo el despliegue fue un **túnel puntual** (Colab/ngrok). Desde el 2026-08-05 hay
además un **servidor permanente** en `chatmundoaventura.com` (VPS, systemd + Caddy con TLS; el
procedimiento completo está en [`DESPLIEGUE.md`](DESPLIEGUE.md)). Lo que sigue es lo que ese
despliegue **todavía no** resuelve:

- ✅ **Autenticación fuerte** en lugar del candado del túnel (`ACCESS_CODE` es una barrera ligera
  contra escaneo, no autenticación real — [ADR-001](decisiones/ADR-001-candado-tunel.md)).
  **Hecho** al preparar el VPS: los endpoints caros exigen sesión de familia
  (`EXIGIR_SESION_FAMILIA`, por defecto ON). Ver [`DESPLIEGUE.md §6`](DESPLIEGUE.md).
- ✅ **Verificación de correo y SMTP transaccional real.** **Hecho**: el OTP sale por
  **Brevo** desde el dominio propio (`no-reply@chatmundoaventura.com`), con plantilla HTML
  (`backend/templates/verificacion_email.html`) y fallback a consola solo en local. En
  producción `EMAIL_VERIFICACION=true`. El default del repo sigue en `false` **a propósito**,
  para que un clon nuevo y el tribunal puedan darse de alta sin montar un servidor de correo.
  Ver [`DESPLIEGUE.md §6.3`](DESPLIEGUE.md).
- **Almacenamiento gestionado**: SQLite es perfecto para local/túnel; un servidor multiusuario
  pediría Postgres y un vector store gestionado.
- **Rate limit y cupo POR CUENTA**, no solo por IP. Hoy el cupo diario de imágenes
  (`cuota_service`) es **global**, no por familia: una familia intensiva puede agotar el cupo
  de todas. Observabilidad (métricas, trazas) más allá de los logs de consola.
- **Un `Dockerfile` simple** para reproducibilidad. Orquestación (Compose/Kubernetes) **no**: sería
  sobre-ingeniería para el tamaño del proyecto (`PLAN.md §6`).
- ✅ **Nomenclatura interna de la credencial de admin.** **Hecho** el 2026-08-06: renombrados
  `CambiarPin` → `CambiarPassword`, `adminChangePin` → `adminChangePassword`, el esquema
  `AdminPin` → `AdminPassword` y los campos del cuerpo JSON (`pin` → `password`), con el
  `schema.d.ts` regenerado. **La clave de BBDD `admin_pin_hash` se conserva a propósito**: es la
  clave primaria de una fila que ya existe en el SQLite de producción, y cambiarla obligaría a
  migrar. Queda documentado con un comentario en el propio `admin_service`. Ojo, sigue habiendo
  **dos credenciales distintas** y solo se renombró la de admin: el **PIN de familia** es un PIN
  de verdad (4 dígitos) y su nombre es correcto.
- ✅ **Catálogos inactivos visibles sin credenciales.** **Corregido** el 2026-08-06:
  `GET /api/personajes?todos=1` y su gemelo de ubicaciones exigen ahora `X-Admin-Token` (→ 401);
  la lista de **activos** sigue siendo pública, porque la SPA la necesita antes de que el niño
  tenga sesión. Fijado con `tests/test_catalogos_inactivos.py`.

## Fase 2 — el despliegue

El despliegue inicial **funcionaba y estaba documentado**, pero se hizo optimizando para que una
persona pudiera montarlo y entenderlo entero. La fase 2 lo lleva a un ciclo automatizado.

### Hecho

- ✅ **Despliegue automático desde GitHub** (`.github/workflows/ci.yml`, job `deploy`): push a
  `main` o botón *Run workflow*, con `needs: [backend, frontend]` para que **sea imposible
  desplegar con el CI en rojo**, y `concurrency` para que dos merges seguidos no se pisen.
  Runner alojado que entra por SSH; lo que hace aceptable guardar una clave del servidor en
  GitHub es que va registrada con **comando forzado** (`command="…/desplegar.sh"`, sin pty) como
  el usuario sin privilegios: esa clave no da una shell. Detalle en
  [`DESPLIEGUE.md §5.1`](DESPLIEGUE.md).
- ✅ **Vuelta atrás automática y comprobación de humo** en `deploy/desplegar.sh`: si `/health` no
  responde tras el reinicio, vuelve al commit anterior, reconstruye, reinicia y sale con error.
  La puerta es `status: ok` y **no** las banderas de los proveedores (un DeepL caído no es un
  despliegue roto, y volver atrás no lo arreglaría).
- ✅ **Despliegue sin corte**: activación por socket de systemd (`deploy/mundoaventura.socket` +
  `uvicorn --fd 3`). Medido: de **10 % de peticiones con 502** durante el reinicio a **0 %**
  ([`mediciones/F2-despliegue-sin-corte.md`](mediciones/F2-despliegue-sin-corte.md)).

### Lo que sigue pendiente

- **¿Es el enfoque correcto, o solo el que funcionó?** Instalación nativa con `uv` + systemd +
  Caddy, un único servidor sin réplica, SQLite y ChromaDB en disco local. Desde el
  [ADR-015](decisiones/ADR-015-despliegue-nativo-vps.md) la decisión **sí está contrastada por
  escrito** contra Docker, Compose/Kubernetes, PaaS y runner autoalojado; lo que sigue sin
  existir es la comparación **empírica** (no se ha montado la alternativa para medirla).
- **Runner autoalojado** en el propio VPS como alternativa al alojado: haría *pull* sin que nadie
  tenga que entrar por SSH, lo que permitiría cerrar el puerto 22 a internet (hoy tiene que
  seguir abierto para que el runner de GitHub llegue). A cambio, un agente más que mantener.
- **Reproducibilidad y entornos.** Un `Dockerfile` sigue pendiente (ver arriba). Con contenedor,
  el despliegue pasa a ser "construye imagen, publica, arranca", y deja de depender de que el
  servidor tenga la versión correcta de Node, `uv` y Python.
- **Entorno de pruebas.** Hoy solo existe producción: lo que se despliega no se ha visto nunca
  funcionando en un servidor antes de estar delante de los usuarios.
- **Peticiones en vuelo: implementado, arnés listo, medición pendiente.** El corte para
  conexiones nuevas está resuelto por el socket de systemd. Para las respuestas ya empezadas
  (el SSE del chat, que dura segundos) el servicio usa `KillSignal=SIGINT` +
  `TimeoutStopSec=30`. Desde el 2026-08-06 existe además `scripts/bench_drenado.py`, que abre
  un stream, reinicia el servicio a mitad y comprueba si la respuesta llega a su final, con el
  criterio de aceptación declarado en
  [`mediciones/F3-drenado-en-vuelo.md`](mediciones/F3-drenado-en-vuelo.md). **Solo falta
  ejecutarlo en el VPS**, porque requiere reiniciar el servicio real.
- **Observabilidad y avisos.** `journalctl` es suficiente para depurar a mano, pero nadie se entera
  si el servicio se cae de madrugada, si caduca un certificado o si se agota el saldo de un
  proveedor. Un *healthcheck* externo con aviso es el mínimo.
- **Copias de seguridad fuera del servidor.** Ya hay copia completa (`deploy/respaldar.sh`, un
  `.tgz` con todo lo que no está en git), **automática** (antes de cada despliegue y cada noche
  vía temporizador de systemd), con **retención de 15 días** y **restauración verificada**
  (2026-08-05: `integrity_check` en `ok` y recuentos idénticos a la BBDD viva). Lo que falta es
  lo más importante: **sacarlas del servidor**. Hoy viven en el mismo disco que protegen, así que
  no cubren el escenario que más duele — perder la máquina. Un `rclone`/`restic` a
  almacenamiento externo desde el mismo temporizador lo cerraría.
- ✅ **Copias cifradas.** **Hecho** el 2026-08-06: `deploy/respaldar.sh` cifra el `.tgz` con
  **GPG de clave pública** (`BACKUP_GPG_RECIPIENT`). Se eligió asimétrico y no una contraseña
  simétrica precisamente por el escenario que importa: el servidor puede **crear** copias pero
  **no leerlas**, porque la clave privada nunca ha estado en esa máquina. Sin la variable
  configurada la copia se sigue haciendo, pero avisa por `stderr` de que va en claro. Probado
  de extremo a extremo: el secreto no aparece en el fichero cifrado y se recupera al descifrar.
  Instrucciones de la clave en la cabecera del propio script y en
  [`DESPLIEGUE.md §5.2`](DESPLIEGUE.md).

## Higiene del repositorio (limpieza, sin impacto funcional)

Nada de esto afecta a cómo funciona la app; son restos que un revisor encontrará al abrir el
repositorio. **La mayoría se limpió el 2026-08-06**; queda constancia de qué era cada cosa.

- ✅ **`backend/models/` borrado.** Directorio vacío (solo un `.gitkeep`) cuyo comentario hablaba
  de checkpoints `.pth` y de un `scripts/download_models.py` inexistente: residuo de cuando la
  generación de imagen iba a ser local. El módulo real de tablas es el **fichero**
  `backend/models.py`; tener además un directorio con ese nombre era un paquete-espacio latente.
- ✅ **`legacy/` borrada.** No quedaba ningún fichero versionado, solo un `__pycache__` local.
- ✅ **`CORS_ORIGINS` movido a `config.py`**, con el mismo comportamiento, restaurando el patrón
  de "toda la configuración de despliegue en un sitio".
- ✅ **`evals/` excluido de la recolección de pytest** (`norecursedirs`), para que `evals/test_ciego.py`
  —que es una herramienta de línea de comandos, no un test— no se recoja nunca por error. No se
  renombró a propósito: el comando está documentado en `EVALUACION.md`.
- **`requirements-backend.txt` duplica a mano** la lista de dependencias de `pyproject.toml`,
  sin versiones. Se declara a sí mismo como *fallback*, pero nada impide que se desincronice
  en silencio. **Sigue pendiente** (generarlo desde el lockfile sería lo suyo).
- **Doble gobernanza de los ajustes de correo y de `DEBUG`**: viven a la vez en `config.py`
  (como toggle de despliegue) y en `settings_service` (editables en caliente). Funciona, pero
  hay que saber cuál gana. **Sigue pendiente.**
- **Cobertura de tests desigual**: 32 ficheros de test, pero sin fichero propio
  `embeddings`, `personajes_service`, `ubicaciones_service`, `settings_service`,
  `voice_service` y `replicate_client`. **Sigue pendiente.**

## Ideas de mejora del producto (con criterio, no lista de deseos)

Ordenadas por relación entre valor para el niño y esfuerzo:

| Mejora | Por qué | Coste estimado |
|---|---|---|
| **Devolver la imagen por URL en vez de en base64** | Incrustarla en la respuesta añade **+33 % de peso** por la codificación. Ya está identificado en el [ADR-009](decisiones/ADR-009-streaming.md) | Bajo: servir el fichero y cambiar el `src` |
| **Recordar la conversación entre sesiones** | Hoy el chat vive en memoria del navegador y se pierde al recargar. Un niño que vuelve al día siguiente empieza de cero | Medio, y **abre un frente de privacidad**: guardar conversaciones de un menor exige decisión explícita |
| **Corpus en español** | Reabriría con sentido la retirada de DeepL (hoy descartada con datos porque el corpus es inglés) y quitaría una llamada de red del camino crítico | Alto: hay que construir y validar el corpus |
| **Búsqueda web segura para la vía GENERAL** | Cuando las fichas no cubren la pregunta, hoy se cae al conocimiento del modelo. Ya hay punto de extensión previsto en `rag_service` | Medio-alto, y **necesita filtrado infantil**, que es el problema de verdad |
| **Métricas de uso agregadas para el adulto** | El panel de auditoría ya existe y lista eventos; lo que falta es la lectura agregada ("esta semana ha preguntado 40 veces, sobre todo a dinosaurios") | Bajo sobre lo ya construido |
| **Más personajes y curación por edades** | El catálogo se gestiona sin tocar código; el cuello de botella es el contenido, no la técnica | Bajo por personaje |
| **TTS local de calidad** | Cerraría el círculo de privacidad (hoy la voz sale a EEUU). Descartado por calidad en español, no por dificultad | Alto, depende de que mejoren los modelos |

## Fase 3 — la app en el móvil

### Hecho

- ✅ **Rediseño responsive** (móvil · tablet · PC). El problema real no era estético: en pantalla
  estrecha el chat estiraba la página y **el campo de escribir la pregunta quedaba fuera de la
  vista**. Ahora la escena se recoge en una barra mini con visor, y el historial hace su propio
  scroll con el input siempre abajo.
- ✅ **PWA instalable**: manifest, iconos (con variante *maskable*) y un service worker mínimo
  escrito a mano. Desde el login se ofrece **"Instalar en Android"**, y la app se abre con su
  icono y sin barra del navegador. En iOS, lo mismo desde *Añadir a pantalla de inicio*.

### Lo que sigue pendiente

- **El APK (TWA) no está generado.** El procedimiento completo está escrito y verificado hasta
  donde se puede sin firmar ([`APK-ANDROID.md`](APK-ANDROID.md)), y la PWA —que es su requisito
  de entrada— ya está en producción. Falta solo el tramo que depende de una **credencial**: crear
  el keystore, empaquetar con PWABuilder y publicar la huella SHA-256 en
  `/.well-known/assetlinks.json` (hoy tiene un valor de ejemplo). Se aparcó a propósito: **la
  apariencia instalada desde el navegador es la misma que tendría el APK**, así que el APK solo
  añade poder distribuirlo como fichero o por Play Store, no una experiencia distinta.
- **Plugins nativos**, si algún día se quieren (háptica al girar el carrusel, notificaciones,
  grabación nativa): eso ya no es TWA sino **Capacitor**, y entonces habría que resolver el CORS
  —la app pasaría a servirse desde `https://localhost`— y el permiso de micrófono en el WebView,
  que hoy funciona gratis porque el motor es el Chrome del dispositivo.
- **Sin conexión no hay app**, y no es un defecto del empaquetado: la imagen la genera Replicate,
  el chat es un LLM en la nube y la voz es ElevenLabs. Un modo offline real exigiría modelos
  locales, que es otro proyecto.

## Ideas de producto (más allá de la ingeniería)

- Enrutar la vía GENERAL a una **búsqueda web** segura cuando las fichas no cubren la pregunta
  (hoy es un punto de extensión previsto en `rag_service`, no implementado).
- Más personajes y un corpus curado por edades.
- Panel para el adulto con métricas de uso del niño (ya hay una base de **auditoría**).
