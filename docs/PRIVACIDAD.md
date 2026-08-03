# Privacidad y cumplimiento (RGPD / LOPDGDD)

Este documento describe qué datos salen del dispositivo, hacia dónde, cuánto se
retienen y con qué base legal, más el checklist de cumplimiento. Para una app usada
por **niños de 8–12 años**, esto vale tanto como la solución técnica: un tribunal
español preguntará por aquí. Revisado en el Hito 9 (2026-08-03).

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
| **Claves API** | No | — | En `.env` (fuera de git); nunca se exportan ni se muestran completas | — |

**Lectura clave:** con **STT local (H7)**, la **voz del niño no sale del PC**; y las fotos
**no se persisten** (H9). El texto de la pregunta y la respuesta sí pasan por proveedores
en la nube (traducción, LLM, TTS). El backend **no guarda historial** de conversaciones.
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
- **Secretos fuera del control de versiones**: las claves viven en `.env` (gitignored),
  nunca en la BBDD ni en los export de configuración.
- **Candado del túnel** (H2) y **PIN de adulto** (H7): los endpoints que cuestan dinero
  van tras un código de acceso; la configuración, tras un PIN.

## Checklist RGPD / LOPDGDD

- [x] **Minimización de datos** (art. 5.1.c RGPD): solo se procesa lo imprescindible
      (pregunta, foto opcional); no se guarda historial ni se piden datos personales.
- [x] **Consentimiento parental** (<14 años, art. 7 LOPDGDD): confirmación de adulto antes
      de subir la foto (implementado, H9). *Pendiente de decidir:* ¿se exige también para
      el chat/voz, o basta el candado de acceso del túnel?
- [ ] **Información transparente** (arts. 13–14 RGPD): esta página describe los flujos;
      *pendiente:* enlazarla desde la propia app para que el adulto la vea.
- [x] **Derecho de supresión** (art. 17): al no persistirse historial ni fotos, no hay
      datos que suprimir salvo la caché de audio local (borrable a mano: `backend/.cache/`).
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
