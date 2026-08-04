# H1 — Andamiaje de calidad

- **Rama:** `feat/h1-andamiaje`
- **Semana:** S1, días 1–3
- **Depende de:** nada
- **Prioridad que sirve:** #1 (buenas prácticas). Es entregable en sí mismo, no
  preparación para otra cosa.

## Objetivo

Poner la infraestructura de calidad que hoy no existe: reproducibilidad, lint,
tests, CI y logging. Es lo primero que ve quien revisa el repo.

## Alcance

### SÍ
- Fijado de dependencias y reproducibilidad.
- `ruff` (lint + format) y `pre-commit`.
- `pytest` con cobertura y los primeros tests de funciones puras.
- CI en GitHub Actions.
- Migración de `print()` a `logging`.

### NO
- Nada de lógica de IA. Ni un modelo, ni un proveedor, ni un prompt.
- Nada de arreglar el `async` ni los timeouts (eso es H2).
- No refactorizar servicios ni cambiar firmas.

## Tareas

### 1. Reproducibilidad
- Fijar versiones en `requirements-backend.txt`. Hoy sólo `elevenlabs` tiene
  restricción; `chromadb` y `langchain-text-splitters` rompen API entre menores.
  Opción preferida: migrar a `uv` con `pyproject.toml` + `uv.lock`.
- Añadir `.python-version`.
- Crear `requirements-dev.txt` (o grupo `dev` en `pyproject.toml`): `pytest`,
  `pytest-cov`, `ruff`, `pre-commit`, `httpx` (para `TestClient`).
- Script único de arranque (`Makefile` o `scripts/dev.ps1`, que estamos en
  Windows) que levante backend y frontend.

### 2. Lint y formato
- Configurar `ruff` en `pyproject.toml`. Reglas mínimas: `E`, `F`, `I`
  (imports), `UP` (pyupgrade), `B` (bugbear), `SIM`.
- `ruff` detectará los `datetime.utcnow()` (10 usos) — **anotarlos pero NO
  arreglarlos aquí**, van en H2. Se marcan con `# noqa` temporal o se deja la
  regla en warning.
- `pre-commit` con `ruff check --fix`, `ruff format` y `oxlint` en el frontend.

### 3. Tests iniciales
Empezar por las funciones puras, que ya están bien aisladas en el repo:

| Función | Fichero | Qué probar |
|---|---|---|
| `_aplicar_cambios_env` | `services/secrets_service.py` | preserva comentarios, sustituye existentes, añade nuevas, respeta salto final |
| `_trocear_para_traducir` | `services/translation_service.py` | respeta párrafos, parte los párrafos gigantes, no pierde texto |
| `_clasificar_umbral` | `services/rag_service.py` | los tres tramos y los bordes exactos |
| `_nombre_con_idioma` | `services/documentos_service.py` | traducido vs no traducido, extensiones |
| `_estimar_tokens` | `services/generation_service.py` | palabras y puntuación |
| `_enmascarar` | `services/secrets_service.py` | vacío, ≤4 caracteres, normal |

Configurar `pytest-cov` con umbral mínimo. Objetivo realista al final de H1:
**≥ 80 % en los módulos con funciones puras**, sin exigir nada global todavía.

### 4. Logging
Hoy hay **36 `print()` y cero `logger`** en `backend/`.

- Configurar `logging` en `main.py`: formato con timestamp, nivel por variable
  de entorno, `logging.getLogger(__name__)` por módulo.
- Sustituir los 36 `print()` por el nivel adecuado: `info` en arranque,
  `warning` en degradaciones (TTS caído, colección vacía), `debug` en trazas.
- `debug_log.py` deja de imprimir por su cuenta y pasa a ser un **formateador
  que emite por `logger.debug`**. Mantiene su API pública (`trazar_prompt`) para
  no tocar los llamadores.
- Los `except Exception` con `pass` mudo (hay 5) pasan a `logger.warning` con el
  contexto. **Sólo eso**; no se cambia el flujo de control aquí.

### 5. CI
`.github/workflows/ci.yml` con dos jobs:
- **backend:** instalar, `ruff check`, `ruff format --check`, `pytest --cov`.
- **frontend:** `npm ci`, `npm run lint`, `npm run build`.

Que corra en push y en pull request contra `dev`.

## Criterios de aceptación (puerta)

- [ ] `pip install -r requirements-backend.txt` (o `uv sync`) instala versiones
      deterministas en una máquina limpia.
- [ ] `ruff check .` y `ruff format --check .` pasan sin errores.
- [ ] `pytest` en verde, cobertura ≥ 80 % en los módulos listados en §3.
- [ ] `grep -rn "print(" backend/ --include=*.py` devuelve **0**.
- [ ] `grep -rn "except Exception" -A1 backend/ | grep -c "pass"` devuelve **0**.
- [ ] CI verde en GitHub Actions, badge en el `README`.
- [ ] `pre-commit run --all-files` pasa.

## Evidencia a entregar para el OK

1. Enlace al run de CI en verde.
2. Salida de `pytest --cov` con el resumen de cobertura.
3. Salida de los dos `grep` de arriba.
4. Informe de hito en el formato de `docs/PLAN.md` §4.

## Instrucción de arranque para Claude Code

> Lee `docs/PLAN.md` y `docs/plan/H1-andamiaje.md`. Trabaja **sólo** en el
> alcance de H1. No toques lógica de IA, no arregles el `async` de los endpoints
> ni los timeouts (eso es H2). Antes de escribir código, dame el plan de
> ejecución paso a paso y espera mi confirmación. Cuando termines, dame el
> INFORME DE HITO.
