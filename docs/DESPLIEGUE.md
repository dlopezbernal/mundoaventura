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

### 3.1 Usuario y directorio de la app

La app corre con un usuario **sin privilegios** cuyo *home* es el propio directorio de la
app. Eso permite endurecer el servicio con `ProtectHome=true` sin romper la caché de
modelos de `~/.cache`.

```bash
adduser --system --group --home /opt/mundoaventura --shell /bin/bash mundoaventura
chown -R mundoaventura:mundoaventura /opt/mundoaventura
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

> Si el repositorio es privado, usa una **deploy key** de solo lectura (`ssh-keygen` en el
> servidor → añadir la pública en Settings → Deploy keys del repo) en vez de meter
> credenciales de tu cuenta en el VPS.

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
| `EMAIL_VERIFICACION` | `true` + SMTP real | Ver §6 |
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

### 3.7 Construir el índice RAG

**Sin este paso el chat no funciona** (`rag_service` solo lee la colección, nunca la
construye). Los documentos de los personajes sí vienen en el repositorio; el índice de
ChromaDB no (está en `.gitignore`, se regenera).

```bash
sudo -u mundoaventura bash -lc 'cd /opt/mundoaventura && uv run python -m backend.ingest'
```

La primera ejecución descarga los modelos de embeddings (ONNX) a `~/.cache`. Tarda unos
minutos y necesita salida a internet.

### 3.8 Servicio systemd

```bash
cp /opt/mundoaventura/deploy/mundoaventura.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mundoaventura
systemctl status mundoaventura
curl -s http://127.0.0.1:8000/health
```

`/health` debe devolver `token_configurado: true`, `deepl_ok: true` y `elevenlabs_ok: true`.
Si alguno es `false`, revisa el `.env` (§3.4) antes de seguir.

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

### 3.9 DNS, cortafuegos y Caddy

Primero el **registro A** del dominio apuntando a la IP del VPS (desde el panel de tu
registrador). Compruébalo con `dig +short chatmundoaventura.com` — hasta que no resuelva, Caddy
no podrá sacar el certificado.

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

```bash
cp /opt/mundoaventura/deploy/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
journalctl -u caddy -n 40 --no-pager     # debe verse la emisión del certificado
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

```bash
# Logs en vivo
journalctl -u mundoaventura -f
journalctl -u caddy -f

# Actualizar a la última versión de main (backup + pull + build + reinicio)
sudo -u mundoaventura bash -lc 'cd /opt/mundoaventura && ./deploy/desplegar.sh'
# …y además reconstruir el índice RAG (si cambiaron documentos, EMBEDDING_BACKEND o CHUNKING)
sudo -u mundoaventura bash -lc 'cd /opt/mundoaventura && ./deploy/desplegar.sh --reindexar'
```

**Qué hay que respaldar.** Todo lo importante que NO está en git:

| Ruta | Contiene | ¿Se regenera? |
|---|---|---|
| `.env` | Claves de los proveedores | No — **respáldalo** |
| `backend/config_db.sqlite3` | Ajustes, catálogos, familias, PIN/2FA, auditoría | No — **respáldalo** |
| `backend/documentos/` | Documentos del RAG subidos desde la UI | Los del repo sí; los subidos **no** |
| `backend/chroma_db/` | Índice vectorial | Sí (`backend.ingest`) |
| `backend/.cache/` | Audio TTS ya sintetizado, modelos ONNX | Sí |
| `backend/avatares/` | Avatares del carrusel | Sí |

Una copia diaria basta con esto (por ejemplo desde el `cron` del usuario):

```bash
tar czf /opt/copias/mundoaventura-$(date +\%F).tgz \
  -C /opt/mundoaventura .env backend/config_db.sqlite3 backend/documentos
```

`deploy/desplegar.sh` ya hace una copia del `.env` y de la BBDD antes de cada actualización,
en `/opt/copias/`.

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
Ponlo en `true` y configura SMTP real (Brevo, Resend, Mailgun…) en el `.env`.

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
| El chat responde "no lo sé" a todo | Falta el índice: `uv run python -m backend.ingest` (§3.7) |
| `bad interpreter: /usr/bin/env bash^M` | El `.sh` se clonó con CRLF. `.gitattributes` lo previene; arréglalo con `dos2unix` |
