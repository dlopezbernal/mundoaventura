# Medición F3 — Drenado de peticiones en vuelo al desplegar

> **Estado: arnés listo, medición pendiente de ejecutar en el servidor.**
> No depende de escribir código: depende de reiniciar el servicio real, y eso
> solo se puede hacer en el VPS.

## Qué queda por responder

La medición [F2](F2-despliegue-sin-corte.md) resolvió el problema de las
conexiones **nuevas**: con activación por socket de systemd, las peticiones que
llegan mientras el backend reinicia esperan en el socket en vez de recibir un
502. Medido: **10 % de peticiones perdidas → 0 %**.

Pero eso no dice nada de las respuestas que **ya habían empezado**. El chat
responde por SSE y tarda segundos: si el servicio reinicia a mitad, ¿se corta la
respuesta que el niño está leyendo?

## El mecanismo existe

`deploy/mundoaventura.service` lo contempla:

```ini
KillSignal=SIGINT
TimeoutStopSec=30
```

`SIGINT` es lo que uvicorn interpreta como apagado ordenado (deja de aceptar
conexiones nuevas y termina las que tiene), y los 30 segundos le dan margen para
hacerlo. Lo que faltaba no era el mecanismo: era **comprobar que funciona**.

## Cómo medirlo

`scripts/bench_drenado.py` abre una pregunta en streaming, espera a recibir los
primeros tokens (para asegurarse de que la respuesta está de verdad en curso),
dispara el reinicio del servicio con el stream abierto, y anota si llegó el
evento `fin` o si el stream murió a medias.

En el servidor, como el usuario de la app:

```bash
cd /opt/mundoaventura

# Control: sin reiniciar nada. Debe dar 100 % de supervivencia.
uv run python scripts/bench_drenado.py --n 3 --reiniciar-con "" \
    --email <cuenta-de-prueba> --password <contraseña>

# La medición de verdad.
uv run python scripts/bench_drenado.py --n 5 \
    --reiniciar-con "sudo systemctl restart mundoaventura" \
    --email <cuenta-de-prueba> --password <contraseña>
```

El permiso de sudoers que ya tiene el usuario de la app
(`systemctl restart mundoaventura`, ver [`DESPLIEGUE.md §3.9`](../DESPLIEGUE.md))
es exactamente el que hace falta; no hay que abrir nada nuevo.

## Criterio de aceptación (declarado ANTES de medir)

- **Control:** 3/3 respuestas completas. Si esto falla, el arnés está mal y el
  resto de la medición no vale.
- **Con reinicio:** ≥ 4 de 5 respuestas llegan a su evento `fin`. Por debajo de
  eso, el drenado no está cumpliendo su función y habría que revisar
  `TimeoutStopSec` frente a la duración real de las respuestas (TOTAL p95 ≈ 5,6 s
  según [H8](H8-latencia-streaming.md), holgadamente por debajo de los 30 s, así
  que el margen debería sobrar).

## Resultados

_Pendiente._ Cuando se ejecute, pegar aquí la salida del bench y la fecha.

| Modo | Corridas | Sobreviven | % |
|---|---|---|---|
| Control (sin reinicio) | — | — | — |
| Con reinicio | — | — | — |
