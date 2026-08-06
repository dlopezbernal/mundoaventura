# Despliegue en VPS

Cómo poner MundoAventura en un servidor propio con dominio y HTTPS, de forma
permanente (a diferencia del túnel puntual de Colab/ngrok que se usó durante el desarrollo).

Los ficheros de configuración están en [`deploy/`](../deploy/): la unidad de systemd, el
`Caddyfile` y el script de actualización. Este documento es el procedimiento que los usa.

---

## 1. Qué se despliega

```
        Internet
           │  HTTPS (443)
           ▼
   ┌───────────────────────┐
   │  Caddy                │  TLS automático (Let's Encrypt)
   │  · sirve la SPA       │  frontend-react/dist/  (ficheros estáticos)
   │  · proxy /api /health │──┐
   └───────────────────────┘  │  HTTP local, 127.0.0.1:8000
                              ▼
                    ┌────────────────────────┐
                    │  uvicorn (systemd)     │
                    │  backend.main:app      │
                    │  1 worker              │
                    └────────────────────────┘
                              │
              SQLite · ChromaDB · documentos · caché TTS
                        (todo en disco local)
                              │
                              ▼
           Replicate · Groq/LLM · DeepL · ElevenLabs  (nube)
```

Dos decisiones que conviene entender antes de tocar nada:

- **La SPA y la API van en el mismo origen.** Caddy sirve los estáticos y reenvía `/api`
  y `/health` al backend. Consecuencia: `VITE_BACKEND_URL` se deja **vacío** y no hay CORS
  que pelear.
- **El backend no se expone directamente.** Escucha solo en `127.0.0.1:8000`. Lo único
  abierto a internet son los puertos 80 y 443 de Caddy.

---

## 2. El servidor

Este despliegue corre sobre:

| | Servidor actual | Mínimo viable |
|---|---|---|
| SO | **Ubuntu 24.04.4 LTS** (AMD64) | Debian 12 / Ubuntu 22.04 |
| RAM | **4 GB** | 2 GB (renunciando al reranker) |
| vCPU | **2** | 1 |
| Disco | **128 GB** (HDD) | 20 GB |
| Dominio | **chatmundoaventura.com** | — |

Tres cosas que estas cifras deciden por nosotros:

- **Ubuntu 24.04 ya trae Python 3.12**, que es justo lo que exige `pyproject.toml`
  (`>=3.12,<3.13`). No hay que compilar ni añadir PPAs.
- **Con 4 GB cabe el reranker.** El `jina-v2` recomendado por el
  [ADR-006](decisiones/ADR-006-reranker.md) son 568M de parámetros ONNX residentes en
  memoria; con 2 GB habría que quedarse en la línea base y perder la mejora de recuperación
  ya medida. Aun así conviene añadir swap (§3.2): 4 GB es holgado para servir, pero justo
  para *construir* la SPA mientras el backend está cargado.
- **El disco es HDD, no SSD.** No afecta al servicio en marcha (SQLite y ChromaDB manejan
  aquí volúmenes pequeños), pero sí a los arranques en frío: la primera carga de los modelos
  ONNX tras un reinicio será notablemente más lenta que en tu PC. Es un motivo más para que
  el servicio esté siempre arriba (`Restart=always`) en lugar de arrancarlo bajo demanda.

**No hace falta GPU.** El STT local (`STT_PROVIDER=local`, faster-whisper) sí la querría;
sin GPU, deja el ajuste en `elevenlabs` o `groq`. Si lo pusieras en `local` sin CUDA,
`stt_service` avisa por log y cae a la nube solo — la app no se queda muda, pero es mejor no
depender de ese fallback en producción.

---

## 3. Instalación desde cero

Todo lo que sigue se ejecuta por SSH **como `root`** (que es el acceso disponible), salvo lo
que va explícitamente con `sudo -u mundoaventura`. Esa distinción no es cosmética: la app
**nunca** debe correr como root — un servicio expuesto a internet que además puede escribir
en todo el sistema convierte cualquier fallo en un compromiso total del servidor.

### 3.0 Antes de nada: endurecer el acceso SSH

Con root habilitado y una IP pública, el servidor recibirá intentos de login automatizados
desde el primer día. Si aún no lo has hecho:

```bash
# 1) Tu clave pública en el servidor (ejecútalo en TU PC, no en el VPS)
#    ssh-copy-id root@chatmundoaventura.com

# 2) Ya en el servidor: desactivar la contraseña, dejar solo la clave
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl restart ssh

# 3) Actualizaciones de seguridad automáticas
apt update && apt install -y unattended-upgrades fail2ban
```

> **No cierres la sesión SSH actual** hasta haber comprobado en **otra terminal** que
> entras con la clave. Si te equivocas en `sshd_config` y cierras, te quedas fuera.

**fail2ban puede banearte a ti el primer día.** Al arrancar lee el `auth.log` reciente, así que
los intentos fallidos que hayas hecho tú mientras configurabas el acceso (contraseñas erróneas,
pruebas con usuarios que no existen) cuentan y te dejan fuera durante el `bantime`. Pon tu IP en
la lista blanca **antes** de que pase:

```bash
cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
ignoreip = 127.0.0.1/8 ::1 TU.IP.PUBLICA.AQUI
bantime  = 1h
findtime = 10m
maxretry = 5
EOF
systemctl restart fail2ban
fail2ban-client get sshd ignoreip     # comprueba que tu IP aparece
```

Si te pasa igualmente: el baneo **caduca solo** (`bantime`), no hace falta rescatar nada. Y ojo
con las IP domésticas dinámicas: esa lista blanca deja de valer cuando tu operador te cambie la IP.

### 3.1 Usuario y directorio de la app

La app corre con un usuario **sin privilegios** cuyo *home* es el propio directorio de la
app. Eso permite endurecer el servicio con `ProtectHome=true` sin romper la caché de
modelos de `~/.cache`.

```bash
adduser --system --group --home /opt/mundoaventura --shell /bin/bash mundoaventura
chown -R mundoaventura:mundoaventura /opt/mundoaventura

# Directorio de copias de seguridad, FUERA del árbol de git (para que un `git clean`
# no se las lleve). Lo crea root porque /opt es suyo y el usuario de la app no puede
# escribir ahí; si falta, `desplegar.sh` aborta en su primer paso. El 750 importa:
# ahí dentro acaban copias del .env, que lleva las claves de los proveedores.
install -d -o mundoaventura -g mundoaventura -m 750 /opt/copias
```

### 3.2 Paquetes base y swap

```bash
apt update && apt install -y git curl ca-certificates
```

**Swap (2 GB).** Con 4 GB de RAM el servicio va sobrado, pero `npm run build` (TypeScript +
Vite) es voraz y se ejecuta con el backend ya cargado en memoria. Un poco de swap evita que
el OOM killer mate el backend en mitad de un despliegue:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
free -h   # debe verse la línea Swap con 2,0Gi
```

**Python 3.12** — Ubuntu 24.04 ya lo trae de serie, que es exactamente lo que exige
`pyproject.toml` (`>=3.12,<3.13`). No hay nada que instalar. Solo hace falta `uv`, y va
instalado **para el usuario de la app**, no para root:

```bash
sudo -u mundoaventura bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u mundoaventura bash -lc 'echo "export PATH=\$HOME/.local/bin:\$PATH" >> ~/.bashrc'
sudo -u mundoaventura bash -lc 'uv --version'
```

**Node 24** (para construir la SPA):

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
apt install -y nodejs
node --version   # debe decir v24.x
```

**Caddy**:

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy
```

### 3.3 Clonar el repositorio

```bash
sudo -u mundoaventura git clone https://github.com/dlopezbernal/mundoaventura.git /opt/mundoaventura
cd /opt/mundoaventura
sudo -u mundoaventura git checkout main
```

**Si el repositorio es privado** (que es el caso), ese `clone` por HTTPS pide credenciales y
falla. Usa una **deploy key de solo lectura** en vez de meter credenciales de tu cuenta en el
VPS: se genera en el servidor, se da de alta en ese repo concreto y no sirve para nada más.

```bash
# En el servidor, como el usuario de la app:
sudo -u mundoaventura bash -lc '
  mkdir -p ~/.ssh && chmod 700 ~/.ssh
  ssh-keygen -t ed25519 -N "" -C "deploy-vps-mundoaventura" -f ~/.ssh/id_ed25519
  ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts
  cat ~/.ssh/id_ed25519.pub'

# Esa pública se da de alta en Settings → Deploy keys del repo (SIN marcar "Allow write
# access"), o desde tu PC con el CLI de GitHub:
#   gh repo deploy-key add clave.pub --repo dlopezbernal/mundoaventura --title "VPS (solo lectura)"

# Y el clonado va por SSH, no por HTTPS:
sudo -u mundoaventura git clone git@github.com:dlopezbernal/mundoaventura.git /opt/mundoaventura
```

Como `/opt/mundoaventura` ya existe (lo creó `adduser`), `git clone` se niega a usarlo si no está
vacío: clona a un temporal y mueve el contenido, o usa `git clone … /tmp/clon && mv /tmp/clon/* /tmp/clon/.[!.]* /opt/mundoaventura/`.

### 3.4 Configurar el backend (`.env`)

```bash
sudo -u mundoaventura cp .env.example .env
sudo -u mundoaventura nano .env
```

Claves y valores que **cambian respecto al desarrollo local**:

| Variable | Valor en el VPS | Por qué |
|---|---|---|
| `REPLICATE_API_TOKEN` | tu token | Generación de imagen |
| `DEEPL_API_KEY` | tu clave | **Obligatoria**: sin ella el chat no responde |
| `ELEVENLABS_API_KEY` | tu clave | Voz (TTS + STT en nube) |
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_BASE_URL` / `LLM_API_KEY` | la config ganadora de H6 (Groq) | [ADR-007](decisiones/ADR-007-eleccion-llm.md) |
| `CORS_ORIGINS` | `https://chatmundoaventura.com` | Vacío = cualquier origen. En internet, acótalo |
| `DEBUG` | `false` | Nada de trazas de prompts en un servidor público |
| `LOG_LEVEL` | `INFO` | `DEBUG` llena el journal |
| `STT_PROVIDER` | `elevenlabs` o `groq` | El VPS no tiene GPU (§2) |
| `MAX_IMAGENES_DIA` | ajústalo a tu presupuesto | Techo duro de gasto en Replicate |
| `EMAIL_VERIFICACION` | `true` + SMTP de Brevo | Ver §6.3 |
| `ACCESS_CODE` | ver §6 | |

Permisos: el `.env` lleva secretos y además **lo reescribe la propia app** cuando el adulto
cambia una clave desde el menú de configuración. Tiene que ser del usuario de la app y no
legible por nadie más:

```bash
chown mundoaventura:mundoaventura /opt/mundoaventura/.env
chmod 600 /opt/mundoaventura/.env
```

### 3.5 Configurar el frontend

```bash
sudo -u mundoaventura cp frontend-react/.env.example frontend-react/.env
sudo -u mundoaventura nano frontend-react/.env
```

```ini
# VACÍO: la SPA y la API comparten origen (Caddy). No pongas aquí la URL del dominio:
# funcionaría, pero convertiría cada llamada en una petición cross-origin innecesaria.
VITE_BACKEND_URL=
VITE_DEBUG=false
# Solo si has definido ACCESS_CODE en el .env del backend (ver §6).
VITE_ACCESS_CODE=
```

> Recuerda que las variables `VITE_*` se **incrustan en el bundle** en tiempo de compilación.
> Cualquiera que abra las herramientas de desarrollo del navegador puede leerlas. No son un
> sitio para secretos.

### 3.6 Instalar dependencias y construir

```bash
cd /opt/mundoaventura
sudo -u mundoaventura bash -lc 'cd /opt/mundoaventura && uv sync --frozen'
sudo -u mundoaventura bash -lc 'cd /opt/mundoaventura/frontend-react && npm ci && npm run build'
```

Si el servidor tiene 2 GB de RAM, `npm run build` (TypeScript + Vite) puede quedarse sin
memoria. Dos salidas: añadir 2 GB de swap (`fallocate -l 2G /swapfile …`) o construir en tu
PC y subir solo `frontend-react/dist/` con `rsync`.

### 3.7 Llevar tu configuración afinada al servidor

**Este paso es fácil de pasar por alto y cambia la calidad del chat.** Los ajustes que se
editan desde el menú de configuración viven en `backend/config_db.sqlite3`, que **está en
`.gitignore`**. Un servidor recién clonado no los tiene: `settings_service` cae a los valores
por defecto de `config.py`, es decir, **la línea base**, no la configuración medida en el
Hito 4. En concreto se perderían `EMBEDDING_BACKEND`, `CHUNKING`, `RERANKER` y sus umbrales,
los prompts editados y el estilo de imagen.

> **El orden importa**: `EMBEDDING_BACKEND` y `CHUNKING` deciden **cómo se construye el
> índice**, así que hay que aplicar los ajustes **antes** del `backend.ingest` de §3.8. Si los
> cambias después, toca reindexar otra vez.

Hay dos vías. La **recomendada** es la de la propia app: Admin → Sistema → **Exportar** en tu
máquina, y **Importar** en el servidor (JSON con ajustes + catálogos, nunca secretos). Requiere
tener el backend ya arrancado en los dos sitios.

La alternativa, sin depender de la UI, es copiar solo las filas que interesan. Lo importante es
qué **no** se copia: nada de cuentas de familia, sesiones, auditoría ni el hash de la contraseña
de admin — el servidor arranca con esos datos limpios.

```bash
# 1) En TU máquina: volcar los ajustes (solo las claves declaradas en _SPEC, para no llevarse
#    admin_pin_hash ni los secretos del 2FA, que son claves reservadas fuera de esa lista).
uv run python - <<'PY' > config_vps.sql
import sqlite3
from backend.services import settings_service as ss
con = sqlite3.connect("backend/config_db.sqlite3")
lit = lambda v: "NULL" if v is None else (str(v) if isinstance(v, (int, float))
      else "'" + str(v).replace("'", "''") + "'")
print("BEGIN;")
for clave, valor in con.execute("SELECT clave, valor FROM settings"):
    if clave in ss._SPEC:          # deja fuera admin_pin_hash, secretos 2FA y claves huérfanas
        print(f"INSERT OR REPLACE INTO settings (clave, valor) VALUES ({lit(clave)}, {lit(valor)});")
print("COMMIT;")
PY

# 2) Subirlo y aplicarlo EN EL SERVIDOR, tras crear el esquema con el seeding.
scp config_vps.sql root@chatmundoaventura.com:/tmp/
sudo -u mundoaventura bash -lc 'cd /opt/mundoaventura &&
  uv run python -c "from backend import seed; print(seed.sembrar_todo())" &&
  uv run python -c "
import sqlite3
con = sqlite3.connect(\"backend/config_db.sqlite3\")
con.executescript(open(\"/tmp/config_vps.sql\", encoding=\"utf-8\").read()); con.commit()"'
```

**Comprueba también los catálogos.** El seeding recrea personajes y ubicaciones desde
`backend/personajes.py` / `ubicaciones.py`, pero **no** conoce lo que hayas creado o editado
desde la UI (una ubicación nueva, un `voz_id` cambiado). Compara las tablas `personajes` y
`ubicaciones` entre tu máquina y el servidor, y porta las diferencias. La vía de
Exportar/Importar sí se los lleva (`GET /api/admin/export` incluye ajustes + ambos catálogos).

**Un detalle que ninguna de las dos vías cubre**: la tabla `documentos` (los metadatos de cada
fichero del RAG). Los ficheros del repositorio sí llegan al servidor con el `git clone`, y el
indexado los lee **del disco**, así que el chat funciona igualmente; pero sin esas filas el visor
de documentos de Admin se ve vacío. Si quieres gestionarlos desde la UI, copia también esa tabla
(mismo procedimiento: `INSERT OR REPLACE INTO documentos …`).

### 3.8 Construir el índice RAG

**Sin este paso el chat no funciona** (`rag_service` solo lee la colección, nunca la
construye). Los documentos de los personajes sí vienen en el repositorio; el índice de
ChromaDB no (está en `.gitignore`, se regenera).

```bash
sudo -u mundoaventura bash -lc 'cd /opt/mundoaventura && uv run python -m backend.ingest'
```

La primera ejecución descarga los modelos de embeddings (ONNX) a `~/.cache`. Tarda unos
minutos y necesita salida a internet.

> El resumen final del `ingest` imprime el ajuste `CHROMA_COLLECTION`, que **no** siempre es la
> colección real (esa la decide `EMBEDDING_BACKEND`). Para verificar de verdad qué se indexó:
> `uv run python -c "from backend.services import vector_store as v; c=v.cliente(); print([(x.name, c.get_collection(x.name).count()) for x in c.list_collections()])"`

### 3.9 Servicio systemd (con socket, para desplegar sin cortes)

Son **dos** unidades. El socket va primero: es quien abre el puerto 8000 y se lo pasa al
proceso, de modo que reiniciar el backend no cierra la escucha y un despliegue no produce
502 (medido: [`mediciones/F2-despliegue-sin-corte.md`](mediciones/F2-despliegue-sin-corte.md)).

```bash
cp /opt/mundoaventura/deploy/mundoaventura.socket  /etc/systemd/system/
cp /opt/mundoaventura/deploy/mundoaventura.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mundoaventura.socket    # abre 127.0.0.1:8000
systemctl enable --now mundoaventura           # arranca uvicorn sobre ese socket
systemctl status mundoaventura
ss -tlnp | grep 8000        # debe verse "systemd", NO "uvicorn": es el socket de systemd
curl -s http://127.0.0.1:8000/health
```

`/health` debe devolver `token_configurado: true`, `deepl_ok: true` y `elevenlabs_ok: true`.
Si alguno es `false`, revisa el `.env` (§3.4) antes de seguir.

El backend arranca con `--fd 3` en vez de `--host`/`--port`: hereda de systemd el socket ya
a la escucha (systemd pasa los suyos a partir del descriptor 3). Consecuencia práctica: los
dos ficheros van **en pareja**. Si algún día vuelves a `--host/--port`, desactiva también el
socket (`systemctl disable --now mundoaventura.socket`) o el arranque fallará con *address
already in use*.

> **Si vienes de una instalación anterior sin socket**, el servicio está ocupando el puerto y
> hay que soltarlo antes de activar la nueva pareja:
> ```bash
> systemctl stop mundoaventura && systemctl daemon-reload
> systemctl enable --now mundoaventura.socket && systemctl start mundoaventura
> ```

**Permiso mínimo para reiniciarse.** `deploy/desplegar.sh` corre como `mundoaventura`, que es
un usuario de sistema sin `sudo`, y su último paso es reiniciar el servicio. En vez de darle
sudo general, se le concede **exactamente esos dos comandos** y nada más:

```bash
cat > /etc/sudoers.d/mundoaventura <<'EOF'
mundoaventura ALL=(root) NOPASSWD: /usr/bin/systemctl restart mundoaventura, /usr/bin/systemctl status mundoaventura
EOF
chmod 440 /etc/sudoers.d/mundoaventura
visudo -c        # debe decir "parsed OK"
```

### 3.10 DNS, cortafuegos y Caddy

Primero el **registro A** del dominio apuntando a la IP del VPS (desde el panel de tu
registrador). Compruébalo con `dig +short chatmundoaventura.com` — hasta que no resuelva, Caddy
no podrá sacar el certificado. (En Windows, `Resolve-DnsName chatmundoaventura.com -Server 8.8.8.8`.)

**Si además hay un registro AAAA (IPv6), tiene que apuntar a una dirección que el servidor
tenga configurada de verdad.** Let's Encrypt valida **por IPv6 primero** cuando existe AAAA, así
que un AAAA que no responde = sin certificado. El caso típico: el proveedor te asigna un **/64
entero** y el AAAA usa una dirección "bonita" del bloque (`…:4f4::1`), mientras que el servidor
solo tiene la autogenerada de netplan. Se arregla añadiéndola en el servidor, no cambiando el DNS:

```bash
ip -6 addr show dev eth0 scope global      # ¿coincide con el AAAA?
ip -6 addr add 2a0a:...:4f4::1/64 dev eth0 # en caliente, para probar
# Y persistente: añádela a la lista `addresses:` de /etc/netplan/50-cloud-init.yaml
# (haz copia antes) y evita que cloud-init la sobrescriba al reiniciar:
echo "network: {config: disabled}" > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
netplan apply
```

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

```bash
cp /opt/mundoaventura/deploy/Caddyfile /etc/caddy/Caddyfile
# Descomenta el bloque `www` del Caddyfile SOLO si existe el registro DNS de www.
caddy validate --config /etc/caddy/Caddyfile
mkdir -p /var/log/caddy && chown -R caddy:caddy /var/log/caddy
systemctl restart caddy
journalctl -u caddy -n 40 --no-pager     # debe verse "certificate obtained successfully"
```

Dos detalles que hacen fallar el arranque de Caddy y cuestan encontrar:

- **`caddy validate` corre como root y CREA el fichero de log** declarado en el `Caddyfile`,
  con dueño `root:root` y permisos 600. Después, el servicio (que corre como `caddy`) no puede
  escribirlo y muere con `permission denied`. De ahí el `chown -R caddy:caddy /var/log/caddy`
  **después** de validar.
- **Caddy tiene que poder leer la SPA.** El *home* del usuario de la app es `/opt/mundoaventura`
  y suele quedar en `750`, que impide a `caddy` atravesarlo. En vez de abrir el directorio a
  todo el mundo, mete a `caddy` en el grupo de la app y cierra a mano lo sensible:

  ```bash
  usermod -aG mundoaventura caddy
  chmod 600 /opt/mundoaventura/.env /opt/mundoaventura/backend/config_db.sqlite3
  systemctl restart caddy      # los cambios de grupo solo aplican al arrancar el proceso
  ```

---

## 4. Verificación

Con el navegador en `https://chatmundoaventura.com`:

1. **Carga la SPA** y el candado del certificado es válido.
2. **Alta de familia** → login → "¿Quién juega?".
3. **Generar escena**: personaje + ubicación → aparece la imagen.
4. **Chat de texto**: la respuesta se pinta **token a token** (si aparece de golpe al final,
   el SSE se está bufferizando: revisa el `flush_interval -1` del `Caddyfile`).
5. **Voz**: el navegador pide permiso de micrófono (esto solo ocurre con HTTPS válido) y la
   respuesta del personaje suena.
6. **Admin** 🛡️: primera contraseña, y si vas a exponer la app, activa el 2FA TOTP.

Si algo falla, el primer sitio donde mirar es `journalctl -u mundoaventura -n 100 --no-pager`.

---

## 5. Operación

Un merge a `main` despliega solo (§5.1). Estos son los comandos de siempre, para cuando quieras
hacerlo a mano o el despliegue automático no esté disponible:

```bash
# Logs en vivo
journalctl -u mundoaventura -f
journalctl -u caddy -f

# Actualizar a la última versión de main (backup + pull + build + reinicio)
sudo -u mundoaventura bash -lc 'cd /opt/mundoaventura && ./deploy/desplegar.sh'
# …y además reconstruir el índice RAG (si cambiaron documentos, EMBEDDING_BACKEND o CHUNKING)
sudo -u mundoaventura bash -lc 'cd /opt/mundoaventura && ./deploy/desplegar.sh --reindexar'
```

**El script decide solo si el despliegue ha ido bien**, que es lo que permite automatizarlo:
anota el commit actual antes del `pull` y, si `/health` no responde tras el reinicio,
**vuelve atrás** a esa versión, reconstruye, reinicia y sale con error. Tres matices
deliberados:

- **La puerta es `status: ok`, no las banderas de los proveedores.** Un `deepl_ok:false`
  casi siempre significa que DeepL está caído, no que este despliegue esté roto; volver
  atrás no lo arreglaría. Esas banderas se avisan por pantalla, no deciden.
- **La vuelta atrás revierte el código, no la BBDD.** Restaurarla borraría los ajustes que
  el adulto haya cambiado desde el menú mientras tanto, y aquí no hay migraciones de esquema
  que deshacer. La copia previa sigue en `/opt/copias/` por si hiciera falta a mano.
- **Si falla la construcción, el servicio en marcha ni se toca**: aún no se ha reiniciado
  nada, así que basta con dejar el árbol como estaba.
- **Todo lo anterior al `git pull` usa solo binarios del sistema** (`git`, `python3`, `tar`).
  No es casualidad: lo que se ejecuta antes de traerse los cambios no puede arreglarse *con*
  esos cambios, así que un fallo ahí deja el despliegue automático incapaz de repararse solo y
  obliga a entrar por SSH. Por eso la copia previa se invoca como `bash …/respaldar.sh` en vez
  de ejecutarla directamente (un bit de ejecución perdido bastó una vez para bloquearlo todo),
  y por eso `uv` y `npm` no aparecen hasta después del `pull`. **Si añades pasos al principio
  del script, mantén esa propiedad.**

### 5.1 Despliegue automático desde GitHub

Un push a `main` (o el botón **Run workflow** de la pestaña Actions) lanza el job `deploy`
de [`.github/workflows/ci.yml`](../.github/workflows/ci.yml): entra por SSH al VPS y ejecuta
`desplegar.sh`. Va en el **mismo** workflow que los tests, con `needs: [backend, frontend]`,
así que **no hay forma de desplegar con el CI en rojo**. `dev` pasa el CI pero no toca el
servidor.

Lo que hace falta configurar, una vez:

**1. Una clave SSH exclusiva para el despliegue** (en tu PC, no en el servidor):

```bash
ssh-keygen -t ed25519 -N "" -C "github-actions-deploy" -f ./deploy_ci
```

**2. Registrarla en el servidor con COMANDO FORZADO.** Este es el punto que hace aceptable
tener una clave del servidor guardada en GitHub: así **no da una shell**. Haga lo que haga
quien la tenga, sshd ejecuta el script de despliegue y nada más.

```bash
# En el servidor, como root — OJO: el usuario es `mundoaventura`, NUNCA root.
mkdir -p /opt/mundoaventura/.ssh && chmod 700 /opt/mundoaventura/.ssh
cat >> /opt/mundoaventura/.ssh/authorized_keys <<'EOF'
command="/opt/mundoaventura/deploy/desplegar.sh",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding ssh-ed25519 AAAA…CONTENIDO_DE_deploy_ci.pub… github-actions-deploy
EOF
chown -R mundoaventura:mundoaventura /opt/mundoaventura/.ssh
chmod 600 /opt/mundoaventura/.ssh/authorized_keys
```

Ese usuario ya tiene el `sudo` limitado a `systemctl restart|status mundoaventura` (§3.9), así
que el daño posible si la clave se filtrara baja de "control del servidor" a "puede
redesplegar". Compruébalo antes de seguir — debe ejecutar el despliegue y **no** darte prompt:

```bash
ssh -i ./deploy_ci mundoaventura@chatmundoaventura.com          # lanza el despliegue
ssh -i ./deploy_ci mundoaventura@chatmundoaventura.com 'whoami' # IGNORA la orden: forzado
```

**3. Los tres secretos del repositorio** (Settings → Secrets and variables → Actions):

| Secreto | Valor |
|---|---|
| `VPS_SSH_KEY` | Contenido de `deploy_ci` (la clave **privada**, entera, con sus líneas `BEGIN/END`) |
| `VPS_HOST` | `chatmundoaventura.com` |
| `VPS_USER` | `mundoaventura` |
| `VPS_KNOWN_HOSTS` | Salida de `ssh-keyscan chatmundoaventura.com` |

`VPS_KNOWN_HOSTS` **no es opcional**: sin fijar la clave del servidor habría que usar
`StrictHostKeyChecking=no`, y entonces cualquiera capaz de interponerse en la conexión recibe
la clave privada de despliegue. Borra `deploy_ci` de tu disco en cuanto lo pegues en GitHub.

**4. (Opcional) Aprobación manual.** El job declara `environment: produccion`. Si en
Settings → Environments le añades un *required reviewer*, cada despliegue se queda esperando
tu visto bueno en la interfaz de GitHub.

**El primer despliegue automático puede fallar, y es normal.** Un comando forzado de SSH no
es una shell de login: no lee `.bashrc`, así que `uv` (que vive en `~/.local/bin`) no está en
el `PATH`. El script lo arregla él mismo… pero la primera vez, el script que corre en el
servidor es todavía el **anterior**, que no lleva esa línea. La secuencia se resuelve sola:

1. Primer intento → hace el `git pull` (que **ya trae el script corregido** al servidor) y
   falla después, en `uv sync`. No ha reiniciado nada: la app sigue intacta.
2. Pulsa **Re-run jobs** en Actions → ahora corre el script nuevo, con el `PATH` arreglado.

Solo pasa al estrenar el despliegue automático (o al actualizar desde una versión anterior a
este cambio). La alternativa es lanzar un despliegue manual desde una shell normal, que sí
tiene `uv` en el `PATH`, y que deja el servidor listo para el siguiente automático.

Lo que **no** hace el despliegue automático, a propósito:

- **No reindexa** el RAG. Es una operación cara y rara vez necesaria; se hace a mano con
  `--reindexar` cuando cambian los documentos, `EMBEDDING_BACKEND` o `CHUNKING`. Mantenerlo
  fuera del comando forzado también lo mantiene simple y auditable.
- **No migra la configuración** (§3.7): esa es una operación de instalación, no de cada día.

**Qué hay que respaldar.** Todo lo importante que NO está en git:

| Ruta | Contiene | ¿Se regenera? |
|---|---|---|
| `.env` | Claves de los proveedores y SMTP | No — **respáldalo** |
| `frontend-react/.env` | Configuración de compilación de la SPA | Trivial, pero se respalda igual |
| `backend/config_db.sqlite3` | Ajustes, catálogos, familias, PIN/2FA, auditoría | No — **respáldalo** |
| `backend/documentos/` | Documentos del RAG subidos desde la UI | Los del repo sí; los subidos **no** |
| `backend/avatares/` | Avatares del carrusel | Sí, pero cada uno cuesta 2 llamadas a Replicate |
| `backend/chroma_db/` | Índice vectorial | Sí (`backend.ingest`, ~1 min) |
| `backend/.cache/` | Audio TTS ya sintetizado, modelos ONNX | Sí |

Las cinco primeras filas son exactamente lo que empaqueta
[`deploy/respaldar.sh`](../deploy/respaldar.sh): **un `.tgz` por copia** (~7 MB), con las rutas
relativas a la raíz de la app, para que restaurar sea un `tar x -C` directo y la copia se pueda
llevar entera a otro servidor.

Dos decisiones del contenido que conviene entender:

- **El índice de ChromaDB no va dentro** aunque no esté en git. Es 100 % derivado de
  `backend/documentos/` y del ajuste `EMBEDDING_BACKEND`, que **sí** se respaldan; restaurar un
  índice viejo sobre unos ajustes nuevos daría malas respuestas **en silencio**, que es peor que
  tardar un minuto en reconstruirlo.
- **`.ssh/` tampoco**, pese a contener la deploy key. Este archivo está pensado para *moverse* a
  otra máquina, y no quieres credenciales de acceso al servidor viajando dentro. Recrearlas son
  dos comandos (§3.3 y §5.1), y al cambiar de servidor conviene rotarlas de todos modos.

El reparto general es: **el `.tgz` restaura los datos; este documento reconstruye el sistema**.
La configuración de systemd, Caddy, ufw o fail2ban no se respalda porque ya está en el
repositorio y en §3.

### 5.2 Copias: cuándo se hacen y cuánto duran

Se disparan desde dos sitios, con la **misma** implementación (para que no haya dos ideas
distintas de qué respaldar, que se desincronicen con el tiempo):

| Cuándo | Etiqueta en el nombre | Para qué |
|---|---|---|
| Antes de cada despliegue | `predespliegue` | Deshacer una actualización que salga mal |
| Cada noche a las 03:30 | `nocturno` | Tener siempre una copia reciente aunque no despliegues |

Sin la nocturna, la copia más reciente sería la del último despliegue: si pasas dos meses sin
tocar el código, pierdes dos meses de cuentas de familia y documentos.

```bash
cp /opt/mundoaventura/deploy/mundoaventura-backup.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mundoaventura-backup.timer

systemctl list-timers mundoaventura-backup     # cuándo toca la próxima
systemctl start mundoaventura-backup.service   # forzar una ahora
journalctl -u mundoaventura-backup -n 30       # cómo fue la última
./deploy/respaldar.sh manual                   # a mano, como el usuario de la app
```

**Por qué un temporizador de systemd y no `cron`.** Sobre todo por `Persistent=true`: si el
servidor estaba apagado a las 03:30, la copia se hace al arrancar; `cron` simplemente se la
salta, y te quedas sin copia justo el día que hubo un problema. Además los fallos quedan en el
journal (mismo `journalctl -u …` que el resto) en lugar de en un correo local que nadie lee.

#### Cifrar las copias (recomendado)

El `.tgz` lleva dentro el **`.env` con todas las claves** de los proveedores y del SMTP. Sin
cifrar, quien consiga leer el disco se las lleva todas de una vez. `respaldar.sh` puede cifrarlo
con **GPG de clave pública**, y esa elección es deliberada: con clave pública el servidor
**crea** copias pero **no puede leerlas**, porque la clave privada nunca ha estado ahí. Con una
contraseña simétrica, esa contraseña tendría que vivir en el servidor y no protegería del
escenario que de verdad importa.

Preparación, **una sola vez**. Los dos primeros comandos van en **tu** máquina, nunca en el
servidor:

```bash
# --- En tu equipo ---
gpg --quick-generate-key "copias-mundoaventura" default default never
gpg --armor --export copias-mundoaventura > publica.asc
scp publica.asc mundoaventura@TU_SERVIDOR:/tmp/

# --- En el servidor, como el usuario de la app ---
gpg --import /tmp/publica.asc && rm /tmp/publica.asc
gpg --list-keys                      # comprueba que aparece
```

Y declara el destinatario en la unidad del temporizador, añadiendo bajo `[Service]`:

```ini
Environment=BACKUP_GPG_RECIPIENT=copias-mundoaventura
```

> **Y vuelve a copiar la unidad desde `deploy/`**, porque el endurecimiento tuvo que cambiar:
> `ProtectSystem=strict` deja todo el sistema en solo lectura salvo lo declarado, y GPG
> necesita escribir en su propio directorio incluso para cifrar. Por eso `ReadWritePaths`
> incluye ahora `/opt/mundoaventura/.gnupg`. Sin eso, la copia **manual** funcionaría (a mano
> el script corre fuera de systemd) pero la **nocturna** fallaría — el peor de los dos mundos,
> porque lo habrías dado por probado.

A partir de ahí las copias salen como `.tgz.gpg`. Para restaurar, en tu equipo:

```bash
gpg -d mundoaventura-AAAAMMDD-HHMMSS-nocturno.tgz.gpg | tar xz -C /ruta/destino
```

> **Guarda la clave privada fuera del servidor y haz copia de ella.** Sin esa clave, las copias
> cifradas son ruido y no hay forma de recuperarlas. Si no defines `BACKUP_GPG_RECIPIENT`, el
> script sigue funcionando pero avisa por `stderr` de que la copia va en claro.

**Retención: 15 días.** Cada ejecución borra los `.tgz` más antiguos, así que la carpeta se
estabiliza en ~105 MB en vez de crecer sin fin. El borrado se acota al patrón
`mundoaventura-*.tgz`: si dejas ahí un fichero tuyo, no se lo lleva por delante.

### 5.3 Restaurar

Sobre una instalación ya montada según §3 (cada `.tgz` lleva dentro un `INVENTARIO.txt` con
estos mismos pasos, la fecha y el commit con el que se hizo):

```bash
systemctl stop mundoaventura
sudo -u mundoaventura tar xzf /opt/copias/mundoaventura-AAAAMMDD-HHMMSS-nocturno.tgz \
  -C /opt/mundoaventura
sudo -u mundoaventura bash -lc 'cd /opt/mundoaventura && uv run python -m backend.ingest'
systemctl start mundoaventura
```

El `ingest` es el paso que no se puede saltar: reconstruye el índice vectorial, que no viaja en
la copia. Comprobado el 2026-08-05 con una restauración real: `PRAGMA integrity_check` en `ok` y
todos los recuentos de tablas idénticos a la BBDD viva.

> **Nunca ejecutes `git clean -fd` en `/opt/mundoaventura`.** El *home* del usuario de la app
> **es** el directorio del repositorio, así que `git status` lista como no rastreados sus
> propios ficheros: `.ssh/` (con la deploy key), `.cache/` (modelos ONNX), `.bashrc`, `.local/`…
> Un `git clean` se los llevaría por delante. Si necesitas limpiar, hazlo con rutas explícitas.

---

## 6. Lo que cambia al pasar de un túnel a internet

El blindaje del [Hito 2](decisiones/ADR-001-candado-tunel.md) se diseñó para un túnel
efímero. Con un dominio permanente hay tres puntos que cambian:

**1. Los endpoints caros exigen sesión de familia** (ya implementado). `ACCESS_CODE` frena
el escaneo automático, pero **no es autenticación**: viaja incrustado en el bundle de la
SPA (`VITE_ACCESS_CODE`), así que cualquiera que abra las DevTools lo lee y puede llamar a
`/api/generate`, `/api/ask` y `/api/transcribe` con `curl`, gastando tu saldo de
Replicate/ElevenLabs.

Por eso esos tres routers llevan una segunda dependencia,
`familias_service.requiere_familia_flujo_nino`, que exige un `X-Family-Token` válido → 401.
La gobierna `EXIGIR_SESION_FAMILIA` en el `.env`, **`true` por defecto**. Para el niño no
cambia nada (la app ya obliga a iniciar sesión antes de jugar, y `client.ts` manda el token
en todas las peticiones); lo que se cierra es la llamada directa de un desconocido.

Sigue siendo un toggle de despliegue y no un ajuste del menú: la autenticación no debe poder
apagarse desde la UI. Ponlo en `false` solo para trastear desde `/docs`. Y no quites el
techo de gasto: `MAX_IMAGENES_DIA` es el que te protege de una familia legítima —o de una
cuenta creada para abusar— que se pase de vueltas.

**2. `EMAIL_VERIFICACION`.** Por defecto está en `false` (cómodo para la demo). En un
servidor abierto significa que cualquiera puede crear cuentas con correos inventados.
Ponlo en `true` y elige un proveedor de envío real (§6.3).

### 6.3 Envío de correo: Brevo desde el dominio propio

El correo del OTP sale por **SMTP** contra un servicio transaccional, **Brevo**, y desde
una dirección **del dominio de la app** (`no-reply@chatmundoaventura.com`). Enviar desde
una cuenta personal de correo tiene dos problemas: da una imagen pobre a la familia que
recibe el mensaje, y los proveedores de correo gratuito limitan y penalizan el envío
automatizado desde un servidor.

La configuración vive en **Admin → Correo** (editable en caliente) y en el `.env`:

| Ajuste | Valor de producción |
|---|---|
| `SMTP_HOST` | `smtp-relay.brevo.com` |
| `SMTP_PORT` / `SMTP_STARTTLS` | `587` / `true` |
| `SMTP_USER` | El login de Brevo (**no** tu correo): algo como `xxxxxxx@smtp-brevo.com` |
| `SMTP_PASSWORD` | La **clave SMTP** de Brevo (no la contraseña de la cuenta) → Admin → APIs |
| `SMTP_FROM` | `no-reply@chatmundoaventura.com` |
| `EMAIL_FROM_NAME` | `MundoAventura` — lo que ve la familia en el remitente |

**Tres cosas hacen fallar el envío con credenciales perfectamente válidas.** Ninguna se
ve en el código, y las tres dan errores que no explican su causa:

**1. El proveedor del VPS bloquea el SMTP saliente.** Es una medida antispam estándar
(netcup, Hetzner, OVH, DigitalOcean…): las conexiones a los puertos 25, 465 y 587 se
descartan y el envío falla con `timed out`. Compruébalo **desde el servidor** antes de
sospechar de tus credenciales:

```bash
for p in 25 465 587 2525; do printf "%s: " $p
  timeout 8 bash -c "exec 3<>/dev/tcp/smtp-relay.brevo.com/$p; head -1 <&3" || echo BLOQUEADO
done
```

Si el 587 está cerrado: ábrelo en el panel del proveedor (ojo con la regla implícita, ver
el aviso de abajo), o usa el **2525**, que casi nadie bloquea y Brevo acepta.

**2. Brevo restringe el acceso por IP.** Si activas esa opción, da de alta la IP del
servidor —y la tuya, si vas a probar desde tu PC—. Con la IP fuera de la lista, unas
credenciales correctas se rechazan igualmente.

**3. El dominio remitente no está verificado.** Enviar desde una dirección de un dominio
que Brevo no reconoce se rechaza. La verificación se hace en *Senders, Domains &
Dedicated IPs → Domains*, publicando en el DNS el TXT `brevo-code:…` que ellos indican.

> **Sobre SPF y DKIM.** Con el dominio verificado, la autenticación del correo la
> gestiona **Brevo** (el DMARC del dominio delega en ellos: `rua=mailto:rua@dmarc.brevo.com`),
> así que no hace falta publicar SPF ni DKIM propios para que el correo llegue a la
> bandeja de entrada — comprobado en este despliegue. Publicarlos sigue siendo lo
> recomendable si algún día envías desde varios servicios a la vez o quieres subir el
> DMARC a `p=quarantine`, pero **no** es un requisito para empezar.

Registros del dominio, para comprobar el estado:

```bash
nslookup -type=TXT chatmundoaventura.com 8.8.8.8          # debe salir el brevo-code:…
nslookup -type=TXT _dmarc.chatmundoaventura.com 8.8.8.8   # DMARC
```

Con todo puesto, **Admin → APIs → "Probar conexión"** en SMTP conecta, autentica y te
recuerda desde qué dirección se enviará.

Si el alta de una familia se quedó a medias por un fallo de envío, no hay que tocar la base
de datos: `familias_service.signup` **reactiva** una cuenta pendiente cuando se repite el
alta con el mismo correo.

> **Si tocas el cortafuegos del proveedor, revisa la regla implícita final.** En netcup, en
> cuanto defines una política de salida propia, la regla implícita pasa de `ACCEPT OUTGOING` a
> **`DROP OUTGOING`**: se cae *todo* el tráfico saliente y con él DeepL, el LLM, Replicate y
> ElevenLabs — mientras el ping y el DNS siguen funcionando, así que "parece" que la red está
> bien. Hay que añadir reglas `ACCEPT OUTGOING` explícitas (una por protocolo si el panel no
> admite `ANY`) **por debajo** de los `DROP` de los puertos de correo.

**3. Datos personales.** Con el despliegue permanente, los correos de los adultos y los
nombres de los niños viven en un servidor tuyo de forma indefinida, no en un portátil
durante una demo. Repasa [`PRIVACIDAD.md`](PRIVACIDAD.md): quién es el responsable del
tratamiento, cifrado del disco del VPS, y borrado de cuentas.

---

## 7. Problemas frecuentes

| Síntoma | Causa probable |
|---|---|
| Caddy no saca certificado | El registro A aún no propaga, o el puerto 80 está cerrado (el reto HTTP-01 lo usa) |
| El chat aparece de golpe, no token a token | Falta `flush_interval -1`, o `encode` no excluye `/api/ask/stream` |
| El micrófono no aparece | Sin HTTPS válido no hay `getUserMedia`. Comprueba el certificado |
| El login de admin falla de forma intermitente | El servicio arrancó con más de un worker: las sesiones viven en memoria (§`mundoaventura.service`) |
| El rate limit corta a todos a la vez | Falta `--proxy-headers`: todas las peticiones se ven como `127.0.0.1` |
| `502 Bad Gateway` | El backend está caído: `journalctl -u mundoaventura -n 100` |
| El chat responde "no lo sé" a todo | Falta el índice: `uv run python -m backend.ingest` (§3.8) |
| El chat responde peor que en tu PC | No migraste los ajustes (§3.7): el servidor corre con la línea base, sin reranker |
| `bad interpreter: /usr/bin/env bash^M` | El `.sh` se clonó con CRLF. `.gitattributes` lo previene; arréglalo con `dos2unix` |
| Te quedas fuera por SSH nada más instalar fail2ban | Te ha baneado por tus propios intentos fallidos. Caduca solo; evítalo con `ignoreip` (§3.0) |
| Caddy no arranca: `permission denied` en su log | `caddy validate` creó el fichero como root. `chown -R caddy:caddy /var/log/caddy` (§3.10) |
| Caddy devuelve 403 al servir la SPA | `caddy` no puede atravesar `/opt/mundoaventura` (750). Métele en el grupo de la app (§3.10) |
| Sin certificado pese a que el registro A es correcto | Hay un AAAA apuntando a una IPv6 que el servidor no tiene configurada (§3.10) |
| Todo deja de responder tras tocar el firewall del proveedor | La regla implícita de salida pasó a `DROP`. Ver §6.3 |
| El código de alta nunca llega (`timed out`) | El proveedor del VPS bloquea el SMTP saliente, o Brevo restringe por IP (§6.3) |
| El código llega pero cae en spam | El dominio remitente no está verificado en Brevo (§6.3) |
| El relé rechaza las credenciales (535) | En Brevo el usuario NO es tu correo: es el login `xxx@smtp-brevo.com` (§6.3) |
| El correo se rechaza por el remitente | El dominio de `SMTP_FROM` no está verificado en Brevo (§6.3) |
| Falla la generación de imagen con `500 Internal server error` | Suele ser Replicate, no tu servidor: comprueba `GET /v1/account` con tu token y su página de estado. Si el panel de Replicate no muestra ni siquiera predicciones **fallidas**, la petición murió antes de crearlas |
| `address already in use` al arrancar el backend | El socket y el servicio se pisan: o `--fd 3` **con** `mundoaventura.socket`, o `--host/--port` **sin** él (§3.9) |
| Siguen apareciendo 502 al desplegar | El `.socket` lleva `PartOf=`, o se reinició `mundoaventura.socket` en vez de solo el `.service` (§3.9) |
| El job `deploy` falla con `Permission denied (publickey)` | La clave no está en `authorized_keys` de **`mundoaventura`** (no de root), o `VPS_SSH_KEY` se pegó incompleta (faltan las líneas `BEGIN/END`) |
| El job `deploy` falla con `Host key verification failed` | `VPS_KNOWN_HOSTS` vacío o desfasado. Regenéralo con `ssh-keyscan` (§5.1) |
| El despliegue automático dice `uv: command not found` | El comando forzado no es una shell de login. El script ya añade `~/.local/bin` al PATH: comprueba que el servidor tiene la versión nueva de `desplegar.sh` |
| `desplegar.sh` falla en el paso 1 con `Permission denied` en `../copias` | Falta el directorio de copias. `install -d -o mundoaventura -g mundoaventura -m 750 /opt/copias` (§3.1) |
| `Permission denied` al ejecutar un `.sh` del repositorio | Se subió desde Windows sin bit de ejecución. Se arregla **en git**, no en el servidor: `git update-index --chmod=+x deploy/loquesea.sh` (un `chmod` en el servidor crea un cambio local que luego bloquea el `git pull`) |
| `git pull` aborta: *untracked working tree files would be overwritten* | Alguien dejó a mano en el servidor un fichero que después pasó a estar en git. Comprueba que el contenido coincide (`sha256sum`) y bórralo: git lo restaurará |
