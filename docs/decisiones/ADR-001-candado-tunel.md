# ADR-001 — Candado del túnel: código de acceso + rate limit + cupo, no autenticación fuerte

- **Estado:** aceptada
- **Fecha:** 2026-08-01
- **Hito:** H2
- **Rama:** `feat/h2-blindaje`

## Contexto

El despliegue de la app es un túnel público (ngrok/Colab) mientras dura una prueba
o la defensa. Una URL de túnel se escanea sola en horas, y los endpoints del niño
(`/api/generate*`, `/api/ask`, `/api/transcribe`) **cuestan dinero** (Replicate,
ElevenLabs, DeepL). Sin protección, `POST /api/generate-on-photo` es una tarjeta de
crédito abierta a internet.

La restricción de producto es dura: **no puede haber un login delante de un niño de
9 años**. La protección tiene que ir en otra capa, sin fricción para el niño.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| A. Autenticación real (usuario/contraseña, OAuth) | Seguridad fuerte | Inviable para un niño; sobredimensionado para un túnel puntual |
| B. Sin protección, confiar en que la URL es secreta | Cero fricción | La URL se escanea sola; el crédito queda expuesto |
| C. Código de acceso compartido + rate limit por IP + cupo diario | Sin fricción para el niño (el código va en el `.env` del frontend); frena el escaneo automático y acota el gasto | No es autenticación fuerte: el código viaja en el frontend |

## Medición

No se midió (decisión de diseño, no de rendimiento). El criterio es el modelo de
amenaza: el atacante realista es un **bot que descubre la URL y prueba endpoints**,
no un adversario dirigido. Contra eso, tres barreras baratas bastan.

## Decisión

**Opción C.** Candado en tres capas: (1) cabecera `X-Access-Code` comparada con
`hmac.compare_digest` contra `ACCESS_CODE` del `.env`; (2) rate limit por IP con
slowapi, generoso para el chat y restrictivo para la imagen; (3) tope diario de
generaciones de imagen en SQLite. Al superar límite o cupo, el personaje **responde
en personaje** (chat) o se devuelve un aviso amable (imagen/voz), nunca un 429 crudo.

## Qué se descarta y por qué

- **Autenticación fuerte (A):** rompería la premisa de producto (un niño no mete
  credenciales) y es desproporcionada para un túnel que se levanta a ratos.
- **Nada (B):** el coste de un escaneo es real y directo (crédito de las APIs).
- **PIN de adulto delante del chat:** ya existe para la *configuración*, pero no
  puede ir delante del flujo del niño. Por eso el candado es una capa distinta.

Se acepta explícitamente que el código de acceso **no es un secreto fuerte** (viaja
en el `.env` del frontend). Su objetivo es frenar el escaneo automático, no resistir
a un atacante que inspeccione el tráfico del navegador.

## Consecuencias

- **Código:** `acceso_service.requiere_codigo_acceso` (dependencia en los endpoints
  de coste), `ratelimit.py` (limiter + degradación en personaje), `cuota_service.py`
  (contador diario en la tabla `uso_diario`). Frontend: `X-Access-Code` en `client.ts`.
- **`.env`:** `ACCESS_CODE` (vacío = candado desactivado, cómodo en local),
  `RATE_LIMIT_ASK`/`GENERATE`/`TRANSCRIBE`, `MAX_IMAGENES_DIA`, `MENSAJE_LIMITE`.
  El frontend usa `VITE_ACCESS_CODE`, que debe coincidir.
- **Deuda/limitación aceptada:** el rate limit por IP usa `get_remote_address`; tras
  un proxy/túnel todas las peticiones pueden compartir la IP del proxy (un único
  cubo). Para el objetivo (frenar el escaneo) sigue sirviendo como techo global.
- **Revisar si:** el proyecto pasa a un despliegue permanente en la nube → entonces
  sí tocaría autenticación real y rate limit por token, no por IP.
