# Privacidad y cumplimiento (RGPD / LOPDGDD)

Este documento describe qué datos se guardan, dónde, hacia dónde salen, cuánto se
retienen y con qué base legal, más el checklist de cumplimiento. Para una app usada
por **niños de 8–12 años**, esto vale tanto como la solución técnica: un tribunal
español preguntará por aquí.

Revisado en el Hito 9 y ampliado en el Hito 9.2 (2026-08-03). **Revisión mayor el
2026-08-06 tras el despliegue en producción**, que cambió la premisa del documento (ver
justo debajo) e incorporó el envío de correo por un tercero.

> **Copia navegable para el adulto:** `frontend-react/public/privacidad.html` es una
> versión de esta misma página que la app enseña al padre/madre y que se enlaza desde la
> pantalla de acceso. Este `.md` es la fuente; **mantener ambos en sync** al editar — el
> HTML es el que ve el usuario final, así que corregir solo el `.md` no arregla nada.

## Dos modos de uso, y no tienen la misma privacidad

Hasta el 2026-08-05 este documento podía decir que los datos "se quedan en el
dispositivo". **Ya no es cierto**, y la distinción es ahora el eje del documento:

| | **Instalación doméstica** | **Servicio publicado** |
|---|---|---|
| Dónde corre | El PC de la familia (o un túnel puntual) | VPS propio en `chatmundoaventura.com` |
| Dónde vive el SQLite | En ese mismo PC | **En el servidor**, bajo control del operador |
| Quién es responsable del tratamiento | La propia familia | **Quien opera el servidor** |
| Correo del adulto | No sale de la máquina | Se guarda en el servidor **y se envía a Brevo** para el código de verificación |

**Lo que se entrega y se demuestra es el segundo modo.** Todo lo que sigue se lee, por
defecto, en clave de servicio publicado; cuando algo solo aplica a la instalación
doméstica, se dice expresamente.

> **Responsable del tratamiento.** En el servicio publicado es el titular del despliegue
> (el autor del proyecto), contactable en la dirección de correo desde la que la app envía
> los avisos. Este proyecto es un trabajo académico sin explotación comercial; si el
> servicio se abriera a familias reales más allá de la evaluación, harían falta un aviso
> legal completo con identidad y domicilio, un canal formal para ejercer derechos y el
> registro de actividades de tratamiento (art. 30).

## Por qué esto es obligatorio

MundoAventura es una app para **menores** (8–12) publicada en internet, que **sube fotos**
de cuartos infantiles a un tercero, les hace **hablar con un LLM** y guarda el **nombre de
pila de cada niño**. Entran de lleno el **RGPD** (UE 2016/679) y la **LOPDGDD**
(LO 3/2018), que en España fija el **consentimiento parental por debajo de los 14 años**
(art. 7). Por eso el consentimiento del adulto y la minimización de datos son requisitos,
no adornos.

## Flujos de datos

| Dato | ¿Sale del dispositivo? | Destino | Retención | Base legal |
|---|---|---|---|---|
| **Voz del niño** (audio del micro) | **No** si `STT_PROVIDER=local` (H7, faster-whisper en el PC); **sí** con el STT en nube (por defecto `elevenlabs`) | ElevenLabs / Groq (solo si STT en nube) | No se guarda localmente; en nube, según el proveedor | Consentimiento |
| **Texto de la pregunta** | Sí | DeepL (traducción ES→EN) + proveedor de LLM (Replicate/OpenAI-compat) | No se persiste en el backend | Consentimiento |
| **Foto de la habitación** | Sí (solo si se usa "mi foto") | Replicate | **No se persiste** localmente: se procesa en memoria y se descarta (verificado, ver §técnicas) | **Consentimiento parental** (pantalla de aviso + confirmación de adulto, H9) |
| **Respuesta del personaje** (texto) | Sí, para la voz | ElevenLabs (TTS) si el personaje tiene voz | El texto no se persiste; el mp3 se **cachea en disco local** (`backend/.cache/tts/`, regenerable, sin datos del niño) | Consentimiento |
| **Historial del chat** | No | — | Vive solo en memoria del navegador; se borra al recargar o empezar de nuevo. El backend no lo guarda | — |
| **Cuenta de familia** (correo del adulto, nombre de familia, contraseña) | Se **guarda en el servidor**; el correo además se **envía a Brevo** al verificar | Brevo (relé SMTP, UE) | En `config_db.sqlite3` del servidor: correo y nombre en claro, **contraseña hasheada** (PBKDF2), hasta borrar la cuenta | **Ejecución del servicio + consentimiento parental** (identifica a la familia y da un contacto de adulto, H9.2) |
| **Perfiles de niños** (**nombre de pila y sexo**) | Se guarda en el servidor **y el nombre viaja con cada pregunta** | Proveedor de LLM (y DeepL, dentro del texto) | En la columna `ninos` de la fila de la familia, hasta borrar la cuenta o el perfil | **Consentimiento parental** — los da de alta el adulto |
| **Código de verificación** (OTP) | Se envía por correo | Brevo | `codigo_hash` + caducidad en la fila de la familia; se borra al verificar | Ejecución del servicio |
| **Sesión de familia** | El token vive en el navegador | — | En el servidor solo su **hash SHA-256**; **90 días** de vida | Ejecución del servicio |
| **Auditoría de uso** (H10, opcional) | Se guarda en el servidor | — | Tabla `auditoria`. **Metadatos** por defecto (evento, familia, niño, personaje/ubicación, hora, **IP**); el **texto de preguntas/respuestas** solo si el adulto activa `AUDITORIA_CONTENIDO`. Purga automática por `AUDITORIA_RETENCION_DIAS` (def. 90) y con la supresión de la cuenta | **Interés legítimo del responsable / consentimiento** — actividad de un menor: activar el contenido exige propósito claro |
| **Preferencias en el navegador** | No salen del navegador | — | Ver §Almacenamiento en el navegador | Estrictamente necesarias / preferencia del usuario |
| **Claves API** | No | — | En `.env` del servidor (fuera de git); nunca se exportan ni se muestran completas | — |

**Lectura clave, en tres frases.**

1. **Lo que NO se guarda nunca:** la **foto** (se procesa en memoria y se descarta), el
   **clip de audio** del micrófono (ni en el navegador ni en el backend) y el **historial
   del chat** del niño (vive en memoria del navegador y se pierde al recargar).
2. **Lo que sí se guarda, y en el servidor:** la cuenta de familia (correo del adulto,
   contraseña hasheada) y los **perfiles de los niños con su nombre de pila y su sexo**.
   Es el dato más sensible de la app y por eso se minimiza al máximo: nombre de pila, sin
   apellidos, sin fecha de nacimiento, sin foto de perfil, sin correo del menor.
3. **Lo que sale hacia terceros:** el texto de la pregunta (DeepL + LLM), la voz si el STT
   es en nube, la foto si se usa, el texto de la respuesta para el TTS, y el **correo del
   adulto** hacia Brevo al verificar la cuenta.

> **El nombre del niño viaja con cada pregunta.** Se usa para personalizar la respuesta del
> personaje ("¡Hola, Alba!") y el género gramatical. Eso significa que el nombre de pila del
> menor llega a **DeepL** y al **proveedor de LLM**. Es una decisión de producto consciente:
> se puede desactivar dejando el perfil sin nombre, a costa de perder la personalización. El
> nombre se sanea con lista blanca antes de entrar al prompt, para que no sirva de vector de
> inyección.

El **LLM por defecto elegido en H6 es Groq (Llama-3.3-70B, EEUU)**: implica una
**transferencia internacional** del texto de la pregunta (ver §Transferencias y las
alternativas UE/local más abajo).

## Almacenamiento en el navegador

La app guarda cinco cosas en el navegador del dispositivo. Ninguna se envía a terceros, y
todas son necesarias para que el servicio funcione o para respetar una preferencia, así que
quedan **exentas del consentimiento de cookies** (art. 22.2 LSSI) — pero hay que declararlas:

| Clave | Almacén | Qué es |
|---|---|---|
| `mdt_family_token` | localStorage | Token de sesión de la familia, **en claro y con 90 días de vida** (en el servidor solo está su hash). Es lo que evita volver a pedir la contraseña |
| `mdt_admin_token` | sessionStorage | Token de administración; **se borra al cerrar la pestaña** |
| `mdt_nino_activo` | localStorage | **Nombre de pila del niño** que juega, para no volver a preguntarlo |
| `mdt_onboarding_saltado_<id>` | localStorage | Si esa familia saltó el alta del primer perfil |
| `mdt_sonido` | localStorage | Preferencia de sonido (`"0"` = silenciado) |
| `mundoaventura-v1` | Cache Storage | Ficheros estáticos de la app (service worker); sin datos personales |

**Al cerrar sesión** se borran el token de familia y el niño activo. **El borrado de la
cuenta no limpia el navegador**: para eliminar también estos restos hay que borrar los
datos del sitio desde el propio navegador. Está dicho así en el apartado de supresión.

## Proveedores: quién entrena con los datos y quién no

Elegir proveedor es también una decisión de privacidad (enlaza con el **ADR-007**, estudio
de LLMs):

- **Ollama local** (LLM 100% local): ni la pregunta ni la respuesta salen del PC. **El
  mejor argumento de privacidad**; su coste es calidad/latencia (modelo 4B).
- **Mistral** (Francia): proveedor europeo sujeto a RGPD; argumento de soberanía del dato.
- **Gemini (tramo gratuito)**: Google **puede usar las entradas para entrenar**. En una
  app infantil **se decide conscientemente** y se documenta; no se hereda por defecto.
- **Replicate / Groq** (EEUU): transferencia internacional; conviene revisar sus términos.

**Decisión tomada (ADR-007, estudio de H6, cerrado el 2026-08-02):** el proveedor por
defecto es **Groq (Llama-3.3-70B)**, elegido por calidad de respuesta (test ciego con 5
personas) y latencia. Groq procesa en **EEUU**, así que la config por defecto **hace una
transferencia internacional** del texto de la pregunta (no de la voz si el STT es local,
ni de la foto, que no se persiste). Es una decisión **consciente**: quien priorice la
soberanía del dato puede cambiar en caliente a **Mistral** (UE) o **Ollama local** (nada
sale del PC) sin tocar código, a cambio de calidad/latencia. El texto de la pregunta
también pasa por **DeepL** (traducción, Alemania/UE) en todos los casos.

## Medidas técnicas ya tomadas

- **Voz procesada en local** (H7): con `STT_PROVIDER=local`, la voz del niño no sale del PC.
- **Fotos no persistidas** (H9): `generation_service.generar_en_foto` procesa la imagen
  **solo en memoria** (bytes → data URI → Replicate); nunca escribe la foto en disco ni en
  la BBDD. El endpoint la lee con tope de tamaño y no la almacena.
- **Consentimiento parental antes de subir foto** (H9): pantalla de aviso (qué se hace, a
  quién se envía, que no se guarda) + **confirmación de adulto** — el **PIN de familia** si
  está configurado; si no, casilla de responsabilidad.
- **Defensa anti-inyección de prompt** (H9): los documentos del RAG entran delimitados
  (`<documento>…</documento>`) y el prompt de sistema los trata como **datos, nunca
  órdenes** — un documento malicioso no puede reescribir al personaje.
- **Filtro de salida en la vía GENERAL** (H9): el texto no fundamentado del LLM se
  comprueba (idioma, longitud, términos inapropiados) antes de entregarse al niño.
- **Sin historial persistido**: el backend no guarda las conversaciones; el historial vive
  en el navegador y se borra al recargar.
- **Cuentas de familia con credenciales protegidas** (H9.2): la contraseña se guarda
  **hasheada** (PBKDF2-HMAC-SHA256 con sal, nunca en claro) y el token de sesión persistente
  solo se guarda como **hash** (SHA-256); el login está protegido contra fuerza bruta
  (retardo fijo + bloqueo temporal por IP → 429).
- **Tres credenciales distintas, cada una con su alcance** — conviene no confundirlas:

  | Credencial | Qué protege | Cómo se guarda |
  |---|---|---|
  | Contraseña de familia | Entrar a la app | PBKDF2 con sal |
  | **PIN de familia** (4 dígitos) | Subir la foto y editar el perfil de la familia | PBKDF2, hasheado |
  | Contraseña de administración (≥ 8) **+ 2FA TOTP opcional** | La configuración global | PBKDF2; el secreto TOTP es una clave reservada que **nunca se exporta** |

- **Sesión obligatoria en los endpoints que cuestan dinero** (`EXIGIR_SESION_FAMILIA`, por
  defecto activo): el candado `ACCESS_CODE` viaja dentro del bundle de la SPA, así que es
  **público de facto** y no sirve como autenticación. Sin sesión de familia válida, generar
  imágenes o preguntar devuelve 401.
- **Secretos fuera del control de versiones**: las claves viven en `.env` (gitignored),
  nunca en la BBDD ni en los export de configuración.
- **HTTPS obligatorio en producción**: además de proteger el tránsito, es lo que permite que
  funcione el micrófono (`getUserMedia` exige contexto seguro).

## Checklist RGPD / LOPDGDD

- [x] **Minimización de datos** (art. 5.1.c RGPD): solo se procesa lo imprescindible
      (pregunta, foto opcional); el chat del niño no se guarda. El dato personal
      almacenado de base es la **cuenta de familia** (correo del **adulto** + nombre de
      familia + contraseña hasheada, H9.2). La **auditoría de uso (H10)** añade actividad
      de la familia/niño, pero **minimizada**: metadatos por defecto, el **contenido** de
      preguntas/respuestas es **opt-in** (`AUDITORIA_CONTENIDO`) y todo tiene **retención
      configurable** (`AUDITORIA_RETENCION_DIAS`, purga automática) — se puede desactivar
      por completo (`AUDITORIA_ACTIVA`).
- [x] **Consentimiento parental** (<14 años, art. 7 LOPDGDD): confirmación explícita de
      adulto antes de subir la **foto** (implementado, H9), por ser el dato sensible que
      sale a un tercero. Para el **chat y la voz** —el núcleo de la app— el consentimiento
      se considera **otorgado por el uso**: un adulto crea la **cuenta de familia** con su
      correo (H9.2) y pone en marcha la app; ese alta por un adulto refuerza el
      consentimiento, y con `EMAIL_VERIFICACION` activo se **verifica ese correo con un
      código** (confirma que un adulto controla el buzón). La foto es el único paso que
      exige un gesto explícito adicional.
      **Limitación declarada:** "otorgado por el uso" es una base más débil que un
      consentimiento explícito e informado por cada tratamiento. Un servicio real debería
      pedir al adulto una aceptación expresa del tratamiento del chat y la voz durante el
      alta, no inferirla. Está en las limitaciones reconocidas, no se disimula.
- [x] **Información transparente** (arts. 13–14 RGPD): esta página se enlaza desde la app
      —en el aviso de consentimiento de la foto, en la pantalla de acceso y en la pestaña
      Sistema— mediante una copia navegable (`frontend-react/public/privacidad.html`).
      Incluye la identidad del responsable y los destinatarios de los datos.
- [x] **Encargados del tratamiento** (art. 28): el servicio se apoya en encargados —Brevo
      (correo), Replicate (imagen), Groq (LLM), DeepL (traducción), ElevenLabs (voz)— y se
      usan bajo sus condiciones de servicio. **Limitación:** al ser un proyecto académico
      no se han firmado contratos de encargo específicos; un servicio real los necesitaría.
- [ ] **Derechos de acceso, rectificación, portabilidad, oposición y limitación**
      (arts. 15, 16, 18, 20, 21): **solo la supresión y la rectificación están
      implementadas** en la interfaz (borrar la cuenta; editar el perfil y los niños desde
      ⚙️ Configuración). No hay exportación de los datos de la familia en formato portable
      ni un canal formal para el resto de derechos. Reconocido como pendiente.
- [ ] **Registro de actividades de tratamiento** (art. 30) y **evaluación de impacto**
      (art. 35): no se han elaborado. Tratándose de datos de menores con registro de
      actividad, una DPIA sería lo esperable en un servicio real; a esta escala y con
      finalidad académica se declara **no realizada**, no "no aplicable".
- [x] **Derecho de supresión** (art. 17): no se persisten fotos ni el chat del niño. Hay
      **borrado autoservicio** de la **cuenta de familia** desde la UI (Configuración →
      "Eliminar la cuenta"): borra la cuenta, los perfiles de los niños, las sesiones **y
      toda su auditoría** (`familias_service.eliminar` → `auditoria_service.eliminar_familia`,
      `DELETE /api/familias/cuenta`). La auditoría, además, se purga sola por retención. El
      **logout** elimina solo la sesión del dispositivo. La caché de audio local es borrable
      a mano (`backend/.cache/`). **El borrado no alcanza al navegador**: las preferencias
      guardadas ahí (ver §Almacenamiento en el navegador) se eliminan borrando los datos del
      sitio.
- [x] **Transferencias internacionales** (cap. V RGPD): **decisión cerrada, no pendiente.**
      La configuración entregada usa **Groq (EEUU)** para el LLM y **ElevenLabs (EEUU)** para
      la voz, así que **sí hay transferencia internacional** del texto de la pregunta —que
      incluye el nombre de pila del niño— y de la respuesta. Se asume conscientemente, con
      dos atenuantes: se eligió por calidad medida (ADR-007) y **es reversible en caliente
      sin tocar código** hacia **Mistral (Francia)** o **Ollama (local, nada sale del
      equipo)**, a costa de calidad y latencia. DeepL (Alemania) y Brevo (Francia) están en
      la UE. Para un despliegue real con familias, la configuración recomendada sería
      Mistral + STT local.
- [x] **Medidas técnicas** (art. 32): sesión obligatoria en los endpoints caros, HTTPS,
      contraseñas y tokens hasheados, voz en local (opcional), no persistencia de imágenes,
      secretos fuera de git, anti-inyección, filtro de salida y límites de subida.

## Limitaciones reconocidas

- El STT y el TTS **por defecto** van a la nube (ElevenLabs): para el argumento fuerte de
  privacidad hay que **activar el STT local** (H7). El TTS en local queda como trabajo
  futuro (la calidad en español local es notablemente peor; ver PLAN.md §2).
- **No hay verificación de edad real** del adulto: la casilla es declarativa y el correo
  verificado solo prueba que alguien controla ese buzón, no que sea el titular de la patria
  potestad. Es la limitación de fondo de casi cualquier app infantil, y aquí no se disimula.
- El consentimiento del **chat y la voz** se infiere del uso (ver checklist); un servicio
  real debería pedirlo de forma expresa durante el alta.
- La lista de términos del filtro de salida es **mínima**, no un servicio de moderación.
- **El nombre de pila del niño se envía a proveedores en EEUU** con cada pregunta, para
  personalizar la respuesta. Es minimización parcial: se envía el nombre, nunca apellidos ni
  fecha de nacimiento.
- **El correo del adulto se guarda en claro** (es un identificador de contacto, no un
  secreto; la contraseña sí va hasheada) y, en el servicio publicado, **reside en el
  servidor**, no en el dispositivo de la familia.
- **Las copias de seguridad del servidor incluyen el `.env` en claro** dentro de un `.tgz`
  sin cifrar, en el mismo disco. No es solo trabajo futuro: hoy es una exposición real si
  alguien accede al servidor. Ver [`TRABAJO-FUTURO.md`](TRABAJO-FUTURO.md).
- No hay registro de actividades de tratamiento ni evaluación de impacto (art. 30 y 35), ni
  contratos de encargo con los proveedores. Proporcionado a un proyecto académico; no a un
  servicio abierto a familias reales.
