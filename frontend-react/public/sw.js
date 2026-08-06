/**
 * sw.js — Service worker mínimo
 * ==============================
 *
 * Existe por DOS razones, en este orden:
 *   1. Es requisito de instalabilidad: sin un service worker con manejador de
 *      `fetch`, Chrome no considera la web instalable y Bubblewrap/PWABuilder
 *      no generan el APK. Ver docs/APK-ANDROID.md.
 *   2. De paso, arrancar la app es instantáneo en la segunda visita.
 *
 * Lo que NO pretende es funcionar sin conexión: la imagen la genera Replicate,
 * el chat es un LLM en la nube y la voz es ElevenLabs. Sin red no hay app, así
 * que un caché offline elaborado sería complejidad sin premio.
 *
 * Está escrito a mano, sin vite-plugin-pwa ni workbox: son ~60 líneas y el
 * proyecto no gana nada añadiendo un plugin de build (y su cadena de
 * dependencias) para generarlas.
 *
 * REGLA DE ORO: solo se intercepta lo que se entiende. Todo lo demás cae al
 * `return` sin `respondWith`, es decir, red normal como si el SW no existiera.
 * En particular NO se toca nada de /api/, porque ahí viven el streaming del
 * chat (SSE, se rompería al bufferizarlo) y las subidas de foto y de audio.
 */

const CACHE = "mundoaventura-v1";

// Al instalar, el SW nuevo entra en vigor sin esperar a que se cierren las
// pestañas viejas: los despliegues son frecuentes y no queremos dos versiones.
self.addEventListener("install", () => {
  self.skipWaiting();
});

// Al activar, se borran los cachés de versiones anteriores y se toma el control
// de las pestañas que ya estaban abiertas.
self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    (async () => {
      const nombres = await caches.keys();
      await Promise.all(nombres.filter((n) => n !== CACHE).map((n) => caches.delete(n)));
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (evento) => {
  const peticion = evento.request;

  // Solo GET: las subidas (foto, audio) y las preguntas del chat son POST.
  if (peticion.method !== "GET") return;

  const url = new URL(peticion.url);

  // Solo nuestro origen: las fuentes de Google van por su cuenta.
  if (url.origin !== self.location.origin) return;

  // La API jamás se cachea ni se envuelve: respuestas personalizadas, con
  // token, y una de ellas es un stream que hay que dejar pasar tal cual.
  if (url.pathname.startsWith("/api/") || url.pathname === "/health") return;

  // Navegación (el index.html): RED PRIMERO. Así, un despliegue nuevo se ve en
  // la siguiente carga en vez de quedarse clavado en la versión cacheada; el
  // caché solo entra como red de seguridad si no hay conexión.
  if (peticion.mode === "navigate") {
    evento.respondWith(
      (async () => {
        try {
          const respuesta = await fetch(peticion);
          const cache = await caches.open(CACHE);
          cache.put("/index.html", respuesta.clone());
          return respuesta;
        } catch {
          return (await caches.match("/index.html")) ?? Response.error();
        }
      })(),
    );
    return;
  }

  // Ficheros construidos por Vite (/assets/index-<hash>.js|css): CACHÉ PRIMERO.
  // El nombre lleva el hash del contenido, así que un fichero dado nunca cambia:
  // si está cacheado, es el correcto. Al desplegar cambian los nombres y los
  // viejos se quedan huérfanos hasta el siguiente cambio de CACHE.
  if (url.pathname.startsWith("/assets/")) {
    evento.respondWith(
      (async () => {
        const cacheado = await caches.match(peticion);
        if (cacheado) return cacheado;
        const respuesta = await fetch(peticion);
        if (respuesta.ok) {
          const cache = await caches.open(CACHE);
          cache.put(peticion, respuesta.clone());
        }
        return respuesta;
      })(),
    );
  }

  // Cualquier otra cosa (iconos, privacidad.html, avatares…): sin tocar.
});
