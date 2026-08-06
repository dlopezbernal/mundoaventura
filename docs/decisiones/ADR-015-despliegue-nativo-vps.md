# ADR-015 — Despliegue nativo en un VPS (uv + systemd + Caddy), no Docker ni PaaS

- **Estado:** aceptada
- **Fecha:** 2026-08-05
- **Fase:** F2 (despliegue) — `docs/DESPLIEGUE.md`, `docs/TRABAJO-FUTURO.md §Fase 2`
- **Sustituye al modelo de despliegue del [ADR-001](ADR-001-candado-tunel.md)** (túnel ngrok/Colab).

## Contexto

Hasta H10 la app se enseñaba por un **túnel efímero** (ngrok/Colab) levantado a ratos. Para
la entrega hacía falta algo que estuviera **siempre en pie, con dominio propio y HTTPS
válido**: sin TLS real, `getUserMedia` no funciona y la mitad de la app (hablar con el
personaje) deja de existir.

Las restricciones son concretas y todas apuntan en la misma dirección:

- El backend guarda **estado en disco** dentro de su propio directorio: `config_db.sqlite3`,
  `backend/chroma_db/`, `backend/documentos/`, `backend/avatares/`, `backend/.cache/` y el
  propio `.env` (que `secrets_service` **reescribe** cuando el adulto cambia una clave desde
  el menú).
- Corre con **`--workers 1` obligatorio**: hay estado en memoria no compartido entre procesos
  (sesiones de admin, contador de fuerza bruta por IP, cubos de slowapi, caché de
  `settings_service`).
- Es **un solo servidor sin réplica**, con un tráfico de una familia y un tribunal.

Sobre eso hay que decidir cómo se instala, cómo se actualiza y cómo se evita que cada
actualización le devuelva un error al niño que está jugando.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| **A. Nativo: `uv sync` + systemd + Caddy** (elegida) | Un solo artefacto (el repo) y las mismas órdenes que en local; `uv.lock` ya clava las versiones; systemd da reinicio, endurecimiento y **activación por socket**; Caddy da TLS automático | El servidor tiene que tener la versión correcta de Python, Node y `uv`; no hay imagen que publicar |
| B. Imagen Docker única | Reproducibilidad real; el servidor solo necesita el runtime | Todo el estado es un volumen montado (incluido el `.env` que la app se reescribe a sí misma); una capa más que depurar para cero ganancia de escala |
| C. Compose / Kubernetes | Orquestación, réplicas, despliegue azul-verde | Sobre-ingeniería declarada (`PLAN.md §6`): un proceso, un worker, SQLite en disco local — no hay nada que orquestar |
| D. PaaS gestionado (Railway/Render/Fly) | Cero administración de sistema; despliegue desde git de fábrica | Sistema de ficheros efímero: SQLite, ChromaDB, los documentos y la caché de modelos se perderían en cada redespliegue; obligaría a rediseñar la persistencia entera |

## Medición

Lo único que se midió es lo que había que arreglar antes de automatizar: **cuántas peticiones
falla un usuario real mientras se reinicia el backend**, que es lo que ocurre en cada
despliegue. 80 `GET /health` a 250 ms de intervalo contra el sitio público por HTTPS
(atravesando Caddy), reiniciando el servicio a mitad del bombardeo:

| Configuración del servicio | 200 | 502 | Peticiones perdidas |
|---|---|---|---|
| `uvicorn --host 127.0.0.1 --port 8000` (línea base) | 72 | **8** | **10,0 %** |
| `uvicorn --fd 3` + `mundoaventura.socket` | **80** | **0** | **0 %** |

Medido el 2026-08-05 sobre el VPS de producción (Ubuntu 24.04, 2 vCPU) →
[`mediciones/F2-despliegue-sin-corte.md`](../mediciones/F2-despliegue-sin-corte.md). El
reinicio duró ~1 s en ambos casos: la diferencia no es velocidad, es que en la línea base el
puerto **se cierra** y las conexiones de esa ventana se rechazan (`connection refused` → 502).

La elección entre A, B, C y D **no se midió**: es una decisión de diseño según el tamaño del
proyecto y la forma de su estado, no de rendimiento.

## Decisión

**Opción A.** Instalación nativa en un VPS (Ubuntu 24.04, 2 vCPU, 4 GB), con:

- **systemd** (`deploy/mundoaventura.service`): `Type=exec`, usuario sin privilegios,
  `ProtectSystem=strict` + un único `ReadWritePaths=/opt/mundoaventura`, `Restart=always`,
  `KillSignal=SIGINT` y `TimeoutStopSec=30` para dar margen a los SSE en vuelo. Deliberadamente
  **sin `EnvironmentFile`**: `config.py` hace su propio `load_dotenv`, y con systemd cacheando
  el `.env` del arranque las dos fuentes se desincronizarían en cuanto el adulto cambiara una
  clave desde el menú.
- **Activación por socket** (`deploy/mundoaventura.socket`): es systemd quien abre y mantiene
  el `127.0.0.1:8000` y se lo pasa al proceso como descriptor 3 (`--fd 3`). Al reiniciar solo
  el servicio, el socket **nunca se cierra**. La unidad **no** lleva `PartOf=`: con esa
  directiva el socket se reiniciaría también y volvería el 502.
- **Caddy** (`deploy/Caddyfile`): TLS de Let's Encrypt automático, SPA estática con
  `try_files … /index.html`, y proxy inverso de `/api/*` y `/health` con
  **`flush_interval -1`** (sin `flush_interval -1` el SSE del chat se bufferiza y el texto
  aparece de golpe al final, en vez de token a token) y **`lb_try_duration 20s`** como segunda
  red contra el 502 (cubre el caso que el socket no cubre: que el backend se caiga de verdad y
  systemd tarde en relanzarlo). La compresión **excluye** `/api/ask/stream` por la misma razón.
  Mismo origen que la SPA ⇒ no hay CORS que configurar.
- **Actualización con `deploy/desplegar.sh`**: copia previa → anotar el commit actual →
  `git pull --ff-only` → `uv sync --frozen` + `npm ci && npm run build` → reinicio →
  **comprobación de humo** contra `/health`. Si no responde, **vuelve atrás solo** al commit
  anterior, reconstruye y sale con error. La puerta es `status: ok` y **no** las banderas de
  los proveedores: un `deepl_ok:false` es casi siempre una caída de DeepL, no un despliegue
  roto, y volver atrás no lo arreglaría.
- **CI/CD desde GitHub Actions** (`.github/workflows/ci.yml`, job `deploy`): `needs:
  [backend, frontend]` hace **imposible desplegar con el CI en rojo**; `concurrency:
  deploy-produccion` con `cancel-in-progress: false` evita que dos merges seguidos se pisen
  sobre el mismo directorio y que se aborte un despliegue a medias. El runner entra por SSH
  con una clave registrada con **comando forzado** (`command="…/desplegar.sh"`): esa clave no
  da una shell, así que guardarla en GitHub es aceptable. Después comprueba el sitio **público**
  (HTTPS + DNS + certificado), que es lo que el script no puede validar desde dentro.

## Qué se descarta y por qué

- **Docker (B):** el argumento fuerte de un contenedor es la reproducibilidad, y aquí ya la dan
  `uv.lock` (con hashes) y `package-lock.json`. A cambio, **todo el estado de la app es
  persistente y está en su propio directorio** —incluido un `.env` que el proceso se reescribe a
  sí mismo—, así que la imagen sería un envoltorio alrededor de un volumen montado. No se
  descarta para siempre: un `Dockerfile` simple queda como trabajo futuro.
- **Compose / Kubernetes (C):** no hay nada que orquestar. Un proceso con `--workers 1`, un
  SQLite y un ChromaDB en disco local; escalar horizontalmente ni siquiera es posible hoy sin
  antes sacar el estado en memoria a SQLite/Redis. Sobre-ingeniería.
- **PaaS gestionado (D):** incompatible con la persistencia real de la app. Un sistema de
  ficheros efímero borraría el índice RAG, los documentos subidos, la BBDD de configuración y
  la caché de modelos ONNX en cada redespliegue.
- **Runner autoalojado en el propio VPS:** haría *pull* sin que nadie entre por SSH y permitiría
  **cerrar el puerto 22 a internet** (hoy debe seguir abierto para que el runner de GitHub
  llegue). Se descarta *por ahora* por el coste de mantener un agente más en un servidor de 2
  vCPU; el comando forzado acota el riesgo mientras tanto. Queda en `TRABAJO-FUTURO.md`.

## Consecuencias

- **Código/ficheros:** `deploy/mundoaventura.service`, `deploy/mundoaventura.socket`,
  `deploy/Caddyfile`, `deploy/desplegar.sh`, `deploy/respaldar.sh` y el job `deploy` del CI.
  **Sin dependencia nueva** en la app.
- **`.env` / servidor:** el `.env` de producción vive en `/opt/mundoaventura` y lo reescribe la
  propia app; el usuario `mundoaventura` tiene un `sudoers.d` que le concede **exactamente**
  `systemctl restart|status mundoaventura`, nada más. `--proxy-headers` +
  `--forwarded-allow-ips=127.0.0.1` para que slowapi vea la IP real del cliente y no la de Caddy.
- **Un cambio del `Caddyfile` NO lo aplica `desplegar.sh`**: hay que copiarlo al servidor y
  recargar Caddy a mano. Es una asimetría que se paga cada vez que se olvida.
- **Deuda aceptada 1 — no hay `Dockerfile`.** El despliegue depende de que el servidor tenga la
  versión correcta de Python, Node y `uv`. Anotado en
  [`TRABAJO-FUTURO.md`](../TRABAJO-FUTURO.md).
- **Deuda aceptada 2 — no hay entorno de pruebas.** Solo existe producción: lo que se despliega
  no se ha visto nunca funcionando en un servidor antes de estar delante de los usuarios. Lo
  que amortigua el riesgo es la vuelta atrás automática, no una fase previa.
- **Deuda aceptada 3 — esto no es alta disponibilidad.** Un proceso y un servidor: si el backend
  se cae y no levanta, la app está caída. La medición elimina el corte *previsible* del
  despliegue, no los demás. Tampoco cubre las **peticiones en vuelo** (un SSE de varios segundos
  se corta igual al reiniciar; sin medir).
- **Revisar si:** aparecen varias familias concurrentes de verdad (haría falta sacar el estado
  en memoria y pasar a `--workers > 1`, y entonces sí un almacenamiento gestionado), o si se
  quiere un entorno de pruebas — ese es el punto donde el contenedor empieza a pagar.
