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

Uso:
  uv run python -m evals.runner --modo completo
  uv run python -m evals.runner --modo retrieval-congelado
"""
