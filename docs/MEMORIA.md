# Memoria del proyecto — guion y fuentes

Este documento **no es la memoria**: es su esqueleto y el mapa de dónde está ya escrito cada
trozo. La memoria se entrega como documento aparte (Word/PDF con portada, índice y
paginación); esto evita reescribir desde cero lo que la documentación técnica ya contiene.

**Cómo usarlo:** recorre las secciones en orden. Cada una dice qué debe contener, de dónde
sacarlo y qué hay que escribir de nuevo. Lo marcado con ✍️ **no existe en ninguna parte** y
hay que redactarlo; el resto es adaptar prosa ya escrita.

> Extensión orientativa para un capstone: **25–40 páginas** sin anexos. Si sobra material,
> el sitio de los detalles es el anexo, no el cuerpo.

---

## 0. Portada, resumen e índice ✍️

- Título, autor, titulación, tutor, convocatoria.
- **Resumen (abstract)**: 200 palabras. Qué es, para quién, qué se ha construido y qué
  resultado se ha medido. Escríbelo **el último**, cuando ya sepas qué has contado.
- Palabras clave: RAG, LLM, educación infantil, evaluación, RGPD.

## 1. Introducción

| Contenido | De dónde |
|---|---|
| Contexto y motivación | ✍️ (el "para qué sirve" del vídeo, bloque 1) |
| Objetivos del proyecto | `docs/PLAN.md` §0 (prioridades declaradas **antes** de empezar) |
| Alcance: qué entra y qué no | `docs/TRABAJO-FUTURO.md` (lo descartado conscientemente) |

> **Punto fuerte que conviene explotar aquí:** las prioridades se declararon por escrito
> antes de empezar y no se reordenaron a posteriori. Eso es metodología, y se demuestra
> con el fichero.

## 2. Estado del arte / tecnologías

| Contenido | De dónde |
|---|---|
| Qué es RAG, chunking con solape, embeddings, CLIP/T5 | `docs/ANEXO-DIDACTICO.md` (está escrito para explicárselo a alguien que no lo sabe) |
| Panorama de proveedores de IA | `docs/PLATAFORMAS-IA.md` |
| La regla que gobierna las decisiones de IA | `docs/PLAN.md` §2 (pequeños en local, generativos en la nube) |

## 3. Análisis y diseño

| Contenido | De dónde |
|---|---|
| Requisitos funcionales | ✍️ a partir del flujo de 3 pasos y la zona de adulto |
| Arquitectura general + diagramas | `docs/ARQUITECTURA.md` (visión general, secuencia, topología de producción) |
| Modelo de datos | `docs/ARQUITECTURA.md` §"Tablas del SQLite" |
| Decisiones de diseño | `docs/DECISIONES.md` → los **ADR**. Son el material más valioso de la memoria |

> **Cómo usar los ADR sin copiarlos enteros:** en el cuerpo, una tabla de una línea por
> decisión (decisión / alternativa descartada / por qué). Los ADR completos, al anexo. Un
> tribunal valora ver que hubo alternativas y que se eligió con criterio.

## 4. Implementación

| Contenido | De dónde |
|---|---|
| Backend por capas | `docs/ARQUITECTURA.md` + `CLAUDE.md` (capas del backend) |
| El pipeline RAG paso a paso | `docs/ARQUITECTURA.md` + `docs/ANEXO-DIDACTICO.md` |
| El Evaluator (RAG vs GENERAL) | `CLAUDE.md` §"El Evaluator" |
| Frontend y experiencia de usuario | `docs/ARQUITECTURA.md` §"Capa de presentación" |
| Blindaje operativo | `docs/ARQUITECTURA.md` §"Blindaje operativo" |
| Seguridad infantil | ADR-010 |

## 5. Evaluación y resultados ⭐

**La sección que más diferencia una memoria buena de una normal.** Está casi entera escrita
en `docs/EVALUACION.md`:

- Metodología: set dorado de 100 preguntas, métricas deterministas, 3 repeticiones.
- **Línea base inmutable** y progresión hito a hito.
- Estudio de elección de LLM: puertas primero, pesos después, test ciego humano.
- Mediciones de plataforma: concurrencia, latencia de streaming, despliegue sin corte.
- **Limitaciones declaradas.**

> Lleva al cuerpo **dos gráficas**: la progresión de recall/ruteo, y el antes/después de la
> latencia percibida. Son las dos que se entienden de un vistazo.

## 6. Despliegue y operación

| Contenido | De dónde |
|---|---|
| Topología, CI/CD, vuelta atrás, copias | `docs/DESPLIEGUE.md` (resumir; el detalle al anexo) |
| Por qué VPS nativo y no Docker | ADR-015 |
| La app en el móvil (PWA / APK) | `docs/APK-ANDROID.md` + ADR-017 |

## 7. Cumplimiento normativo

Todo en `docs/PRIVACIDAD.md`. **No lo resumas de más**: para una app de menores, esta
sección puntúa. Lleva al cuerpo la tabla de flujos de datos, los dos modos de uso
(doméstico vs publicado) y las limitaciones reconocidas.

## 8. Conclusiones ✍️

- Objetivos cumplidos, uno a uno, contra los del §1.
- **Lo aprendido**, incluido lo que salió mal. Ejemplo defendible: se midió la retirada de
  DeepL esperando simplificar y **empeoró** el retrieval, así que se mantuvo (ADR-014).
  Cambiar de opinión con datos delante es exactamente lo que se quiere demostrar.
- Trabajo futuro: `docs/TRABAJO-FUTURO.md`, resumido.

## 9. Bibliografía y anexos ✍️

- ADR completos, tablas de resultados, guion de la demo, manual de usuario.

---

## Material gráfico que hace falta ✍️

La memoria necesita imágenes y **hoy solo hay una** en `docs/img/`. Mínimo recomendable:

| Figura | Cómo obtenerla |
|---|---|
| Diagrama de arquitectura | Redibujar el ASCII de `ARQUITECTURA.md` en una herramienta de diagramas |
| Diagrama de secuencia de una pregunta | Ídem |
| Capturas del flujo (3 pasos + chat) | Directamente de la app |
| Captura en móvil | DevTools en 390×780 |
| Gráfica de progresión de métricas | De los CSV de `evals/resultados/` |
| Gráfica de latencia antes/después | De `docs/mediciones/H8-latencia-streaming.md` |

---

## Errores típicos que conviene evitar

- **Contar el proceso en vez del resultado.** El tribunal no necesita el diario de hitos:
  necesita qué se construyó, por qué así y qué se midió. Los hitos, al anexo.
- **Pegar código en el cuerpo.** Como mucho, fragmentos de 5–10 líneas cuando ilustren una
  decisión. El resto, al anexo o al repositorio.
- **Esconder las limitaciones.** Están declaradas en `EVALUACION.md` y `PRIVACIDAD.md`;
  llevarlas a la memoria suma, no resta. Un trabajo sin fisuras declaradas parece un trabajo
  sin revisar.
- **Vender lo que no hay.** El APK no está generado, no hay Dockerfile y no hay DPIA. Está
  todo dicho en `TRABAJO-FUTURO.md` con su motivo; decirlo también en la memoria es
  coherencia.
