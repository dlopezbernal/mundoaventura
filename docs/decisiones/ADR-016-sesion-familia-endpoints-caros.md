# ADR-016 — Sesión de familia obligatoria en los endpoints que cuestan dinero

- **Estado:** aceptada
- **Fecha:** 2026-08-04
- **Hito:** H9.2 / F2 (despliegue permanente)
- **Extiende y sustituye parcialmente al [ADR-001](ADR-001-candado-tunel.md)**: el candado sigue,
  pero deja de ser la única barrera.

## Contexto

El ADR-001 se escribió para un modelo de amenaza concreto: un **túnel efímero** (ngrok/Colab)
levantado a ratos, con un atacante realista que es *un bot que descubre la URL y prueba
endpoints*. Contra eso, `X-Access-Code` + rate limit por IP + cupo diario bastaban, y el propio
ADR-001 cerraba con "revisar si el proyecto pasa a un despliegue permanente en la nube".

Eso ya ha pasado: desde el 2026-08-05 la app vive en un **dominio público permanente**
([ADR-015](ADR-015-despliegue-nativo-vps.md)). Y en ese escenario el candado tiene un agujero
que no es una sospecha, es una propiedad del diseño:

> **`ACCESS_CODE` viaja dentro del bundle de la SPA.** El frontend lo lee de `VITE_ACCESS_CODE`
> en tiempo de construcción, así que acaba incrustado en el JavaScript que se descarga cualquiera
> que abra la web. Es **público de facto**. Lo mismo dentro del APK, que se descomprime en dos
> órdenes (`docs/APK-ANDROID.md §6`).

Por tanto `/api/generate`, `/api/generate-on-photo`, `/api/ask` y `/api/transcribe` —los que
gastan crédito de Replicate, Groq, DeepL y ElevenLabs— estaban al alcance de cualquiera con
`curl` y treinta segundos de herramientas de desarrollo. El rate limit y el cupo acotan la
factura, pero no impiden el uso.

La restricción de producto del ADR-001 sigue vigente y es dura: **no puede haber un login
delante de un niño de 9 años**. La diferencia es que ahora ya no hace falta inventarlo: desde
H9.2 la app tiene **cuentas de familia** con sesión persistente, y el niño **ya ha entrado**
antes de llegar a jugar.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| A. Seguir solo con el candado (statu quo ADR-001) | Cero trabajo; cero fricción | El código es público de facto: no cierra nada en un dominio permanente |
| B. **Exigir además la sesión de familia ya existente** (elegida) | Autenticación real, con credencial personal y token de vida larga; **fricción cero** — el niño ya inició sesión y `client.ts` ya manda el token en todas las peticiones | Deja de poderse probar la API desde `/docs` sin token |
| C. OAuth / proveedor de identidad externo (Google, Auth0) | No hay que custodiar contraseñas | Obliga a la familia a tener cuenta de un tercero; una transferencia de datos personales más en una app de menores; desproporcionado |
| D. Sustituir el rate limit por IP por rate limit por token | Cuota justa por familia | Es una mejora **ortogonal**, no una barrera: sin autenticación, un token se inventa igual |

## Medición

No se midió (decisión de diseño, no de rendimiento). El criterio es el cambio de **modelo de
amenaza**: de "un bot que escanea una URL que estará viva dos horas" a "un dominio indexable,
permanente, cuyo código de acceso está publicado en el bundle". La comprobación es de
comportamiento y está en la suite: `tests/test_acceso.py` verifica que los tres endpoints caros
cortan con **401** sin `X-Family-Token`, que un token inventado también da 401, que un token
válido atraviesa la puerta, que el toggle a `false` reproduce el comportamiento anterior y que
los **catálogos GET siguen siendo públicos**.

## Decisión

**Opción B.** Los endpoints caros llevan una **segunda dependencia** además del candado:
`familias_service.requiere_familia_flujo_nino`, que exige un `X-Family-Token` válido → **401**.

En `backend/main.py` las dos barreras se componen explícitamente, y los routers caros se montan
con la lista combinada:

```python
_acceso = [Depends(acceso_service.requiere_codigo_acceso)]
_familia = [Depends(familias_service.requiere_familia_flujo_nino)]
_caros = _acceso + _familia          # generation, conversacion, transcription
```

Se gobierna con **`config.EXIGIR_SESION_FAMILIA`** (`.env`, **por defecto `true`**). Es un toggle
de **despliegue**, y deliberadamente **NO es un ajuste editable en caliente**: la autenticación
no debe poder apagarse desde el menú de configuración. Con `false` se reproduce el
comportamiento previo (solo candado), útil para trastear desde `/docs` o para atacar la API por
HTTP desde un banco de pruebas.

**Qué NO cambia para el niño:** nada. La app ya exige iniciar sesión de familia para jugar, el
token vive en `localStorage` y `client.ts` lo manda en todas las peticiones, incluido
`askStream`. No hay una pantalla de login nueva a mitad de partida. Lo que se cierra es la
llamada directa de un desconocido.

## Qué se descarta y por qué

- **Seguir solo con el candado (A):** el ADR-001 ya aceptaba explícitamente que el código "no es
  un secreto fuerte" y que su objetivo era *frenar el escaneo automático*, no resistir a quien
  inspeccione el tráfico del navegador. Ese objetivo era el correcto para un túnel; en un
  dominio permanente, dejarlo como única barrera sería confundir una molestia con una defensa.
- **OAuth / identidad externa (C):** resolvería un problema que no tenemos (ya hay credencial:
  email del adulto + contraseña con PBKDF2, con login endurecido contra fuerza bruta) y añadiría
  uno que sí importa en una app de menores: otra transferencia de datos personales a un tercero,
  con su capítulo de RGPD. Ver [`PRIVACIDAD.md`](../PRIVACIDAD.md).
- **Rate limit por token en vez de por IP (D):** no es una alternativa, es una mejora que
  **depende** de esta decisión — solo hay tokens fiables que contar porque ahora hay
  autenticación. Sigue pendiente (el cupo diario de imágenes es hoy **global**, no por familia:
  una familia intensiva puede agotar el de todas). Anotado en
  [`TRABAJO-FUTURO.md`](../TRABAJO-FUTURO.md).
- **Quitar el candado ahora que hay sesión:** se mantiene como **defensa en profundidad**. Es
  gratis, corta antes de tocar la lógica de sesión, y sigue frenando el escaneo automático que
  ni siquiera llega a intentar autenticarse.

## Consecuencias

- **Código:** `familias_service.requiere_familia_flujo_nino` (nueva dependencia, devuelve la
  familia o `None` si el toggle está apagado; se monta por su efecto de cortar con 401);
  composición `_caros = _acceso + _familia` en `main.py`. **Sin dependencia nueva.**
- **`.env`:** `EXIGIR_SESION_FAMILIA` (por defecto `true`). No aparece en `settings_service`.
- **Superficie que sigue pública:** los `GET` de los catálogos (`/api/personajes`,
  `/api/ubicaciones`) y `/health`. El flujo del niño necesita leer los catálogos antes de tener
  con qué jugar, y no cuestan dinero.
- **Coste asumido:** `/docs` deja de servir para probar los endpoints caros a mano sin obtener
  antes un token de familia. Para eso está el toggle en `false` en local.
- **Tests:** `tests/test_acceso.py` (barrera 1 candado + barrera 2 sesión). Un fixture *autouse*
  de `tests/conftest.py` deja el toggle en `false` para toda la suite —la mayoría de los tests
  van de rate limit o de validación, no de autenticación— y los tests de la puerta lo reactivan
  explícitamente.
- **Revisar si:** se abre el registro a familias desconocidas de verdad. Entonces la conversación
  pasa a ser el **cupo por cuenta** (D) y la verificación de correo obligatoria, no la puerta.
