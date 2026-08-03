# Privacidad y cumplimiento (RGPD / LOPDGDD)

Este documento describe qué datos salen del dispositivo, hacia dónde, cuánto se
retienen y con qué base legal, más el checklist de cumplimiento. Para una app usada
por **niños de 8–12 años**, esto vale tanto como la solución técnica: un tribunal
español preguntará por aquí. Revisado en el Hito 9 (2026-08-03) y ampliado en el Hito 9.2 (cuentas de
familia con correo del adulto; 2026-08-03).

> **Copia navegable para el adulto:** `frontend-react/public/privacidad.html` es una
> versión de esta misma página que la app enseña al padre/madre (aviso de la foto +
> pestaña Sistema). Este `.md` es la fuente; **mantener ambos en sync** al editar.

## Por qué esto es obligatorio

La Máquina del Tiempo es una app para **menores** (8–12), que puede exponerse por un
**túnel público** (ngrok/Colab), **sube fotos** de cuartos infantiles a un tercero y les
hace **hablar con un LLM**. Entran de lleno el **RGPD** (UE 2016/679) y la **LOPDGDD**
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
| **Cuenta de familia** (correo del adulto, nombre de familia, contraseña) | **No** (se queda en el SQLite local) | — | Persistente en `backend/config_db.sqlite3`: el correo y el nombre en claro, la **contraseña hasheada** (PBKDF2), hasta borrar la cuenta/BBDD | **Ejecución del servicio + consentimiento parental** (identifica a la familia y da un contacto de adulto, H9.2) |
| **Claves API** | No | — | En `.env` (fuera de git); nunca se exportan ni se muestran completas | — |

**Lectura clave:** con **STT local (H7)**, la **voz del niño no sale del PC**; y las fotos
**no se persisten** (H9). El texto de la pregunta y la respuesta sí pasan por proveedores
en la nube (traducción, LLM, TTS). El backend **no guarda historial** de conversaciones.
El **único dato personal que la app almacena** (H9.2) es la **cuenta de familia** (correo
de un adulto + nombre de familia + contraseña **hasheada**), y lo guarda **en el propio
dispositivo** (SQLite local): **no se envía a ningún tercero**. Es el correo del **adulto**
—no del niño—, lo que refuerza el contacto de consentimiento parental y minimiza datos de
menores.
El **LLM por defecto elegido en H6 es Groq (Llama-3.3-70B, EEUU)**: implica una
**transferencia internacional** del texto de la pregunta (ver §Transferencias y las
alternativas UE/local más abajo).

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
  quién se envía, que no se guarda) + **confirmación de adulto** (PIN de adulto si está
  configurado; si no, casilla de responsabilidad).
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
  (retardo fijo + bloqueo temporal por IP). El correo del adulto no sale del dispositivo.
- **Secretos fuera del control de versiones**: las claves viven en `.env` (gitignored),
  nunca en la BBDD ni en los export de configuración.
- **Candado del túnel** (H2) y **PIN de adulto** (H7): los endpoints que cuestan dinero
  van tras un código de acceso; la configuración, tras un PIN.

## Checklist RGPD / LOPDGDD

- [x] **Minimización de datos** (art. 5.1.c RGPD): solo se procesa lo imprescindible
      (pregunta, foto opcional); no se guarda historial. El **único dato personal**
      almacenado es la **cuenta de familia** (correo del **adulto** + nombre de familia +
      contraseña hasheada, H9.2): el mínimo para identificar a la familia y tener un contacto
      de consentimiento; no se pide ningún dato del niño más allá de su nombre de pantalla
      (previsto en fases posteriores).
- [x] **Consentimiento parental** (<14 años, art. 7 LOPDGDD): confirmación explícita de
      adulto antes de subir la **foto** (implementado, H9), por ser el dato sensible que
      sale a un tercero. Para el **chat y la voz** —el núcleo de la app— el consentimiento
      se considera **otorgado por el uso**: un adulto crea la **cuenta de familia** con su
      correo (H9.2) y pone en marcha la app; ese alta por un adulto refuerza el
      consentimiento. La foto es el único paso que exige un gesto explícito adicional.
- [x] **Información transparente** (arts. 13–14 RGPD): esta página se enlaza desde la app
      —en el aviso de consentimiento de la foto y en la pestaña Sistema (zona de adulto)—
      mediante una copia navegable (`frontend-react/public/privacidad.html`).
- [~] **Derecho de supresión** (art. 17): no se persisten historial ni fotos. El único dato
      suprimible es la **cuenta de familia**: hoy se borra a mano (fila de la tabla `familias`
      / fichero SQLite) y el **logout** elimina la sesión del dispositivo; el **borrado de
      cuenta autoservicio** desde la UI queda como trabajo pendiente. La caché de audio local
      es borrable a mano (`backend/.cache/`).
- [ ] **Transferencias internacionales** (cap. V RGPD): el LLM por defecto (Groq, EEUU) y
      opcionalmente el STT/TTS en nube implican transferencia; *a gestionar:* preferir
      proveedores UE (Mistral) o local (Ollama) la elimina, a cambio de calidad/latencia.
- [x] **Medidas técnicas** (art. 32): voz en local (opcional), no persistencia de imágenes,
      secretos fuera de git, anti-inyección, filtro de salida, candado de túnel y PIN de adulto.

## Limitaciones reconocidas

- El STT y el TTS **por defecto** van a la nube (ElevenLabs): para el argumento fuerte de
  privacidad hay que **activar el STT local** (H7). El TTS en local queda como trabajo
  futuro (la calidad en español local es notablemente peor; ver PLAN.md §2).
- No hay verificación de edad real del adulto (la casilla es declarativa); el PIN es la
  barrera más fuerte disponible.
- La lista de términos del filtro de salida es **mínima**, no un servicio de moderación.
- **Borrado de cuenta de familia** (H9.2): aún no hay autoservicio desde la UI; se borra a
  mano en la BBDD. El correo del adulto se guarda **en claro** (es un identificador de
  contacto, no un secreto; la contraseña sí va hasheada). Todo ello vive **en el dispositivo**,
  no en un tercero.
