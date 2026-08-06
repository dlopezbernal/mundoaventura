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

## Material gráfico

### Capturas ya hechas ✅

Están en [`img/`](img/), tomadas de la aplicación funcionando de verdad (con una cuenta de
demostración, escena generada real y respuesta real del LLM):

| Fichero | Qué muestra | Dónde encaja |
|---|---|---|
| `app-01-acceso.png` | Pantalla de acceso, con el manual y la política de privacidad a la vista | §1 o §4 |
| `app-02-quien-juega.png` | Selector de perfil con dos hermanos | §4 (multi-perfil) |
| `app-03-paso1-personaje.png` | Paso 1: carrusel coverflow de personajes | §4 |
| `app-04-paso2-mundo.png` | Paso 2: carrusel de mundos, con la carta "Mi foto" | §4 |
| `app-05-consentimiento-foto.png` | **Consentimiento parental** antes de subir la foto | §7 (cumplimiento) |
| `app-06-generando-escena.png` | El chat ya usable mientras la escena se genera | §4 (decisión de latencia percibida) |
| `app-07-paso3-escena-chat.png` | Escena generada + respuesta del personaje **llamando al niño por su nombre** | §1 y §4 — es la mejor figura del conjunto |
| `app-08-movil-paso3.png` | El mismo paso 3 en móvil: barra mini + chat a pantalla completa | §4 (responsive) |
| `app-09-movil-visor-escena.png` | El visor "⤢ Ver" de móvil | §4 |
| `app-10-configuracion-familia.png` | ⚙️ Configuración: perfiles, PIN y borrado de cuenta | §7 (derechos) |
| `app-11-manual-usuario.png` | El manual en pantalla | §4 |

> La captura 07 es la que mejor resume el proyecto en una imagen: escena generada,
> conversación fundamentada y personalización por nombre, todo a la vez.

### Gráficas ✅

En [`img/`](img/), en **SVG** (vectorial: no se pixela al ampliar ni al imprimir el PDF). Se
regeneran con `uv run python scripts/generar_graficas.py`, así que si algún dato cambia no hay
que redibujar nada:

| Fichero | Qué muestra | Dónde encaja |
|---|---|---|
| `gr-01-progresion-retrieval.svg` | Recall@3 de chunk y acierto de ruteo en las cuatro configuraciones de H4 | §5 — es la figura del "¿cómo sabéis que ha mejorado?" |
| `gr-02-latencia-percibida.svg` | Latencia percibida antes y después del streaming | §5 y §1 — la que explica el problema que más se nota |

> Los colores están **validados para daltonismo** (ΔE 24,7 en protanopía frente a un umbral de
> 8) y las series llevan etiqueta además de color, así que la figura sigue leyéndose impresa en
> blanco y negro o por alguien con visión del color reducida.

### Lo que aún falta ✍️

| Figura | Cómo obtenerla |
|---|---|
| Diagrama de arquitectura | Redibujar el ASCII de `ARQUITECTURA.md` en una herramienta de diagramas |
| Diagrama de secuencia de una pregunta | Ídem |

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
