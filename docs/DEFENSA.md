# Guion de defensa — demo y vídeo

Qué enseñar, en qué orden y con qué plan B, tanto para la **defensa en sala** como para el
**vídeo grabado** que se entrega con la memoria. El trabajo futuro está en
[`TRABAJO-FUTURO.md`](TRABAJO-FUTURO.md); la memoria, en [`MEMORIA.md`](MEMORIA.md).

> **✅ El vídeo ya está grabado y publicado:** [`youtu.be/SrndAsGQIw0`](https://youtu.be/SrndAsGQIw0)
> (miniatura en [`img/Miniatura_2_Tecnica_MundoAventura.png`](img/Miniatura_2_Tecnica_MundoAventura.png),
> enlazada desde la §8 del [`README.md`](../README.md)).
> Lo de abajo se conserva **tal cual se escribió antes de grabar**: sigue siendo el guion de la
> defensa en sala, y deja constancia del método (ensayo, plan B por paso y qué no puede salir
> en cámara) en vez de reescribirlo a posteriori para que cuadre con lo grabado.

> **Regla de oro del ensayo:** ensayar contra **`https://chatmundoaventura.com`**, que es lo
> que se entrega, no contra `localhost:5173`. En producción no hay CORS ni candado que
> pelear (SPA y API comparten origen) y el micrófono funciona porque hay HTTPS válido —
> justamente los tres problemas que el guion antiguo intentaba esquivar con un túnel.
> Ensayar **≥ 2 veces de principio a fin** antes de grabar.

## Preparación

- [ ] `curl -s https://chatmundoaventura.com/health` en verde: `status: ok`,
      `token_configurado: true`, `deepl_ok: true`, `elevenlabs_ok: true`.
- [ ] **Saldo en los tres proveedores que se van a usar en vivo**: Replicate (imagen),
      **Groq** (el LLM que responde el chat, ganador de H6) y ElevenLabs (voz). ~10 € de
      saldo compran tranquilidad.
- [ ] Índice del RAG construido en el servidor (si no, el chat responde sin fundamento).
- [ ] Una cuenta de familia ya creada **con DOS perfiles de niño** — con uno solo, la
      pantalla "¿Quién juega?" **no aparece** y se pierde el paso 2.
- [ ] Escena de reserva ya generada, por si la generación tarda o falla.
- [ ] **Sesión de Admin ya abierta** en otra pestaña si se va a enseñar (va tras contraseña,
      y con 2FA activo no da tiempo a teclear el código en cámara).
- [ ] Para el tramo móvil: el teléfono con la app **sin instalar todavía** (ver trampa abajo).

## El guion (≈ 7 minutos)

| # | Acción | Qué se enseña | Tiempo |
|---|---|---|---|
| 1 | Abrir `chatmundoaventura.com` → **login de familia** | La app va detrás de una cuenta; no es anónima. De paso, el enlace a la **política de privacidad** | 0:30 |
| 2 | Señalar **"◇ INSTÁLALA EN TU DISPOSITIVO ◇"** e instalarla | Es una **PWA instalable**: icono, splash y sin barra del navegador | 0:30 |
| 3 | Pantalla **"¿Quién juega?"** → elegir un perfil | Multi-perfil; el chat se personaliza con el nombre y el género | 0:20 |
| 4 | **"Selecciona tu personaje"** → girar el carrusel → **`SIGUIENTE ▶`** | Catálogo desde la BBDD, no del código. **Se oye el sonido de giro** | 0:25 |
| 5 | **"Selecciona tu mundo"** → elegir lugar → **`¡GENERAR! ▶`** | Combinación libre lugar × personaje | 0:25 |
| 6 | Esperar la escena (animación "ABRIENDO EL PORTAL…") | Generación en la nube. **Suena el bucle de "generando" y el chime al terminar** | 0:40 |
| 7 | Pregunta **fundamentada** ("¿qué comías?") | Respuesta **RAG en streaming**, palabra a palabra + voz. Desplegable **"📚 ¿De dónde lo he sacado?"** | 0:50 |
| 8 | Pregunta **fuera de dominio** ("¿cuánto es 2+2?") | No alucina anclado: ruteo RAG vs GENERAL/SIN_INFO | 0:30 |
| 9 | **Micrófono**: tocar 🎙️ → hablar → **tocar otra vez para enviar** | Entrada por voz (STT). **No hay paso de confirmación**: se envía directo | 0:40 |
| 10 | Volver al paso 2 → carta **"MI FOTO"** → aparece el **consentimiento** | Consentimiento parental con **PIN de familia**; la foto **no se guarda** | 0:40 |
| 11 | Mostrar la **misma URL en el móvil** (o DevTools en modo dispositivo) | Responsive real: barra mini de escena + chat a pantalla completa | 0:40 |
| 12 | (Si sobra tiempo) 🛡️ Admin → **Personajes → Documentos** y **Auditoría** | Configuración sin código; base de conocimiento; registro de uso con purga | 0:50 |

**Cierre (25 s):** "Todo lo pesado corre en la nube; lo que toca los datos del menor —voz,
preguntas— puede correr en local. Cada mejora está medida contra una línea base, y lo que no
se midió está declarado como tal."

> **Si hay que recortar a 5 minutos**, caen en este orden: 12, 11, 10. Nunca 7 ni 8: son el
> núcleo del proyecto.

## Plan B por paso

| Si falla… | Síntoma | Plan B |
|---|---|---|
| **El servidor o el dominio** | La URL no carga | Levantar el backend en local (`uv run uvicorn backend.main:app`) + `npm run dev`, y demostrar en `localhost` — que también es contexto seguro, así que el micro sigue funcionando |
| **Internet / la nube** | El LLM o el TTS no responden | **Modo local total:** `LLM_PROVIDER=openai` + `LLM_BASE_URL=http://localhost:11434/v1` (**Ollama**), TTS local (**Kokoro**), `STT_PROVIDER=local`. Se cambia en 🛡️ Admin → pestaña **IA** (el LLM) y **Voz** (STT/TTS), sin reiniciar |
| **El botón de instalar no aparece** | La app ya estaba instalada, o el navegador no lo ofrece | Es el comportamiento correcto: solo se pinta si se puede instalar. Desinstalar antes, usar un perfil limpio de Chrome, o enseñar [`APK-ANDROID.md`](APK-ANDROID.md) |
| **Generación de imagen** | La escena tarda demasiado o falla | Usar la **escena de reserva**; seguir con el chat, que no depende de la imagen |
| **Micrófono** | Permiso denegado o no disponible | El micro se deshabilita solo, con aviso; **seguir por texto** |
| **STT local (GPU)** | Error de DLL cuBLAS/cuDNN | El **fallback a la nube es automático**; no hay que tocar nada en vivo |
| **Cuota / free tier** | 429 de un proveedor | Claves de pago ya cargadas. El rate limit responde **en personaje**, nunca un 429 crudo al niño |
| **DeepL** | Error de traducción en el chat | Sin plan B en caliente: es obligatorio. Por eso está en el checklist de preparación |

---

# Grabación del vídeo con OBS

## Escenas y fuentes

Una sola escena basta:

1. **Captura de pantalla** (o de ventana del navegador) a 1920×1080.
2. **Audio del escritorio** — *imprescindible*. Sin esta fuente **no se oirán ni los efectos
   de sonido ni la voz del personaje**, que son la mitad de lo que se está demostrando.
3. **Micrófono** para la narración.
4. (Opcional) **Cámara** en un recuadro pequeño. Muchos tribunales piden ver al ponente.

Comprueba en el mezclador que **las dos barras de audio se mueven** antes de grabar de
verdad: graba 20 segundos, reprodúcelo y escúchalo. Es el fallo más común y solo se descubre
al terminar.

## Ajustes

- Salida **MP4**, 1080p, 30 fps. Nada de resoluciones raras: el tribunal lo verá en un portátil.
- Cierra notificaciones, correo y todo lo que pueda emerger en pantalla.
- Navegador **sin barra de marcadores** y con perfil limpio.

## Qué NO puede salir en cámara

- El **`.env`**, la terminal donde se vea una clave, o la pestaña **🛡️ Admin → APIs**: aunque
  las claves salen enmascaradas, el botón 👁 las revela y no conviene tenerlo cerca del ratón.
- Tu **correo personal real**: crea una cuenta de familia con un correo de demostración.
- La **contraseña de administración** al teclearla (pre-autentica antes de grabar).

## Grabar el tramo móvil

Tres opciones, de más a menos fiable:

1. **DevTools en modo dispositivo** (F12 → icono de móvil, 390×780). Es lo más controlable y
   se ve perfectamente en el vídeo. Suficiente para demostrar el responsive.
2. **Espejar el móvil** por USB (`scrcpy`) y capturar esa ventana. Es lo más honesto porque
   se ve la app instalada de verdad, sin barra del navegador.
3. **Grabar la pantalla del móvil** aparte y montarlo después.

Si el tiempo aprieta, la opción 1 y decir en voz alta que también funciona instalada.

## Estructura sugerida del vídeo (10–12 min)

| Bloque | Qué contar | Minutos |
|---|---|---|
| **1. Para qué sirve** | El problema: acercar historia y ciencia a niños de 8–12 con algo que les enganche. Enseñar la app funcionando 20 s antes de explicar nada | 1:00 |
| **2. Cómo está hecho** | Diagrama de `ARQUITECTURA.md`: SPA React ↔ FastAPI ↔ nube. La regla que gobierna todo: modelos pequeños en local, generativos grandes en la nube | 1:30 |
| **3. Demo** | El guion de arriba, entero | 7:00 |
| **4. Problemas y cómo se resolvieron** | Elegir tres, no doce (ver abajo) | 2:00 |
| **5. Estado final y qué falta** | Está en producción con despliegue continuo; y lo que no está, con su motivo, de `TRABAJO-FUTURO.md` | 0:30 |

## Los tres problemas que mejor se cuentan

No cuentes doce; cuenta tres, con el número al lado. Estos tienen medición y se entienden
en 40 segundos cada uno:

1. **"El chat tardaba 7–12 segundos en blanco."** → Streaming SSE con la voz por frases.
   **Primer contenido a 0,92 s** (p50). [`mediciones/H8-latencia-streaming.md`](mediciones/H8-latencia-streaming.md).
2. **"El personaje traía las fichas equivocadas."** → Embeddings multilingües + troceado por
   estructura + reranker. **Recall de chunk 78,2 % → 90,9 %**, ruteo 66,7 % → 82,2 %.
   [`EVALUACION.md`](EVALUACION.md).
3. **"¿Y si un documento le dice al personaje que ignore sus instrucciones?"** → Las fichas
   entran delimitadas y el prompt las trata como datos, nunca como órdenes. Corrida
   adversarial: **0 fallos de 18**. [ADR-010](decisiones/ADR-010-seguridad-infantil.md).

Si hay que elegir uno solo, el 1: es el que se **ve** en la propia demo.

---

## Preguntas previsibles del tribunal

**¿Por qué ese LLM y no otro?**
→ Se eligió con método, no por moda: **puertas primero** (seguridad 0 fallos, idioma,
legibilidad, latencia), **pesos después** (calidad 50 / latencia 30 / coste 20), y un **test
ciego humano** para desempatar finalistas. Ganó `groq-llama70b`. Detalle en el
[ADR-007](decisiones/ADR-007-eleccion-llm.md) y [`EVALUACION.md §9–10`](EVALUACION.md).

**¿Cómo sabéis que ha mejorado?**
→ Hay una **línea base inmutable** (`BASELINE.csv`) y cada cambio se compara contra ella. El
retrieval subió de **78,2 % a 90,9 %** de recall de chunk y el ruteo de **66,7 % a 82,2 %**.
Tabla de progresión en [`EVALUACION.md`](EVALUACION.md).

**¿Cualquiera puede gastaros el saldo de Replicate con un `curl`?**
→ No. Los endpoints que cuestan dinero llevan **dos** barreras: el candado `X-Access-Code` y
una **sesión de familia** válida (`EXIGIR_SESION_FAMILIA`, por defecto activo). El candado
solo no bastaría, porque viaja dentro del bundle de la SPA y es público de facto. Más rate
limit por IP y un cupo diario de imágenes.
[ADR-016](decisiones/ADR-016-sesion-familia-endpoints-caros.md).

**¿Qué pasa con los datos de los niños?**
→ De cada niño se guarda solo el **nombre de pila** y opcionalmente el sexo. La **foto no se
persiste** y el **audio tampoco**. La voz puede procesarse **en local** (STT local). Hay
cuenta de familia con consentimiento parental y borrado autoservicio. Y está declarado lo que
no se ha hecho: no hay DPIA ni contratos de encargo, porque es un proyecto académico. Todo en
[`PRIVACIDAD.md`](PRIVACIDAD.md) y el [ADR-011](decisiones/ADR-011-arquitectura-hibrida.md).

**¿Por qué no usasteis un framework de agentes (LangGraph, etc.)?**
→ Decisión **consciente**: el Evaluator se escribió a mano, es simple, está medido y se
defiende. Un framework añadiría dependencia y opacidad sin resolver un problema que tenemos.

**¿Por qué no está en Docker?**
→ [ADR-015](decisiones/ADR-015-despliegue-nativo-vps.md): instalación nativa con `uv` + systemd +
Caddy sobre un único VPS. Se asume la contrapartida —falta un `Dockerfile` y no hay entorno
de pruebas— y está en el trabajo futuro. A cambio, el despliegue es sin corte (10 % de 502 →
0 %, medido) y con vuelta atrás automática.

**¿Y una limitación de verdad?**
→ Varias, y no se esconden: el **juez LLM no se validó** (< 85 % de acuerdo), así que el
desempate lo hizo el test ciego humano; el **recall a nivel de fichero está saturado**, por
eso gobierna el de chunk; la **tabla WER del STT local** no se hizo porque hace falta grabar
voces infantiles reales; y el consentimiento del chat se infiere del uso en vez de pedirse
expresamente. Lista completa en [`EVALUACION.md`](EVALUACION.md) y
[`PRIVACIDAD.md`](PRIVACIDAD.md).
