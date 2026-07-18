# 🎭 Playwright MCP en Claude Code (Windows, sin permisos de admin)

Guía para dejar el MCP de Playwright funcionando en este proyecto en un PC Windows
donde no tienes permisos de administrador (típico en portátiles corporativos).

## El problema en una frase

El MCP de Playwright, por defecto, busca un Chrome instalado en el sistema. Si no está
instalado, falla — y `npx playwright install chrome` para instalar el Chrome "de verdad"
puede pedir permisos que no tienes.

**La solución:** Playwright puede descargar su propio **Chromium** en tu carpeta de
usuario (`%LOCALAPPDATA%\ms-playwright`, sin admin. Solo hay que decirle al MCP que use
ese, con `--browser chromium`.

> `chrome` ≠ `chromium`. El primero es el navegador de Google instalado en el sistema
> (puede pedir permisos de admin). El segundo es el build que Playwright se descarga
> solo, en tu carpeta de usuario. Toda la diferencia está ahí.

## Requisitos previos

```powershell
node --version    # v18+ recomendado (probado con v24)
npx --version
```

## Paso 1 — Descargar el Chromium de Playwright

Solo hace falta **una vez por máquina** (no por proyecto): se guarda en
`%LOCALAPPDATA%\ms-playwright` y lo comparten todos los proyectos.

```powershell
npx playwright install chromium
```

Comprobar que está:

```powershell
Get-ChildItem $env:LOCALAPPDATA\ms-playwright
# debe aparecer algo como: chromium-1228\  chromium_headless_shell-1228\  ffmpeg-1011\
```

Si ya existe, salta al paso 2. A diferencia de Linux, en Windows **no existe** el paso
de `install-deps` (librerías del sistema tipo `libnss3`): Chromium trae lo que necesita.

## Paso 2 — Copia de seguridad de `~/.claude.json`

No te lo saltes. Ese fichero guarda mucho estado de Claude Code (no solo los MCP); un
error al editarlo se lo puede cargar entero.

```powershell
Copy-Item $env:USERPROFILE\.claude.json "$env:USERPROFILE\.claude.json.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
```

## Paso 3 — Configurar el MCP

Desde la **raíz del proyecto** (`capston/`):

```powershell
claude mcp add playwright -- npx @playwright/mcp@latest --browser chromium
```

El `--` separa los argumentos de `claude mcp` de los del comando; todo lo que va detrás
se le pasa tal cual a `npx`.

Esto crea una entrada de **scope local** (privada, solo para este proyecto) en
`~/.claude.json`. No se hereda entre proyectos: en un proyecto nuevo hay que repetir
este paso (el paso 1 no, el Chromium ya está descargado para la máquina).

## Paso 4 — Verificar

```powershell
claude mcp list
claude mcp get playwright
```

Debe salir `✔ Connected`. Si el servidor ya estaba corriendo en la sesión, un cambio de
argumentos en `~/.claude.json` **no se recoge en caliente** — cierra y reabre la sesión
de Claude Code tras editar la config a mano (con `claude mcp add` desde una sesión nueva
no hace falta).

En la sesión, pide navegar a una URL local del proyecto (con el frontend arrancado,
`npm run dev` en `frontend-react/`) para comprobar que abre el navegador y devuelve
contenido.

## Plan B: el CLI de Playwright (sin MCP)

Si el MCP no arranca y necesitas una captura ya, el CLI usa el mismo Chromium:

```powershell
npx playwright screenshot --browser chromium --wait-for-timeout 3000 --viewport-size "1440,900" http://localhost:5173/ docs/img/captura.png
```

Sirve para capturas puntuales; para navegar e interactuar hace falta el MCP.

## Avisos y trampas conocidas

| Aviso | Detalle |
|---|---|
| Ámbito local | La config vive en `~/.claude.json` bajo la ruta de este proyecto. En un proyecto nuevo hay que repetir el paso 3. |
| `/mcp` puede pisarlo | Si en el futuro tocas los MCP con `/mcp` o `claude mcp`, puedes perder el `--browser chromium`. Si vuelve el error de Chrome, mira ahí primero. |
| Reinicio | Un cambio manual en `~/.claude.json` requiere sesión nueva para aplicarse. |
| Capturas y git | Las imágenes en `docs/img/` quedan sin seguimiento salvo que las añadas tú; decide si las commiteas o las metes en `.gitignore`. |
| Entorno apuntado | Si apuntas a `localhost:5173` estás mirando tu sesión de dev levantada (`npm run dev`), con cambios sin commitear — no es el build de producción. |

## Restaurar si algo va mal

```powershell
Copy-Item "$env:USERPROFILE\.claude.json.bak-AAAAMMDD-HHMMSS" $env:USERPROFILE\.claude.json
```

Y reinicia la sesión.

## Resumen ejecutable

```powershell
# 1. Navegador (una vez por máquina)
npx playwright install chromium

# 2. Backup
Copy-Item $env:USERPROFILE\.claude.json "$env:USERPROFILE\.claude.json.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"

# 3. MCP (una vez por proyecto), desde la raíz del proyecto
claude mcp add playwright -- npx @playwright/mcp@latest --browser chromium

# 4. Reiniciar la sesión de Claude Code (si venía de config manual)

# 5. Probar pidiendo navegar a http://localhost:5173/ con el frontend arrancado
```
