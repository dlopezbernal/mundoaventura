#!/usr/bin/env bash
# =====================================================================
#  respaldar.sh — Copia de seguridad de TODO lo que no está en git
# ---------------------------------------------------------------------
#  Se ejecuta EN EL SERVIDOR, como el usuario dueño de la app:
#      ./deploy/respaldar.sh [etiqueta]
#
#  Se lanza desde dos sitios:
#    · `desplegar.sh`, antes de cada actualización  → etiqueta "predespliegue"
#    · el temporizador de systemd, cada noche       → etiqueta "nocturno"
#      (mundoaventura-backup.timer, ver docs/DESPLIEGUE.md §5.2)
#
#  Produce UN fichero por copia:
#      /opt/copias/mundoaventura-AAAAMMDD-HHMMSS-<etiqueta>.tgz
#
#  QUÉ LLEVA DENTRO (lo irreemplazable, ~7 MB):
#    .env                       claves de los proveedores y SMTP
#    frontend-react/.env        configuración de compilación de la SPA
#    backend/config_db.sqlite3  ajustes, catálogos, familias, 2FA, auditoría
#    backend/documentos/        base de conocimiento del RAG (lo subido desde
#                               la UI NO está en git)
#    backend/avatares/          regenerables, pero cada uno cuesta dos llamadas
#                               a Replicate
#
#  QUÉ NO, y por qué:
#    backend/chroma_db/   derivado de documentos + EMBEDDING_BACKEND (ambos aquí
#                         dentro). Se rehace con `backend.ingest` en ~1 min, y
#                         restaurar un índice viejo sobre ajustes nuevos daría
#                         malas respuestas EN SILENCIO: peor que reconstruirlo.
#    backend/.cache/      caché de audio TTS: se rehace sola al usarse.
#    .venv, node_modules  se reconstruyen desde los lockfiles.
#    .ssh/                claves de acceso al servidor. Fuera a propósito: este
#                         fichero está pensado para MOVERSE a otra máquina, y
#                         recrear esas claves son dos comandos (§3.3 y §5.1).
#
#  El límite es deliberado: el tarball restaura los DATOS; el sistema (systemd,
#  Caddy, ufw, fail2ban) lo reconstruye docs/DESPLIEGUE.md, que sí está en git.
# =====================================================================
set -euo pipefail

# Todo lo que se crea aquí lleva secretos (el .env va dentro): que nazca privado
# en vez de arreglarlo con un chmod a posteriori.
umask 077

APP_DIR="${APP_DIR:-/opt/mundoaventura}"
DESTINO="${DESTINO:-$APP_DIR/../copias}"
RETENCION_DIAS="${RETENCION_DIAS:-15}"
ETIQUETA="${1:-manual}"

cd "$APP_DIR"

if [ ! -d "$DESTINO" ] || [ ! -w "$DESTINO" ]; then
	echo "ERROR: no se puede escribir en $DESTINO (su padre suele ser de root)." >&2
	echo "Créalo una vez, como root:" >&2
	echo "  install -d -o mundoaventura -g mundoaventura -m 750 $(cd "$APP_DIR/.." && pwd)/copias" >&2
	exit 1
fi

SELLO="$(date +%Y%m%d-%H%M%S)"
ARCHIVO="$DESTINO/mundoaventura-$SELLO-$ETIQUETA.tgz"
ESCENARIO="$(mktemp -d)"
trap 'rm -rf "$ESCENARIO"' EXIT

# --- 1. Instantánea CONSISTENTE de la BBDD -----------------------------------
# Un `cp` de un SQLite vivo puede capturarlo a medias si justo hay una escritura
# en vuelo. La API de copia en caliente (`Connection.backup`) resuelve eso sin
# parar el servicio. Se usa el python3 DEL SISTEMA a propósito: así la copia
# sigue funcionando aunque el .venv esté a medio construir o roto.
mkdir -p "$ESCENARIO/backend"
if [ -f backend/config_db.sqlite3 ]; then
	python3 - "$APP_DIR/backend/config_db.sqlite3" "$ESCENARIO/backend/config_db.sqlite3" <<'PY'
import sqlite3
import sys

origen, destino = sys.argv[1], sys.argv[2]
con_origen = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
con_destino = sqlite3.connect(destino)
with con_destino:
    con_origen.backup(con_destino)
con_destino.close()
con_origen.close()
PY
fi

# --- 2. Inventario legible dentro del propio archivo -------------------------
# Para que dentro de seis meses el .tgz se explique solo, sin buscar la doc.
{
	echo "MundoAventura — copia de seguridad"
	echo "fecha:     $(date --iso-8601=seconds)"
	echo "servidor:  $(hostname)"
	echo "etiqueta:  $ETIQUETA"
	echo "commit:    $(git rev-parse HEAD 2>/dev/null || echo 'desconocido')"
	echo
	echo "RESTAURAR (sobre una instalación ya montada según docs/DESPLIEGUE.md §3):"
	echo "  systemctl stop mundoaventura"
	echo "  tar xzf $(basename "$ARCHIVO") -C /opt/mundoaventura"
	echo "  cd /opt/mundoaventura && uv run python -m backend.ingest   # rehace el índice"
	echo "  systemctl start mundoaventura"
	echo
	echo "NO incluido (se regenera): backend/chroma_db, backend/.cache, .venv,"
	echo "node_modules, dist, .ssh."
} > "$ESCENARIO/INVENTARIO.txt"

# --- 3. Empaquetar -----------------------------------------------------------
# Rutas relativas a la raíz de la app, para que restaurar sea un `tar x -C`
# directo. Solo se añade lo que existe: una instalación recién hecha aún no
# tiene avatares, y tar aborta si le nombras algo que no está.
RUTAS=()
for ruta in .env frontend-react/.env backend/documentos backend/avatares; do
	[ -e "$APP_DIR/$ruta" ] && RUTAS+=("$ruta")
done

tar czf "$ARCHIVO" \
	-C "$ESCENARIO" INVENTARIO.txt $([ -f "$ESCENARIO/backend/config_db.sqlite3" ] && echo backend/config_db.sqlite3) \
	-C "$APP_DIR" ${RUTAS[@]+"${RUTAS[@]}"}

# --- 4. Verificar que el archivo se puede leer -------------------------------
# Una copia que no se ha abierto nunca es una hipótesis. Esto no sustituye a una
# restauración de verdad, pero sí detecta el archivo truncado o corrupto.
if ! tar tzf "$ARCHIVO" > /dev/null 2>&1; then
	echo "ERROR: el archivo generado no se puede leer. Se borra: $ARCHIVO" >&2
	rm -f "$ARCHIVO"
	exit 1
fi

echo "Copia creada: $ARCHIVO ($(du -h "$ARCHIVO" | cut -f1), $(tar tzf "$ARCHIVO" | wc -l) entradas)"

# --- 5. Retención ------------------------------------------------------------
# Se borran las copias con más de RETENCION_DIAS días. El patrón del nombre
# acota el borrado a NUESTROS ficheros: si alguien deja algo suyo en la carpeta,
# no se lo llevamos por delante.
BORRADAS="$(find "$DESTINO" -maxdepth 1 -name 'mundoaventura-*.tgz' -type f -mtime "+$RETENCION_DIAS" -print -delete | wc -l)"
[ "$BORRADAS" -gt 0 ] && echo "Retención: borradas $BORRADAS copias de más de $RETENCION_DIAS días."

echo "En $DESTINO hay $(find "$DESTINO" -maxdepth 1 -name 'mundoaventura-*.tgz' | wc -l) copias ($(du -sh "$DESTINO" | cut -f1))."
