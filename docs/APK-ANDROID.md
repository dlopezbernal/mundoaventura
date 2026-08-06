# APK de Android (TWA)

Cómo empaquetar MundoAventura como aplicación de Android instalable, sin reescribir
nada y sin duplicar la aplicación web.

> **Estado: no ejecutado, a propósito.** La PWA instalable —que es el requisito de entrada de
> todo esto— **ya está en producción**, y desde el login se ofrece "Instalar en Android". Como
> la app instalada desde el navegador **se ve y se comporta igual que el APK**, generar el APK
> solo añadiría poder distribuirlo como fichero o por Play Store. Se dejó como trabajo futuro
> (ver [`TRABAJO-FUTURO.md`](TRABAJO-FUTURO.md)); este documento es el procedimiento listo para
> ejecutar cuando haga falta.

---

## 1. Qué es esto y qué no es

La técnica es **TWA** (*Trusted Web Activity*): un APK que abre
`https://chatmundoaventura.com` a pantalla completa, **sin barra de direcciones**, usando el
Chrome del dispositivo como motor. Para el niño es indistinguible de una app nativa: icono
en el escritorio, pantalla de arranque y ventana propia en el multitarea.

**Lo que se gana**

- Icono, splash y ventana propia. Sin barra del navegador ni pestañas.
- **Cero divergencia**: no hay una "versión app" que mantener aparte. Cada `merge` a `main`
  actualiza también el APK ya instalado, porque el APK carga el sitio real. Solo hace falta
  regenerarlo si cambian el nombre, los iconos o el identificador del paquete.
- Las APIs del navegador se comportan **exactamente igual que en Chrome**, que es donde se
  probaron: micrófono (`getUserMedia`), Web Audio de los efectos, selector de foto y el
  streaming del chat por SSE.

**Lo que no se gana**

- **No funciona sin conexión**, y no es un defecto del empaquetado: la imagen la genera
  Replicate, el chat es un LLM en la nube y la voz es ElevenLabs. Sin red no hay app.
- Nada de plugins nativos (háptica, notificaciones push, grabación nativa). Si algún día se
  quieren, el camino es Capacitor — y todo lo de este documento se reaprovecha.

---

## 2. Requisitos, y cuáles ya están hechos

Bubblewrap y PWABuilder no empaquetan una web cualquiera: exigen que sea una **PWA
instalable**. Esa parte ya está en el repositorio:

| Requisito | Dónde | Estado |
|---|---|---|
| HTTPS con certificado válido | Caddy + Let's Encrypt | ✅ ya en producción |
| `manifest.webmanifest` | `frontend-react/public/` | ✅ |
| Iconos 192 y 512 + *maskable* | `frontend-react/public/icon-*.png` | ✅ |
| Service worker con manejador `fetch` | `frontend-react/public/sw.js` | ✅ |
| Registro del service worker | `frontend-react/src/main.tsx` (solo en producción) | ✅ |
| `/.well-known/assetlinks.json` | `frontend-react/public/.well-known/` | ⚠️ **con huella de ejemplo** |

Lo único pendiente es la última fila, y no se puede dejar hecha de antemano: la huella
depende del **keystore de firma**, que se genera al empaquetar y que solo debes tener tú.

> Los tres ficheros de `public/` los copia `npm run build` a `dist/` tal cual, incluida la
> carpeta `.well-known` (verificado: Vite no se salta los directorios que empiezan por punto).
> Es decir, se despliegan solos con el `desplegar.sh` de siempre.

### Decisiones del manifest que conviene conocer

- **`display: "standalone"`, no `"fullscreen"`.** `fullscreen` esconde también la barra de
  estado y la app dibuja bajo la barra de gestos de Android, que taparía justo el campo de
  escribir la pregunta — lo contrario de lo que se acaba de arreglar en el rediseño
  responsive. `standalone` ya quita la barra del navegador, que es el 90 % del efecto.
  Si aun así lo quieres, es cambiar esa palabra y regenerar el APK.
- **`orientation: "any"`.** La app se ve bien en vertical y en horizontal desde el rediseño
  responsive; bloquear la rotación sería tirar ese trabajo.
- **Icono *maskable* aparte** (`icon-maskable-512.png`): el launcher de Android recorta el
  icono a su forma (círculo, cuadrado, gota…). El icono normal tiene esquinas redondeadas
  transparentes que se verían como mordiscos; el *maskable* va a sangre y con la marca al
  56 % para caber en la zona segura. La fuente editable es `icon-maskable.svg`.

---

## 3. Generar el APK

Dos caminos. **En Windows, usa PWABuilder**: compila en la nube y evita instalar Android
Studio y el SDK.

### Opción A — PWABuilder (recomendada)

1. Entra en <https://www.pwabuilder.com> y analiza `https://chatmundoaventura.com`.
2. **Package for stores → Android → Google Play**. Ajusta:
   - *Package ID*: `com.chatmundoaventura.twa` (debe coincidir con `assetlinks.json`).
   - *App name*: `MundoAventura`.
   - *Signing key*: **Create new** la primera vez; a partir de ahí, **Use mine** con el
     keystore que guardaste.
3. Descarga el `.zip`. Dentro vienen el `.apk` (para instalar a mano), el `.aab` (para Play
   Store), el **`signing.keystore`**, el `signing-key-info.txt` con la contraseña y el alias,
   y un **`assetlinks.json` ya relleno con la huella**.

> ⚠️ **Guarda el keystore y su contraseña donde no se pierdan.** Sin ellos no puedes publicar
> una actualización del APK: Android la rechazará por venir firmada con otra clave. Fuera del
> repositorio, obviamente — es una credencial.

### Opción B — Bubblewrap (local, línea de comandos)

```bash
npm install -g @bubblewrap/cli
bubblewrap init --manifest https://chatmundoaventura.com/manifest.webmanifest
bubblewrap build          # la primera vez se descarga el JDK y el SDK de Android
```

Deja `app-release-signed.apk` y el keystore en el directorio del proyecto. Para sacar la
huella del keystore:

```bash
keytool -list -v -keystore android.keystore -alias android | grep SHA256
```

---

## 4. Publicar la huella (el paso que hace desaparecer la barra)

Un TWA abre sin barra de direcciones **solo si el dominio confirma que ese APK es suyo**. Esa
confirmación es Digital Asset Links.

1. Copia el `sha256_cert_fingerprints` que te dio PWABuilder (o `keytool`) dentro de
   `frontend-react/public/.well-known/assetlinks.json`, sustituyendo el valor de ejemplo.
   Es la huella en mayúsculas con los bytes separados por dos puntos.
2. Commit, merge a `main` y el despliegue automático lo publica.
3. Verifica que se sirve bien:

   ```bash
   curl -sI https://chatmundoaventura.com/.well-known/assetlinks.json | grep -i content-type
   #  → application/json     (si dice text/html, el fichero NO existe y Caddy
   #                          está devolviendo el index.html por el try_files)
   ```

4. Comprobación oficial:
   <https://developers.google.com/digital-asset-links/tools/generator>

Después, instala el APK. **Si aparece la barra de direcciones, la verificación ha fallado**:
casi siempre es la huella mal copiada, o el APK instalado firmado con otro keystore.

---

## 5. Distribución

Para la defensa **no hace falta Google Play**: sube el `.apk` a algún sitio accesible y se
instala de lado (Android pedirá permitir "instalar apps desconocidas" para el navegador). Es
lo más rápido para que el tribunal lo pruebe en su propio móvil.

Si algún día va a Play Store: se sube el `.aab`, hay que subir el `versionCode` en cada
entrega, y al ser una app dirigida a menores toca rellenar la sección de *Families* y enlazar
la política de privacidad, que ya está publicada en `/privacidad.html`.

---

## 6. Trampas

- **El micrófono es el de Chrome.** El permiso se concede por origen y lo gestiona Chrome, no
  el APK. Si el permiso se denegó antes en Chrome para `chatmundoaventura.com`, la app
  aparecerá muda. Se arregla en Ajustes de Chrome → Configuración de sitios, no reinstalando.
- **`try_files {path} /index.html` en el Caddyfile.** Cualquier ruta inexistente devuelve el
  `index.html` con un 200, así que un `assetlinks.json` que falte no da 404: da HTML, y la
  verificación falla sin decir por qué. De ahí la comprobación del `Content-Type` del §4.
- **El tipo MIME del `.webmanifest`** no está en la tabla interna de Go, así que Caddy podría
  servirlo como `application/octet-stream`. Chrome se lo traga igual, pero los validadores lo
  marcan; por eso el `Caddyfile` lo declara explícitamente. **Ese cambio del `Caddyfile` no lo
  aplica `desplegar.sh`**: hay que copiarlo a mano en el servidor una vez.

  ```bash
  cp /opt/mundoaventura/deploy/Caddyfile /etc/caddy/Caddyfile
  caddy validate --config /etc/caddy/Caddyfile
  systemctl reload caddy
  ```

- **El dispositivo necesita Chrome 72 o superior.** Si no lo tiene, el APK sigue abriendo, pero
  como pestaña de navegador con su barra.
- **`VITE_ACCESS_CODE` viaja dentro del APK**, igual que dentro del bundle de la web. Un APK
  se descomprime en dos comandos, así que el candado sigue sin ser autenticación: lo que
  protege de verdad los endpoints que cuestan dinero es `X-Family-Token`.

---

## 7. De paso, el iPad

iOS no admite APK ni TWA, pero el manifest y las metaetiquetas `apple-*` de `index.html`
hacen que **"Añadir a pantalla de inicio"** en Safari abra la app sin barra del navegador,
con su icono y su splash. Sin instalar nada y sin trabajo adicional.
