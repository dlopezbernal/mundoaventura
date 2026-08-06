# ADR-017 — App de Android como PWA + TWA, no Capacitor ni React Native

- **Estado:** aceptada — PWA instalable **en producción**; el APK (TWA) queda documentado y sin
  generar, por el keystore (ver Consecuencias).
- **Fecha:** 2026-08-06
- **Hito:** F2 (despliegue) — `docs/APK-ANDROID.md`
- **Depende de:** [ADR-015](ADR-015-despliegue-nativo-vps.md) (dominio propio con HTTPS válido).

## Contexto

El producto es una SPA React que ya funciona bien en el móvil tras el rediseño responsive. Falta
lo que espera cualquiera que oiga "app para niños": **icono en el escritorio, sin barra de
direcciones, y algo instalable** que el tribunal pueda probar en su propio teléfono.

Tres hechos acotan la decisión antes de empezar:

1. **La app no puede funcionar sin conexión, y no es un defecto del empaquetado:** la imagen la
   genera Replicate, el chat es un LLM en la nube y la voz es ElevenLabs. Sin red no hay app.
   Así que el argumento clásico a favor de lo nativo ("funciona offline") aquí no existe.
2. **Las partes frágiles son APIs del navegador:** micrófono (`getUserMedia`), Web Audio de los
   efectos, selector de foto y el **streaming del chat por SSE**. Todas se han probado en Chrome
   contra el servidor real.
3. **Ya hay HTTPS con certificado válido** en un dominio propio (ADR-015), que es exactamente el
   requisito de entrada de una PWA instalable.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| **A. PWA instalable + TWA para el APK** (elegida) | El motor es el **Chrome del dispositivo**: micro, Web Audio y SSE se comportan igual que donde se probaron; **cero divergencia** (cada merge a `main` actualiza la app instalada, porque carga el sitio real); una sola base de código | Sin plugins nativos (háptica, notificaciones push); el APK exige publicar una huella SHA-256 y custodiar un keystore |
| B. Capacitor | Envuelve la misma SPA y **sí** abre la puerta a plugins nativos | El WebView no es la pestaña de Chrome: hay que resolver **CORS** (la app deja de servirse del mismo origen que la API) y volver a pedir el **permiso de micrófono** dentro del WebView. Trabajo real para un beneficio que hoy no se usa |
| C. React Native | App verdaderamente nativa, con acceso a todo el dispositivo | **Reescribir la SPA entera** y mantener **dos bases de código** (web + móvil) para el mismo producto. Desproporcionado |
| D. Solo web, sin instalar | Cero trabajo | Se abre con barra de direcciones y pestañas; no hay nada que dar al tribunal para su móvil |

## Medición

No se midió (decisión de diseño). El criterio es de **superficie de riesgo**: la opción A es la
única en la que las tres APIs delicadas (micrófono, audio, SSE) corren en el mismo motor donde
ya se verificaron, así que no reabre ninguna verificación hecha. B y C sí las reabren todas.

## Decisión

**Opción A.** La web se convierte en **PWA instalable** —`manifest.webmanifest`, iconos 192/512
más uno *maskable*, service worker con manejador `fetch`— y el APK, cuando se genere, será un
**TWA** (*Trusted Web Activity*): un contenedor que abre `https://chatmundoaventura.com` a
pantalla completa con el Chrome del dispositivo, sin barra de direcciones.

- **Instalación desde la propia app:** `src/pwa/instalar.ts` captura `beforeinstallprompt` **en
  el módulo, no en un `useEffect`** (el evento llega antes de que React pinte el login; esperar
  al montaje hacía que el botón no apareciera nunca) y lo expone con `useSyncExternalStore`.
  Desde el login se ofrece "Instalar en Android". Safari y Firefox no implementan el evento: allí
  sencillamente no hay botón, que es el comportamiento correcto.
- **Service worker mínimo y escrito a mano** (`public/sw.js`, ~60 líneas, sin `vite-plugin-pwa`
  ni Workbox). Su primera razón de existir es **ser requisito de instalabilidad**; que la segunda
  visita arranque al instante es una propina. Regla de oro: *solo se intercepta lo que se
  entiende*. Navegación → **red primero** (un despliegue nuevo se ve en la siguiente carga, en
  vez de quedarse clavado en caché); `/assets/` → **caché primero** (llevan el hash del contenido
  en el nombre); **`/api/` y `/health` no se tocan jamás**, porque ahí viven el SSE del chat (se
  rompería al bufferizarlo) y las subidas de foto y de audio.
- **`display: "standalone"`, no `"fullscreen"`:** `fullscreen` esconde también la barra de estado
  y la app dibujaría bajo la barra de gestos de Android, tapando justo el campo de escribir la
  pregunta. `orientation: "any"`, porque la app se ve bien en vertical y horizontal desde el
  rediseño responsive.
- **iOS de propina:** no admite APK ni TWA, pero el manifest y las metaetiquetas `apple-*` hacen
  que "Añadir a pantalla de inicio" en Safari abra la app sin barra, con su icono y su splash.
  Sin trabajo adicional.

## Qué se descarta y por qué

- **React Native (C):** obligaría a **reescribir toda la SPA** y a mantener **dos bases de
  código** —web y móvil— para el mismo producto, con dos sitios donde arreglar cada bug. Todo el
  beneficio nativo que compraría (offline, plugins) es beneficio que esta app no puede usar: sin
  red no hay imagen, ni chat, ni voz.
- **Capacitor (B):** se descarta **hoy**, no para siempre. Es explícitamente la **puerta de
  salida** si algún día hacen falta plugins nativos (háptica, notificaciones push, grabación
  nativa), y todo lo de este ADR se reaprovecha tal cual: es la misma SPA. El precio de cruzar
  esa puerta está identificado: la app deja de servirse del mismo origen que la API, así que hay
  que **configurar CORS** (hoy no hace falta ninguno, ver el `Caddyfile`), y hay que **volver a
  resolver el permiso de micrófono dentro del WebView**, que ya no es el de Chrome. Pagarlo sin
  necesitar todavía ningún plugin sería comprar deuda por adelantado.
- **Un caché offline elaborado:** complejidad sin premio. La app depende de tres servicios en la
  nube; guardar el cascarón no da una app usable, solo una pantalla bonita sin respuestas.
- **`vite-plugin-pwa` / Workbox:** son ~60 líneas de service worker; no se añade un plugin de
  construcción (y su cadena de dependencias) para generarlas.

## Consecuencias

- **Código:** `frontend-react/public/manifest.webmanifest`, `public/sw.js`, iconos
  (`icon-192/512` + `icon-maskable-512`), `public/.well-known/assetlinks.json`,
  `src/pwa/instalar.ts` y el registro del SW en `src/main.tsx` **solo en producción**. **Sin
  dependencia nueva.**
- **Caddy:** `try_files {path} /index.html` implica que un fichero que falte no da 404 sino el
  `index.html` con 200 — por eso `assetlinks.json` se versiona en `public/.well-known/` (Vite lo
  copia a `dist/`, verificado) y la comprobación del §4 de `APK-ANDROID.md` mira el
  `Content-Type`. Además el `Caddyfile` declara a mano el MIME de `.webmanifest`, que Go no trae
  en su tabla interna; **ese cambio del `Caddyfile` no lo aplica `desplegar.sh`**.
- **Pendiente declarado — el APK no está generado.** Falta exactamente el tramo que depende del
  **keystore de firma**: generarlo, empaquetar con PWABuilder o Bubblewrap, sacar la huella
  SHA-256 y publicarla en `assetlinks.json` sustituyendo el valor de ejemplo. No se puede dejar
  hecho de antemano (la huella no existe hasta que existe la clave, y esa clave es una credencial
  que no va al repositorio). El procedimiento completo está escrito en
  [`APK-ANDROID.md`](../APK-ANDROID.md) y anotado en [`TRABAJO-FUTURO.md`](../TRABAJO-FUTURO.md).
  Se pudo aplazar porque **la app instalada desde el navegador se ve y se comporta igual que el
  APK**: lo único que añadiría el APK es poder distribuirlo como fichero o por Play Store.
- **El micrófono es el de Chrome, para bien y para mal:** el permiso se concede por origen y lo
  gestiona Chrome, no el APK. Si el niño lo denegó antes en `chatmundoaventura.com`, la app
  aparecerá muda y se arregla en los ajustes de Chrome, no reinstalando.
- **`VITE_ACCESS_CODE` viaja dentro del APK**, igual que dentro del bundle web (un APK se
  descomprime en dos órdenes). Es la misma razón por la que lo que protege de verdad los
  endpoints caros es `X-Family-Token` → [ADR-016](ADR-016-sesion-familia-endpoints-caros.md).
- **Revisar si:** aparece la necesidad de un plugin nativo (→ Capacitor, con su factura de CORS y
  permisos) o si se quiere publicar en Play Store (→ `.aab`, subir `versionCode` en cada entrega
  y rellenar la sección *Families* enlazando la política de privacidad ya publicada).
