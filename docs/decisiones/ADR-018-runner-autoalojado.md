# ADR-018 — Runner autoalojado en el VPS, y no un runner de GitHub con clave SSH

- **Estado:** aceptada — el repositorio ya apunta al runner; **el agente se instala en el
  servidor siguiendo [`DESPLIEGUE.md §5.4`](../DESPLIEGUE.md)**.
- **Fecha:** 2026-08-06
- **Fase:** F2 (despliegue) — `docs/DESPLIEGUE.md §5.4`
- **Extiende al [ADR-015](ADR-015-despliegue-nativo-vps.md)** (que decidió *qué* se despliega y
  cómo; esto decide **quién ejecuta** el despliegue).

## Contexto

El despliegue automático de [ADR-015](ADR-015-despliegue-nativo-vps.md) lo ejecutaba un runner
alojado por GitHub que **entraba por SSH** al VPS. Funcionaba y estaba acotado con sensatez —
clave dedicada, registrada con `command="…/desplegar.sh"`, sin pty, como usuario sin
privilegios—, pero arrastraba tres consecuencias que no se pueden quitar con más configuración:

1. **El puerto 22 tiene que estar abierto a internet**, porque la conexión la abre alguien de
   fuera. En un servidor con IP pública eso significa recibir intentos automatizados de login
   desde el primer día (de ahí `fail2ban` en §3.0).
2. **Una clave privada del servidor vive fuera del servidor**, en los secretos de GitHub.
3. **Cada despliegue consume minutos facturables.** Con el plan gratuito y el ritmo de trabajo
   de la fase final, los minutos se agotaron: los `.md` de este mismo repositorio llegaron a
   gastar cuatro corridas completas de `pytest` + `npm run build` sin una línea de código.

El desencadenante fue el tercer punto, pero el que decide es el primero.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| **A. Runner autoalojado en el VPS, solo para el job de despliegue** (elegida) | La conexión la abre el servidor: **el 22 deja de tener que estar abierto** y no hay clave del servidor en GitHub; minutos no facturables; el despliegue sigue disparándose solo con el merge | Un agente más que mantener y actualizar; ejecuta lo que diga el workflow, así que hay que acotar qué puede hacer |
| B. Seguir con SSH desde un runner de GitHub | Cero mantenimiento en el servidor; el `command=` forzado ya acotaba el daño | Obliga a mantener el 22 abierto y la clave fuera; sigue gastando minutos |
| C. Mover **todos** los trabajos al runner autoalojado | Cero minutos facturados | 2 vCPU y 4 GB **compartidos con producción**: un `npm run build` de un PR competiría por la memoria con el backend que está sirviendo, y ya hubo que añadir swap para que el OOM killer no matara el backend durante un despliegue |
| D. Despliegue *pull*: un temporizador en el servidor que mira si hay commits nuevos | No necesita agente de GitHub ni el 22 abierto | Despliega **a ciegas**: sin la garantía `needs: [backend, frontend]`, se publicaría un commit con el CI en rojo. Rompe el invariante de ADR-015 |

## Decisión

**Opción A.** El job `deploy` declara `runs-on: [self-hosted, linux, despliegue]` y ejecuta el
script directamente en el servidor; los dos trabajos de verificación **se quedan en los runners
de GitHub** (opción C descartada por la memoria del VPS).

Para no perder la propiedad que daba el `command=` forzado —"pase lo que pase, esta credencial
solo despliega"—, el agente **no corre como el usuario de la app**: corre como `gha-runner`, que
no puede leer el `.env` ni la base de datos, y su único permiso es una regla de sudoers acotada
a un comando:

```
gha-runner ALL=(mundoaventura) NOPASSWD: /opt/mundoaventura/deploy/desplegar.sh
```

## Qué se descarta, y qué NO arregla esto

- **No da independencia de GitHub.** El trabajo lo sigue repartiendo Actions: durante la
  incidencia del 2026-08-06 un runner propio se habría quedado esperando igual. Lo que no
  depende de GitHub es el despliegue a mano (`./deploy/desplegar.sh`), que sigue ahí.
- **No es más seguro en todos los ejes, y conviene decirlo.** Se gana cerrar el 22 y sacar la
  clave de GitHub; se acepta que quien pueda modificar un workflow del repositorio ejecuta
  código en el servidor. Con un repositorio privado de un solo autor es un intercambio
  razonable; en un repositorio con colaboradores externos —o con PRs desde forks— no lo sería,
  y habría que volver a la opción B.
- **El puerto 22 no se cierra solo.** Es un paso manual y posterior a comprobar que el runner
  despliega (§5.4), dejando la propia IP en la regla y con la consola KVM del proveedor a mano
  por si esa IP cambia.

## Consecuencias

- **Orden de instalación obligatorio:** primero el agente en el servidor, después el merge de
  este cambio. Al revés, el job `deploy` se queda esperando indefinidamente a un runner con la
  etiqueta `despliegue` que no existe, y el merge a `main` no llega a producción.
- Los secretos `VPS_SSH_KEY`/`VPS_HOST`/`VPS_USER`/`VPS_KNOWN_HOSTS` dejan de usarse pero **no
  se borran**: son lo que permite volver a la opción B cambiando una línea.
- El paso "Comprobar el sitio público" del workflow gana valor: ahora se ejecuta **desde el
  propio servidor**, así que comprobar `https://chatmundoaventura.com` verifica de verdad el
  camino completo (DNS público, certificado y Caddy), no solo que el proceso local responde.
- Mantenimiento nuevo, documentado en §5.4: actualizar el agente cuando GitHub lo marque como
  obsoleto, y `journalctl -u actions.runner.*` para ver qué hizo.
