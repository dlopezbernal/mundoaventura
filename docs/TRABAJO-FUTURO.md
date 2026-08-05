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

## Fase 2 — revisar el despliegue

El despliegue actual **funciona y está documentado paso a paso**, pero se hizo optimizando para
que una persona pudiera montarlo y entenderlo entero, no para un equipo. Antes de darlo por bueno
a largo plazo conviene contrastarlo con la práctica habitual del sector:

- **¿Es el enfoque correcto, o solo el que funcionó?** Revisar el despliegue actual contra buenas
  prácticas: instalación nativa con `uv` + systemd + Caddy, actualización manual con
  `deploy/desplegar.sh`, un único servidor sin réplica, SQLite y ChromaDB en disco local. Cada una
  de esas decisiones tiene una justificación de tamaño de proyecto, pero ninguna se ha contrastado
  con la alternativa profesional.
- **Automatizar el despliegue desde GitHub.** Hoy el ciclo es manual: merge a `main` y luego entrar
  por SSH a lanzar el script. La alternativa es un *runner* de GitHub Actions que despliegue al
  hacer merge. Dos variantes con implicaciones muy distintas:
  - **Runner alojado** (`ubuntu-latest`) que entra por SSH con una clave guardada en los *secrets*
    del repositorio. Sencillo, pero mete una credencial de escritura del servidor en GitHub.
  - **Runner autoalojado** en el propio VPS, que hace *pull* y despliega sin abrir el SSH a nadie.
    Encaja mejor con el modelo actual (deploy key de solo lectura, el servidor tira del repo), a
    cambio de mantener un agente más en el servidor.
- **Qué exigirle a ese despliegue automático** para que sea una mejora real y no solo un botón:
  desplegar únicamente si el CI está verde, *smoke test* de `/health` después de reiniciar,
  **vuelta atrás automática** si no responde, y un despliegue sin corte perceptible (hoy hay unos
  segundos de 502 mientras systemd reinicia el servicio).
- **Reproducibilidad y entornos.** Un `Dockerfile` sigue pendiente (ver arriba). Con contenedor,
  el despliegue pasa a ser "construye imagen, publica, arranca", y deja de depender de que el
  servidor tenga la versión correcta de Node, `uv` y Python.
- **Entorno de pruebas.** Hoy solo existe producción: lo que se despliega no se ha visto nunca
  funcionando en un servidor antes de estar delante de los usuarios.
- **Observabilidad y avisos.** `journalctl` es suficiente para depurar a mano, pero nadie se entera
  si el servicio se cae de madrugada, si caduca un certificado o si se agota el saldo de un
  proveedor. Un *healthcheck* externo con aviso es el mínimo.
- **Copias de seguridad automáticas y probadas.** `desplegar.sh` copia `.env` y la BBDD antes de
  cada actualización, pero no hay copia periódica, ni fuera del servidor, ni **restauración
  probada** — una copia que no se ha restaurado nunca no se sabe si sirve.

## Ideas de producto (más allá de la ingeniería)

- Enrutar la vía GENERAL a una **búsqueda web** segura cuando las fichas no cubren la pregunta
  (hoy es un punto de extensión previsto en `rag_service`, no implementado).
- Más personajes y un corpus curado por edades.
- Panel para el adulto con métricas de uso del niño (ya hay una base de **auditoría**).
