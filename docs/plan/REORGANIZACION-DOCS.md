# Reorganización de la documentación

Se ejecuta en H10, pero **cada hito va dejando su parte** según avanza.

## El problema actual

| Fichero | Tamaño | Problema |
|---|---|---|
| `README.md` | 44 KB | Mezcla instalación, uso, arquitectura, teoría de RAG y decisiones |
| `CLAUDE.md` | 20 KB | Se solapa con README y ARQUITECTURA; describe un diseño que va a cambiar |
| `ARQUITECTURA.md` | 9,8 KB | Bien, pero repite lo que ya está en el README |
| `docs/feats/*.md` | 40 KB | Documentos de implementación de hitos pasados, sin índice |

Son ~114 KB de documentación con mucha superficie duplicada. **Documentación
duplicada es documentación que deriva**, y ya hay evidencia de ello: comentarios
que anuncian como futuro lo que ya está implementado.

La documentación actual es **pedagógica**: explica qué es RAG, por qué el
solape, cómo funciona CLIP. Para un capstone eso es defendible y no se tira,
pero una memoria necesita otra cosa: **decisiones con evidencia**. Se separan
los dos géneros.

## Estructura objetivo

```
README.md                        ← SÓLO: qué es, instalación, uso, arranque
CLAUDE.md                        ← contexto operativo para Claude Code
docs/
  PLAN.md                        ← plan de trabajo (se archiva tras la entrega)
  plan/                          ← un fichero por hito
  ARQUITECTURA.md                ← diseño del sistema, diagramas, flujos
  DECISIONES.md                  ← índice de ADRs con su estado
  decisiones/
    ADR-000-plantilla.md
    ADR-001-....md
  EVALUACION.md                  ← metodología, línea base, resultados
  PRIVACIDAD.md                  ← flujos de datos, RGPD/LOPDGDD (H9)
  ANEXO-DIDACTICO.md             ← el material explicativo actual
  historico/                     ← docs/feats/* movidos aquí, con índice
  img/
```

## Reparto de contenido

| Contenido actual | Va a |
|---|---|
| Instalación, requisitos, arranque | `README.md` |
| Guía de uso paso a paso | `README.md` |
| Diagramas de flujo, secuencias | `docs/ARQUITECTURA.md` |
| Invariante `personaje_id`, capa de configuración | `docs/ARQUITECTURA.md` |
| "Qué es RAG", "qué es el solape", "CLIP vs T5" | `docs/ANEXO-DIDACTICO.md` |
| Decisiones justificadas (por qué DeepL, por qué multilingual_v2, por qué no LangGraph) | `docs/decisiones/ADR-*.md` |
| Umbrales, calibración, mediciones | `docs/EVALUACION.md` |
| `docs/feats/*` | `docs/historico/` con un índice y nota de "documento histórico" |

## Regla para `README.md`

Objetivo: **menos de 300 líneas**. Si un tercero no puede clonar, instalar y
arrancar leyendo sólo el README, el README ha fallado. Si necesita saber por qué
se eligió el reranker, eso no es el README.

## Regla para `CLAUDE.md`

Describe la arquitectura **actual**, no la histórica ni la deseada. **Cada hito
que cambie la arquitectura lo actualiza en el mismo commit.** Un `CLAUDE.md`
desactualizado hace que Claude Code trabaje contra un mapa equivocado, y es la
causa número uno de refactores que se van de madre.

Debe contener: estructura de carpetas, capas y sus responsabilidades, invariantes
del dominio, comandos habituales, y **lo que está fuera de alcance** (§6 de
`PLAN.md`).

## Plantilla de ADR

Ver `docs/decisiones/ADR-000-plantilla.md`. Media página por decisión. **Cinco o
seis ADRs bien hechos valen más que treinta páginas de prosa.**
