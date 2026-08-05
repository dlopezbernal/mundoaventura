# Medición — El 502 de los despliegues (Fase 2, deploy)

**Qué se mide:** cuántas peticiones de un usuario real fallan **mientras se reinicia
el backend**, que es lo que ocurre en cada despliegue.

**Por qué importa ahora:** mientras el despliegue era manual, esos segundos de error
los elegía una persona (a las 2 de la mañana, con nadie usando la app). Al
automatizarlo, el corte pasa a ocurrir cada vez que se mergea a `main`, sin que nadie
decida el momento. Antes de automatizar hay que quitarlo.

**Cómo:** 80 peticiones `GET /health` a intervalos de 250 ms **contra el sitio público
por HTTPS** (`https://chatmundoaventura.com/health`, es decir, atravesando Caddy: el
mismo camino que el navegador del niño), reiniciando el servicio a mitad del bombardeo:

```bash
for i in $(seq 1 80); do
  curl -s -o /dev/null -w "%{http_code}\n" https://chatmundoaventura.com/health >> codigos.txt
  sleep 0.25
done &
sleep 3 && systemctl restart mundoaventura
```

## Resultado

| Configuración del servicio | 200 | 502 | Peticiones perdidas |
|---|---|---|---|
| `uvicorn --host 127.0.0.1 --port 8000` (línea base) | 72 | **8** | **10,0 %** |
| `uvicorn --fd 3` + `mundoaventura.socket` | **80** | **0** | **0 %** |

Medido el 2026-08-05 sobre el VPS de producción (Ubuntu 24.04, 2 vCPU). El reinicio
duró ~1 s en ambos casos, así que la diferencia **no** es que uno sea más rápido: es
que en la línea base el puerto se cierra y las conexiones que llegan en esa ventana se
rechazan (`connection refused` → Caddy responde 502).

## Por qué funciona

Con **activación por socket**, quien abre y mantiene el puerto 8000 es **systemd**, no
uvicorn: se lo pasa al proceso como descriptor 3 (de ahí `--fd 3`). Al reiniciar solo el
servicio, el socket **nunca se cierra**; las conexiones que llegan mientras uvicorn
arranca se quedan encoladas en el kernel y se atienden en cuanto el proceso nuevo
acepta. El cliente ve unos segundos de latencia en lugar de un error.

Detalle que anula el efecto si se pasa por alto: la unidad `.socket` **no** debe llevar
`PartOf=mundoaventura.service`. Con esa directiva, reiniciar el servicio reinicia
también el socket — lo cierra, y vuelve el 502.

Como segunda red de seguridad, el `Caddyfile` añade `lb_try_duration 20s`: reintenta la
conexión en vez de devolver un 502. No sustituye a lo anterior (cubre otro caso: que el
backend se caiga de verdad y systemd tarde en relanzarlo), y solo actúa ante fallos al
**conectar**, así que no reintenta respuestas a medias ni interfiere con el SSE del chat.

## Lo que esta medición NO dice

- **No mide las peticiones en vuelo.** Una respuesta que ya había empezado a enviarse
  cuando llegó el `SIGINT` se corta igual; `TimeoutStopSec=30` le da margen a uvicorn
  para terminarlas, pero no se ha medido ese caso. Con SSE (`/api/ask/stream`) es más
  probable, porque la respuesta dura segundos.
- **No es alta disponibilidad.** Sigue habiendo un solo proceso y un solo servidor: si
  el backend se cae y no levanta, la app está caída. Esto solo elimina el corte
  *previsible* del despliegue.
- **`/health` es una petición barata.** No mide qué pasa con una generación de imagen
  de 40 s a mitad de reinicio.
