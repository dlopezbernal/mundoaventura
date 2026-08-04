# ADR-013 — Mantener ElevenLabs (nube) para el TTS, aunque el STT baje a local

- **Estado:** aceptada
- **Fecha:** 2026-08-02
- **Hito:** H7 / H8
- **Rama:** `feat/h7-stt-local`, `feat/h8-streaming`

## Contexto

El [ADR-008](ADR-008-stt-local.md) baja la **transcripción** (STT, voz→texto) a local con
faster-whisper, con un argumento de privacidad de peso: **la voz del niño no sale del PC**.
Surge la pregunta simétrica: ¿debería bajarse también la **síntesis** (TTS, texto→voz) a un
motor local (Piper, Kokoro, XTTS…) por coherencia y coste cero? Hay que decidirlo
explícitamente para no dejar el TTS en la nube "por inercia".

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| **A. TTS local (Piper/Kokoro/XTTS)** | Gratis, offline, coherente con el STT local | Calidad del español **notablemente peor**; voces poco expresivas; XTTS arrastra torch |
| **B. ElevenLabs en la nube (elegida)** | Voces expresivas y con carácter por personaje; Flash es rápido; una sola clave y SDK cubren STT+TTS | Coste por uso; una llamada de red más |

## Medición

Decisión **no medida con un banco formal** (a diferencia del retrieval o el LLM): es un juicio
de **calidad percibida** del español y de expresividad, más una asimetría de privacidad. Se
declara así explícitamente. La señal es cualitativa pero clara: el TTS local en español está
un escalón por debajo, y **la voz es el producto** —dar carácter a cada personaje (Sherlock
grave, Da Vinci cálido) es parte de la experiencia, no un extra.

## Decisión

El **TTS se queda en la nube con ElevenLabs Flash**, con una voz propia por personaje (`voz_id`,
opcional: sin voz = solo texto). El STT sí es seleccionable y su default recomendado es local.

## Qué se descarta y por qué

- **TTS local (A):** descartado por calidad y por el eje del producto. La **asimetría** con el
  STT es deliberada y defendible: el STT procesa un **dato personal del menor** (su voz de
  entrada) → bajarlo a local es una mejora real de privacidad. El TTS produce la **voz de
  salida del personaje** a partir de un texto que ya está en el servidor → no es dato personal
  del niño, así que el argumento de privacidad **no aplica** y manda la calidad.
- **Bajar el TTS "por coherencia":** descartado. La coherencia con el STT local sería estética;
  el coste sería una voz peor en aquello que más define la experiencia.

## Consecuencias

- ElevenLabs sigue siendo un proveedor de la nube (junto a Replicate y DeepL); `ELEVENLABS_API_KEY`
  sigue haciendo falta para la voz de la respuesta aunque el STT sea local.
- **Degradación:** un fallo de TTS (o falta de clave) nunca rompe el chat — `audio_base64` viaja
  como `null` y el texto se sirve igual.
- En streaming (H8) el TTS se sintetiza **por frases** y se **cachea en disco** (`audio_cache`),
  lo que amortigua el coste de las frases fijas y las preguntas repetidas.
- **A revisar si:** aparece un TTS local en español con calidad comparable a Flash, o si un
  requisito de coste cero / offline total pasara por delante de la calidad de voz. En ese caso,
  la nota del **Plan B "sin internet"** de la defensa (Kokoro) sería el punto de partida.
