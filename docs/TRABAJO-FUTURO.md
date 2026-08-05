# Trabajo futuro

Sección honesta: lo que se **recortó** (con el motivo), lo que se **descartó conscientemente**, y
lo que se haría en un **despliegue en servidor**. No es una lista de deseos: es el mapa de lo que
sabemos que falta y por qué no está.

## Lo que se recortó por tiempo/alcance (con motivo)

| Recorte | Motivo | Qué haría falta para retomarlo |
|---|---|---|
| **Verdad de referencia a nivel de chunk** más rica | Con 1–2 ficheros por personaje, el recall@fichero satura al 100 % y es poco discriminante; se midió con recall de **chunk** como proxy | Anotar a mano el chunk esperado de cada pregunta sobre un corpus más grande |
| **Validar el juez LLM** (H6) | Ningún juez llegó al ≥ 85 % de acuerdo con el humano; se usó como señal indicativa y desempató el test ciego | Un juez más potente o un prompt de juicio mejor calibrado para roleplay en 1ª persona |
| **Tabla WER del STT local** y **latencia p50/p95 del streaming** | Requieren GPU/CUDA y claves para cronometrar el flujo real; el sandbox de desarrollo no las tiene | Ejecutar las mediciones en la máquina del usuario (mecanismos ya implementados y con tests verdes) |
| **Test ciego con más evaluadores** | n=5 basta para desempatar dos finalistas, no para robustez estadística | Más evaluadores y un diseño con potencia estadística declarada |

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
- **Verificación de correo obligatoria** (hoy `EMAIL_VERIFICACION` es un toggle por defecto OFF)
  y SMTP transaccional real en vez del fallback a consola.
- **Almacenamiento gestionado**: SQLite es perfecto para local/túnel; un servidor multiusuario
  pediría Postgres y un vector store gestionado.
- **Rate limit y cupo por cuenta**, no solo por IP; observabilidad (métricas, trazas) más allá de
  los logs de consola.
- **Un `Dockerfile` simple** para reproducibilidad. Orquestación (Compose/Kubernetes) **no**: sería
  sobre-ingeniería para el tamaño del proyecto (`PLAN.md §6`).
- **Nomenclatura interna**: la UI y los mensajes de la credencial de admin ya dicen "contraseña"
  (≥ 8 + 2FA, H9.2d); quedan por renombrar algunos **identificadores internos** heredados del
  Hito 7 (el componente `CambiarPin`, la función `adminChangePin`, la clave `admin_pin_hash`), sin
  impacto funcional ni visible. Refactor de limpieza para después de la entrega.

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

- **¿Es el enfoque correcto, o solo el que funcionó?** Queda por contrastar contra la práctica
  habitual: instalación nativa con `uv` + systemd + Caddy, un único servidor sin réplica, SQLite
  y ChromaDB en disco local. Cada decisión tiene una justificación de tamaño de proyecto, pero
  ninguna se ha comparado con su alternativa profesional.
- **Runner autoalojado** en el propio VPS como alternativa al alojado: haría *pull* sin que nadie
  tenga que entrar por SSH, lo que permitiría cerrar el puerto 22 a internet (hoy tiene que
  seguir abierto para que el runner de GitHub llegue). A cambio, un agente más que mantener.
- **Reproducibilidad y entornos.** Un `Dockerfile` sigue pendiente (ver arriba). Con contenedor,
  el despliegue pasa a ser "construye imagen, publica, arranca", y deja de depender de que el
  servidor tenga la versión correcta de Node, `uv` y Python.
- **Entorno de pruebas.** Hoy solo existe producción: lo que se despliega no se ha visto nunca
  funcionando en un servidor antes de estar delante de los usuarios.
- **Peticiones en vuelo.** El corte del despliegue está resuelto para conexiones nuevas, pero una
  respuesta ya empezada (sobre todo el SSE del chat, que dura segundos) se corta igual al
  reiniciar. Sin medir.
- **Observabilidad y avisos.** `journalctl` es suficiente para depurar a mano, pero nadie se entera
  si el servicio se cae de madrugada, si caduca un certificado o si se agota el saldo de un
  proveedor. Un *healthcheck* externo con aviso es el mínimo.
- **Copias de seguridad fuera del servidor.** Ya hay copia completa (`deploy/respaldar.sh`, un
  `.tgz` con todo lo que no está en git), **automática** (antes de cada despliegue y cada noche
  vía temporizador de systemd), con **retención de 15 días** y **restauración verificada**
  (2026-08-05: `integrity_check` en `ok` y recuentos idénticos a la BBDD viva). Lo que falta es
  lo más importante: **sacarlas del servidor**. Hoy viven en el mismo disco que protegen, así que
  no cubren el escenario que más duele — perder la máquina. Un `rclone`/`restic` a
  almacenamiento externo desde el mismo temporizador lo cerraría; conviene cifrarlas antes de
  subirlas, porque el `.tgz` lleva el `.env` con todas las claves.

## Ideas de producto (más allá de la ingeniería)

- Enrutar la vía GENERAL a una **búsqueda web** segura cuando las fichas no cubren la pregunta
  (hoy es un punto de extensión previsto en `rag_service`, no implementado).
- Más personajes y un corpus curado por edades.
- Panel para el adulto con métricas de uso del niño (ya hay una base de **auditoría**).
