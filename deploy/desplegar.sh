#!/usr/bin/env bash
# =====================================================================
#  desplegar.sh — Actualiza la app en el VPS a la última versión
# ---------------------------------------------------------------------
#  Se ejecuta EN EL SERVIDOR, como el usuario dueño de la app:
#      cd /opt/mundoaventura && ./deploy/desplegar.sh
#      ./deploy/desplegar.sh --reindexar    # además, reconstruye el índice RAG
#
#  Qué NO toca (y por eso una actualización no pierde datos): .env,
#  config_db.sqlite3, backend/documentos/, backend/chroma_db/ y
#  backend/.cache/ están todos en .gitignore.
#
#  La instalación desde cero está en docs/DESPLIEGUE.md; esto es solo el
#  "git pull + reconstruir + reiniciar" del día a día.
# =====================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/mundoaventura}"
SERVICIO="${SERVICIO:-mundoaventura}"
RAMA="${RAMA:-main}"
REINDEXAR=0

for arg in "$@"; do
	case "$arg" in
		--reindexar) REINDEXAR=1 ;;
		*) echo "Uso: $0 [--reindexar]" >&2; exit 2 ;;
	esac
done

cd "$APP_DIR"

echo "==> 1/6  Copia de seguridad de los datos (BBDD + .env)"
# Antes de nada, por si una migración futura tocara el esquema. Se guardan
# fuera del árbol de git para que un `git clean` no se las lleve por delante.
COPIAS="${COPIAS:-$APP_DIR/../copias}"
mkdir -p "$COPIAS"
SELLO="$(date +%Y%m%d-%H%M%S)"
[ -f backend/config_db.sqlite3 ] && cp backend/config_db.sqlite3 "$COPIAS/config_db-$SELLO.sqlite3"
[ -f .env ] && cp .env "$COPIAS/env-$SELLO.bak"

echo "==> 2/6  Traer los cambios de la rama $RAMA"
git fetch --prune origin
git checkout "$RAMA"
git pull --ff-only origin "$RAMA"

echo "==> 3/6  Dependencias del backend (uv, exactamente lo del uv.lock)"
# --frozen = falla si pyproject y uv.lock se han desincronizado, en vez de
# resolver por su cuenta. En un servidor queremos el pin exacto o nada.
uv sync --frozen

echo "==> 4/6  Construir la SPA"
cd frontend-react
# `npm ci` (no `install`) = instala exactamente el package-lock.json.
npm ci
npm run build
cd "$APP_DIR"

if [ "$REINDEXAR" -eq 1 ]; then
	echo "==> 5/6  Reindexar el RAG (reconstrucción completa de ChromaDB)"
	uv run python -m backend.ingest
else
	echo "==> 5/6  Reindexado OMITIDO (pásale --reindexar si cambiaron documentos,"
	echo "         EMBEDDING_BACKEND o CHUNKING)"
fi

echo "==> 6/6  Reiniciar el servicio y comprobar salud"
# El usuario de la app no tiene sudo general: /etc/sudoers.d/mundoaventura le
# concede EXACTAMENTE `systemctl restart|status mundoaventura` (ver DESPLIEGUE.md §3.8).
sudo systemctl restart "$SERVICIO"

# El arranque toca red (comprueba DeepL/ElevenLabs), así que damos margen y
# reintentamos en vez de asumir que responde al instante.
for intento in $(seq 1 15); do
	if curl -fsS --max-time 5 http://127.0.0.1:8000/health > /tmp/health.json; then
		echo "OK — /health responde:"
		cat /tmp/health.json
		echo
		echo "Revisa que token_configurado / deepl_ok / elevenlabs_ok sean true."
		exit 0
	fi
	sleep 2
done

echo "ERROR: el backend no responde en /health tras el reinicio." >&2
echo "Mira los logs con:  journalctl -u $SERVICIO -n 80 --no-pager" >&2
exit 1
