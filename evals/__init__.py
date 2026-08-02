"""
evals/ — Banco de pruebas y evaluación del sistema RAG (Hito 3)
==============================================================

El instrumento que convierte "creo que ha mejorado" en "mejoró un 18 %, aquí está
la tabla". No cambia NINGÚN modelo, prompt ni proveedor: solo mide.

Piezas:
  - esquema.py       → forma y validación de los sets de preguntas (YAML).
  - set_dorado.yaml  → preguntas de calidad (20 por personaje, español infantil real).
  - set_seguridad.yaml → set adversarial (violencia/muerte con tacto, salir del papel…).
  - metricas.py      → métricas deterministas (legibilidad, idioma, recall@3…).
  - runner.py        → ejecuta los sets y produce CSV + HTML (modos completo /
                       retrieval-congelado).
  - fixtures/        → retrieval congelado (chunks recuperados, para aislar el generador).
  - resultados/      → CSV/HTML de cada corrida; BASELINE.csv es la línea base inmutable.

Piezas del estudio de LLMs (Hito 6):
  - candidatos.yaml  → los 5 candidatos + el juez, con su config exacta.
  - comparar.py      → agrega las corridas y decide (puertas §8 → pesos §7).
  - juez.py          → juez LLM de fidelidad al contexto + su validación.
  - test_ciego.py    → pares anonimizados entre finalistas + agregación de votos.
  - resultados_h6.yaml → inputs de juicio (seguridad, juez, test ciego) a mano.

Uso:
  uv run python -m evals.runner --modo completo
  uv run python -m evals.runner --modo retrieval-congelado
  uv run python -m evals.comparar
"""

import sys


def forzar_utf8_consola() -> None:
    """Hace que los `print` con acentos/glifos (§, ↳, →, ñ) no revienten en la consola
    de Windows (cp1252): reconfigura stdout a UTF-8 degradando a '?' si no se puede
    representar, en vez de lanzar UnicodeEncodeError. La llaman los `main()` de las CLIs.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
