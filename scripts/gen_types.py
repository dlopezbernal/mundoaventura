"""scripts/gen_types.py — Genera los tipos TS del frontend desde el OpenAPI del backend.

Fuente de verdad: los `response_model`/schemas Pydantic del backend. Este script
exporta el esquema OpenAPI de la app y lo convierte en TypeScript con
`openapi-typescript`, dejando el resultado en `frontend-react/src/api/schema.d.ts`.
`frontend-react/src/api/types.ts` re-exporta esos tipos con nombres estables, así los
componentes del frontend no cambian sus imports.

Uso:
    uv run python -m scripts.gen_types

Requisitos: Node/npx disponibles. `openapi-typescript` se ejecuta con `npx` (no es una
dependencia de package.json: es una herramienta de desarrollo, y su peer de TypeScript
va por detrás de la versión del proyecto). El fichero generado SÍ se versiona.
"""

import json
import pathlib
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "frontend-react" / "src" / "api" / "schema.d.ts"


def main() -> None:
    # Importar la app aquí (no arriba) para que un fallo de import se vea claro.
    from backend.main import app

    esquema = app.openapi()
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(esquema, tmp, ensure_ascii=False)
        ruta_json = tmp.name

    print(f"OpenAPI exportado ({len(esquema.get('paths', {}))} rutas). Generando {SALIDA.name}…")
    # npx openapi-typescript <json> -o <salida>. shell=True en Windows para resolver npx.cmd.
    cmd = f'npx -y openapi-typescript "{ruta_json}" -o "{SALIDA}"'
    res = subprocess.run(cmd, shell=True, cwd=RAIZ)
    pathlib.Path(ruta_json).unlink(missing_ok=True)
    if res.returncode != 0:
        sys.exit(f"openapi-typescript falló (código {res.returncode}).")
    print(f"✅ Tipos generados en {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
