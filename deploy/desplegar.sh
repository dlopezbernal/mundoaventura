#!/usr/bin/env bash
# =====================================================================
#  desplegar.sh — Actualiza la app en el VPS a la última versión
# ---------------------------------------------------------------------
#  Se ejecuta EN EL SERVIDOR, como el usuario dueño de la app:
#      cd /opt/mundoaventura && ./deploy/desplegar.sh
#      ./deploy/desplegar.sh --reindexar    # además, reconstruye el índice RAG
#
#  También lo invoca GitHub Actions por SSH (docs/DESPLIEGUE.md §5.1). Por eso
#  no asume una sesión interactiva: fija el PATH que necesita y decide solo si
#  el despliegue ha ido bien, sin que nadie lea la salida.
#
#  Qué NO toca (y por eso una actualización no pierde datos): .env,
#  config_db.sqlite3, backend/documentos/, backend/chroma_db/, backend/avatares/
#  y backend/.cache/ están todos en .gitignore.
#
#  Si la comprobación final falla, VUELVE ATRÁS solo (al commit anterior) y sale
#  con error. La instalación desde cero está en docs/DESPLIEGUE.md; esto es solo
#  el "git pull + reconstruir + reiniciar" del día a día.
# =====================================================================
set -euo pipefail

# Invocado como comando forzado de SSH, esto NO es una shell de login: `uv` vive
# en ~/.local/bin y no estaría en el PATH. Se añade explícitamente.
export PATH="$HOME/.local/bin:$PATH"

APP_DIR="${APP_DIR:-/opt/mundoaventura}"
SERVICIO="${SERVICIO:-mundoaventura}"
RAMA="${RAMA:-main}"
SALUD_URL="${SALUD_URL:-http://127.0.0.1:8000/health}"
REINDEXAR=0

for arg in "$@"; do
	case "$arg" in
		--reindexar) REINDEXAR=1 ;;
		*) echo "Uso: $0 [--reindexar]" >&2; exit 2 ;;
	esac
done

cd "$APP_DIR"

# ---------------------------------------------------------------------
#  Funciones auxiliares
# ---------------------------------------------------------------------

# Espera a que el backend responda y sea ÉL quien sirve. Devuelve 0 / 1.
#
# La puerta es `status: ok`, y NO las banderas de los proveedores: un
# `deepl_ok:false` casi siempre significa que DeepL está caído, no que este
# despliegue esté roto, y volver atrás no lo arreglaría. Los proveedores se
# avisan, no se usan para decidir.
esperar_salud() {
	local intentos="${1:-20}" i
	for ((i = 1; i <= intentos; i++)); do
		if curl -fsS --max-time 5 "$SALUD_URL" -o /tmp/health.json 2>/dev/null &&
			grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' /tmp/health.json; then
			return 0
		fi
		sleep 2
	done
	return 1
}

# Reconstruye el árbol de trabajo tal y como está ahora mismo en disco.
construir() {
	uv sync --frozen
	(cd "$APP_DIR/frontend-react" && npm ci && npm run build)
}

# Vuelve al commit indicado, reconstruye y reinicia. Es el plan B cuando la
# versión nueva no levanta.
#
# Solo revierte el CÓDIGO: la BBDD se deja como está a propósito. Restaurarla
# borraría los ajustes que el adulto haya cambiado desde el menú mientras tanto,
# y este proyecto no tiene migraciones de esquema que deshacer. La copia previa
# sigue en /opt/copias por si hiciera falta a mano.
volver_atras() {
	local commit="$1"
	echo "==> ⏪ VUELTA ATRÁS a $commit"
	git reset --hard "$commit"
	construir
	sudo systemctl restart "$SERVICIO"
	if esperar_salud 20; then
		echo "==> Vuelta atrás COMPLETADA: la versión anterior responde en $SALUD_URL"
	else
		echo "==> ⚠️  La vuelta atrás TAMPOCO responde. Requiere intervención manual:" >&2
		echo "    journalctl -u $SERVICIO -n 80 --no-pager" >&2
	fi
}

# ---------------------------------------------------------------------
#  Despliegue
# ---------------------------------------------------------------------

echo "==> 1/7  Copia de seguridad previa"
# Una sola implementación de la copia, compartida con la nocturna: así no hay
# dos ideas distintas de "qué hay que respaldar" que se desincronicen.
# Se etiqueta como "predespliegue" para distinguirla de las diarias.
#
# Se invoca con `bash …` en lugar de ejecutarlo directamente, a propósito. Este
# paso va ANTES del `git pull` (la copia tiene que preceder a cualquier cambio),
# así que todo lo que falle aquí deja el despliegue SIN PODER REPARARSE SOLO:
# muere antes de traerse la corrección y hay que entrar por SSH. Pasó de verdad,
# con este fichero subido desde Windows sin bit de ejecución. Llamarlo por el
# intérprete elimina esa dependencia del camino crítico. (systemd sí necesita el
# bit para la copia nocturna, pero allí el peor caso es saltarse una copia, no
# quedarse sin poder desplegar.)
bash "$APP_DIR/deploy/respaldar.sh" predespliegue

echo "==> 2/7  Anotar la versión actual (por si hay que volver)"
COMMIT_ANTERIOR="$(git rev-parse HEAD)"
echo "    versión actual: $COMMIT_ANTERIOR"

echo "==> 3/7  Traer los cambios de la rama $RAMA"
git fetch --prune origin
git checkout "$RAMA"
git pull --ff-only origin "$RAMA"
COMMIT_NUEVO="$(git rev-parse HEAD)"

if [ "$COMMIT_NUEVO" = "$COMMIT_ANTERIOR" ] && [ "$REINDEXAR" -eq 0 ]; then
	echo "==> Ya estaba en la última versión ($COMMIT_NUEVO). Nada que hacer."
	esperar_salud 5 && echo "    (el servicio responde)" || echo "    ⚠️  ojo: el servicio NO responde" >&2
	exit 0
fi
echo "    versión nueva:  $COMMIT_NUEVO"

echo "==> 4/7  Dependencias y construcción de la SPA"
# --frozen = falla si pyproject y uv.lock se han desincronizado, en vez de
# resolver por su cuenta. `npm ci` (no `install`) = exactamente el lockfile.
# Si la construcción falla, el servicio VIEJO sigue corriendo intacto: aún no
# hemos reiniciado nada. Basta con dejar el árbol como estaba.
if ! construir; then
	echo "==> ❌ Falló la construcción. El servicio en marcha NO se ha tocado." >&2
	git reset --hard "$COMMIT_ANTERIOR"
	construir || true
	exit 1
fi

if [ "$REINDEXAR" -eq 1 ]; then
	echo "==> 5/7  Reindexar el RAG (reconstrucción completa de ChromaDB)"
	uv run python -m backend.ingest
else
	echo "==> 5/7  Reindexado OMITIDO (pásale --reindexar si cambiaron documentos,"
	echo "         EMBEDDING_BACKEND o CHUNKING)"
fi

echo "==> 6/7  Reiniciar el servicio"
# El usuario de la app no tiene sudo general: /etc/sudoers.d/mundoaventura le
# concede EXACTAMENTE `systemctl restart|status mundoaventura` (ver DESPLIEGUE.md §3.9).
# Con activación por socket (§3.9) el corte no se ve desde fuera: systemd mantiene
# el puerto abierto y el kernel encola las peticiones mientras uvicorn arranca.
sudo systemctl restart "$SERVICIO"

echo "==> 7/7  Comprobación de humo"
if ! esperar_salud 20; then
	echo "==> ❌ El backend no responde en $SALUD_URL tras el reinicio." >&2
	volver_atras "$COMMIT_ANTERIOR"
	exit 1
fi

echo "OK — /health responde:"
cat /tmp/health.json
echo
# Aviso, NO motivo de vuelta atrás: casi siempre es una incidencia del proveedor.
for bandera in token_configurado deepl_ok elevenlabs_ok; do
	grep -q "\"$bandera\"[[:space:]]*:[[:space:]]*true" /tmp/health.json ||
		echo "⚠️  $bandera es false — revisa el proveedor o el .env (no es culpa del despliegue)."
done
echo "==> ✅ Desplegado $COMMIT_NUEVO"
