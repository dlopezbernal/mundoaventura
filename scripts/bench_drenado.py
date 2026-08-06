"""Bench de DRENADO: ¿sobrevive una respuesta ya empezada a un despliegue?

El despliegue sin corte (F2) resolvió el problema de las conexiones NUEVAS: la
activación por socket de systemd hace que, mientras el backend reinicia, las
peticiones entrantes esperen en el socket en vez de recibir un 502. Eso está
medido en `docs/mediciones/F2-despliegue-sin-corte.md` (10 % → 0 %).

Queda otra pregunta, que NO responde aquella medición: una respuesta que YA
había empezado —el SSE del chat, que dura segundos y va llegando por trozos—,
¿se corta cuando el servicio se reinicia por debajo?

El mecanismo para que no se corte existe: `deploy/mundoaventura.service` usa
`KillSignal=SIGINT` + `TimeoutStopSec=30`, que le pide a uvicorn un apagado
ordenado y le da margen para terminar lo que tiene en vuelo. Lo que faltaba era
comprobarlo. Esto lo comprueba.

CÓMO FUNCIONA
    1. Abre una pregunta en streaming y espera a recibir los primeros tokens
       (así sabemos que la respuesta está de verdad en curso, no encolada).
    2. Con el stream abierto, dispara el reinicio del servicio.
    3. Sigue leyendo y anota si llegó el evento `fin` (sobrevivió) o si el
       stream murió a medias (se cortó), y cuántos tokens se recibieron.
    4. Repite N veces y resume.

DÓNDE SE EJECUTA
    En el SERVIDOR, porque necesita poder reiniciar el servicio. El usuario de
    la app tiene concedido exactamente `systemctl restart mundoaventura` por
    sudoers (ver docs/DESPLIEGUE.md §3.9), que es justo lo que hace falta.

USO
    # En el servidor, como el usuario de la app:
    uv run python scripts/bench_drenado.py --n 5 \\
        --reiniciar-con "sudo systemctl restart mundoaventura"

    # Sin reiniciar nada (control): mide cuántas sobreviven sin interferencia.
    uv run python scripts/bench_drenado.py --n 3 --reiniciar-con ""

Si los endpoints exigen sesión de familia (`EXIGIR_SESION_FAMILIA=true`, que es
el valor de producción), pásale `--email` y `--password` de una cuenta de
prueba: el script hace login y usa su token.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import threading
import time

import httpx

# Pregunta larga a propósito: cuanto más dure la respuesta, más ancha es la
# ventana en la que el reinicio la pilla a medias, que es lo que se quiere medir.
PERSONAJE = "t-rex"
PREGUNTA = "cuéntame con mucho detalle cómo era tu vida, qué comías y cómo cazabas"


def _login(cliente: httpx.Client, url: str, email: str, password: str) -> str:
    """Devuelve un token de sesión de familia, o lanza si no se puede entrar."""
    r = cliente.post(
        f"{url}/api/familias/login", json={"email": email, "password": password}, timeout=20.0
    )
    r.raise_for_status()
    token = r.json().get("token", "")
    if not token:
        raise RuntimeError("el login no devolvió token")
    return token


def _una_corrida(
    cliente: httpx.Client, url: str, cabeceras: dict, comando_reinicio: str, tokens_antes: int
) -> dict:
    """Abre un stream, reinicia a mitad y cuenta si llegó hasta el final."""
    t0 = time.perf_counter()
    n_tokens = 0
    reinicio_lanzado = False
    reinicio_en = None
    llego_fin = False
    fallo = None
    disparador: threading.Thread | None = None

    def _reiniciar():
        # En un hilo: `systemctl restart` bloquea hasta que el servicio vuelve, y
        # mientras tanto queremos seguir leyendo el stream.
        subprocess.run(shlex.split(comando_reinicio), check=False)

    try:
        with cliente.stream(
            "POST",
            f"{url}/api/ask/stream",
            headers=cabeceras,
            json={"personaje_id": PERSONAJE, "pregunta": PREGUNTA},
            timeout=90.0,
        ) as r:
            r.raise_for_status()
            evento = None
            for linea in r.iter_lines():
                if not linea.startswith("event:"):
                    continue
                evento = linea[len("event:") :].strip()
                if evento == "token":
                    n_tokens += 1
                    # Esperamos a que la respuesta esté claramente en curso antes
                    # de reiniciar: si disparamos con el primer token, aún podría
                    # estar en una fase que no prueba nada.
                    if not reinicio_lanzado and n_tokens >= tokens_antes and comando_reinicio:
                        reinicio_lanzado = True
                        reinicio_en = time.perf_counter() - t0
                        disparador = threading.Thread(target=_reiniciar, daemon=True)
                        disparador.start()
                elif evento == "fin":
                    llego_fin = True
                elif evento == "error":
                    fallo = "el backend emitió un evento 'error'"
    except Exception as exc:  # noqa: BLE001 — aquí cualquier fallo ES el resultado
        fallo = f"{type(exc).__name__}: {exc}"

    if disparador is not None:
        disparador.join(timeout=60)

    return {
        "sobrevivio": llego_fin,
        "n_tokens": n_tokens,
        "reinicio_en_s": reinicio_en,
        "duracion_s": time.perf_counter() - t0,
        "fallo": fallo,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Bench de drenado de peticiones en vuelo.")
    ap.add_argument("--url", default="http://127.0.0.1:8000", help="Base del backend.")
    ap.add_argument("--n", type=int, default=5, help="Corridas.")
    ap.add_argument(
        "--reiniciar-con",
        default="sudo systemctl restart mundoaventura",
        help="Comando que reinicia el servicio. Cadena vacía = no reiniciar (control).",
    )
    ap.add_argument(
        "--tokens-antes",
        type=int,
        default=8,
        help="Tokens que hay que recibir antes de disparar el reinicio.",
    )
    ap.add_argument("--email", default="", help="Cuenta de familia (si se exige sesión).")
    ap.add_argument("--password", default="", help="Contraseña de esa cuenta.")
    ap.add_argument("--access-code", default="", help="X-Access-Code, si el candado está activo.")
    ap.add_argument("--espera", type=float, default=8.0, help="Segundos entre corridas.")
    args = ap.parse_args()

    cabeceras: dict[str, str] = {}
    if args.access_code:
        cabeceras["X-Access-Code"] = args.access_code

    with httpx.Client() as cliente:
        if args.email:
            cabeceras["X-Family-Token"] = _login(cliente, args.url, args.email, args.password)
            print("Sesión de familia iniciada.")

        if not args.reiniciar_con:
            print("MODO CONTROL: no se reinicia nada.\n")
        else:
            print(f"Reinicio: {args.reiniciar_con}\n")

        resultados = []
        for i in range(1, args.n + 1):
            r = _una_corrida(cliente, args.url, cabeceras, args.reiniciar_con, args.tokens_antes)
            resultados.append(r)
            estado = "SOBREVIVE" if r["sobrevivio"] else "SE CORTA"
            reinicio = f"{r['reinicio_en_s']:.2f}s" if r["reinicio_en_s"] else "—"
            print(
                f"  {i:2d}/{args.n}  {estado:9s}  tokens={r['n_tokens']:4d}  "
                f"reinicio@{reinicio}  dur={r['duracion_s']:.2f}s"
                + (f"  [{r['fallo']}]" if r["fallo"] else "")
            )
            if i < args.n:
                # El servicio necesita estar arriba otra vez antes de la siguiente.
                time.sleep(args.espera)

    vivas = sum(1 for r in resultados if r["sobrevivio"])
    print(
        f"\nResumen: {vivas}/{len(resultados)} respuestas terminaron pese al reinicio "
        f"({100 * vivas / len(resultados):.0f} %)."
    )
    if vivas == len(resultados):
        print("El drenado funciona: ninguna respuesta en vuelo se cortó.")
    elif vivas == 0:
        print("El drenado NO está funcionando: todas se cortaron.")
    else:
        print("Drenado parcial: revisa TimeoutStopSec y la duración de las respuestas.")


if __name__ == "__main__":
    main()
