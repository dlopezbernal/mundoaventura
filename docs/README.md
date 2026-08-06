# Documentación de MundoAventura

Índice de la documentación del proyecto. El [`README.md`](../README.md) de la raíz cuenta cómo
instalar y usar; aquí está todo lo demás.

## Para entender el sistema

| Documento | Qué contiene |
|---|---|
| [`ARQUITECTURA.md`](ARQUITECTURA.md) | Diseño del sistema **actual**: capas, proveedores, flujos, invariantes, seguridad. |
| [`ANEXO-DIDACTICO.md`](ANEXO-DIDACTICO.md) | La teoría de fondo: qué es RAG, chunking con solape, `origen` vs `método`, CLIP/T5. |
| [`DECISIONES.md`](DECISIONES.md) | Índice de los **ADRs** (decisiones con contexto, opciones, medición y descartes). |

## Para defender el proyecto (memoria y tribunal)

| Documento | Qué contiene |
|---|---|
| [`EVALUACION.md`](EVALUACION.md) | Metodología de medición, línea base, progresión hito a hito, estudio de LLMs, **limitaciones**. |
| [`DEFENSA.md`](DEFENSA.md) | Guion de demo de 5 min (clics exactos), plan B por paso, preguntas del tribunal. |
| [`TRABAJO-FUTURO.md`](TRABAJO-FUTURO.md) | Lo recortado, lo descartado conscientemente, y lo que se haría en un servidor. |
| [`PRIVACIDAD.md`](PRIVACIDAD.md) | Flujos de datos personales y checklist RGPD/LOPDGDD. |

## Referencia y proceso

| Ruta | Qué contiene |
|---|---|
| [`DESPLIEGUE.md`](DESPLIEGUE.md) | Puesta en producción en un VPS: uv + systemd + Caddy, HTTPS, operación y copias. |
| [`APK-ANDROID.md`](APK-ANDROID.md) | Empaquetar la app como APK de Android (TWA): PWA instalable, firma y Digital Asset Links. |
| [`decisiones/`](decisiones/) | Un fichero ADR por decisión (ADR-000 es la plantilla). |
| [`plan/`](plan/) | El plan de trabajo por hitos (H1–H10) y el plan de reorganización documental. Se archiva tras la entrega. |
| [`mediciones/`](mediciones/) | Notas de mediciones puntuales (concurrencia, GPU/STT, latencia de streaming). |
| [`historico/`](historico/) | Documentos de implementación de hitos pasados (histórico, no describen el estado actual). |
| [`PLAN.md`](PLAN.md) | Documento maestro del plan de trabajo (prioridades, calendario, reglas). |
| [`PLATAFORMAS-IA.md`](PLATAFORMAS-IA.md) · [`playwright-mcp.md`](playwright-mcp.md) | Guías puntuales. |

> El contexto operativo para trabajar con **Claude Code** vive en [`../CLAUDE.md`](../CLAUDE.md).
