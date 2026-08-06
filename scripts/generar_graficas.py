"""Genera las gráficas de la memoria en SVG, sin dependencias.

Dos figuras, a partir de datos ya medidos y archivados en el repositorio:

  1. `docs/img/gr-01-progresion-retrieval.svg`
     Arco de mejora del retrieval (recall@3 de chunk y acierto de ruteo) a lo
     largo de las cuatro configuraciones de H4. Fuente: la tabla comparativa del
     ADR-006, que es donde vive la corrida de solo-retrieval.

  2. `docs/img/gr-02-latencia-percibida.svg`
     Latencia percibida del chat antes y después del streaming (H8).
     Fuente: `docs/mediciones/H8-latencia-streaming.md` (n=15).

Por qué SVG y no PNG: la memoria se entrega en PDF y una gráfica vectorial no se
pixela al ampliar ni al imprimir. Y por qué a mano y no con matplotlib: sería la
única dependencia del proyecto que existe solo para dibujar dos figuras.

Uso:
    uv run python scripts/generar_graficas.py
"""

from __future__ import annotations

import pathlib

DESTINO = pathlib.Path("docs/img")

# --- Paleta -----------------------------------------------------------------
# Dos series categóricas de la paleta de referencia, validadas para daltonismo:
# el peor par adyacente da ΔE 24,7 en protanopía y 33,6 en visión normal (el
# umbral es 8 y 15). Superficie clara a propósito: esto se imprime.
AZUL = "#2a78d6"
NARANJA = "#eb6834"
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_SUAVE = "#52514e"
REJILLA = "#e3e2df"
FUENTE = "Segoe UI, Helvetica, Arial, sans-serif"


def _barra_arriba_redondeada(x: float, y: float, ancho: float, base: float, r: float = 4) -> str:
    """Barra con las esquinas de ARRIBA redondeadas y la base plana.

    Anclar la base al eje (sin redondear) evita que la barra parezca flotar, que
    es el defecto típico de usar un `rect` con `rx` a secas.
    """
    if base - y < r:  # barra más baja que el radio: rectángulo simple
        return (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{ancho:.1f}" height="{max(base - y, 0):.1f}"/>'
        )
    return (
        f'<path d="M{x:.1f},{base:.1f} L{x:.1f},{y + r:.1f} '
        f"Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"L{x + ancho - r:.1f},{y:.1f} "
        f"Q{x + ancho:.1f},{y:.1f} {x + ancho:.1f},{y + r:.1f} "
        f'L{x + ancho:.1f},{base:.1f} Z"/>'
    )


def _cabecera(ancho: int, alto: int, titulo: str, descripcion: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" '
        f'width="{ancho}" height="{alto}" role="img" aria-labelledby="t d">',
        f"<title id='t'>{titulo}</title>",
        f"<desc id='d'>{descripcion}</desc>",
        f'<rect width="{ancho}" height="{alto}" fill="{SUPERFICIE}"/>',
        f'<g font-family="{FUENTE}">',
    ]


# ---------------------------------------------------------------------------
# Gráfica 1 — progresión del retrieval
# ---------------------------------------------------------------------------
def progresion_retrieval() -> str:
    etapas = ["Línea base", "H4.1\nembeddings", "H4.2\ntroceado", "H4.3\nreranker"]
    recall = [78.2, 81.8, 83.6, 90.9]
    ruteo = [66.7, 70.0, 71.1, 82.2]

    # Alto holgado: las etiquetas de etapa ocupan dos líneas y la leyenda va debajo,
    # así que apurar el margen inferior hacía que se solaparan.
    ancho, alto = 780, 470
    x0, x1 = 66, 752
    y_cero, y_cien = 348, 62
    escala = (y_cero - y_cien) / 100

    p = _cabecera(
        ancho,
        alto,
        "Progresión del retrieval a lo largo del Hito 4",
        "Recall@3 de chunk y acierto de ruteo en las cuatro configuraciones: "
        "el recall sube de 78,2 % a 90,9 % y el ruteo de 66,7 % a 82,2 %.",
    )

    # Título y subtítulo
    p.append(
        f'<text x="{x0}" y="30" font-size="17" font-weight="700" fill="{TINTA}">'
        "Cada cambio del retrieval, medido contra la línea base</text>"
    )
    p.append(
        f'<text x="{x0}" y="49" font-size="12.5" fill="{TINTA_SUAVE}">'
        "Set dorado de 100 preguntas · 3 repeticiones a temperature=0</text>"
    )

    # Rejilla y eje Y (recesivos: la rejilla no compite con los datos)
    for valor in (0, 25, 50, 75, 100):
        y = y_cero - valor * escala
        p.append(
            f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
            f'stroke="{REJILLA}" stroke-width="1"/>'
        )
        p.append(
            f'<text x="{x0 - 10}" y="{y + 4:.1f}" font-size="11.5" text-anchor="end" '
            f'fill="{TINTA_SUAVE}">{valor} %</text>'
        )

    # Barras
    n = len(etapas)
    paso = (x1 - x0) / n
    barra = 52
    for i, etapa in enumerate(etapas):
        centro = x0 + paso * i + paso / 2
        for serie, (valores, color) in enumerate(((recall, AZUL), (ruteo, NARANJA))):
            v = valores[i]
            y = y_cero - v * escala
            # 2 px de hueco entre las dos barras del par (separador de superficie)
            x = centro - barra - 1 if serie == 0 else centro + 1
            p.append(f'<g fill="{color}">{_barra_arriba_redondeada(x, y, barra, y_cero)}</g>')
            # Etiqueta directa: en una figura impresa no hay tooltip que consultar.
            # El texto se compone APARTE: aplicar .replace(".", ",") sobre la cadena
            # entera convertía también el punto decimal de x="118.0" en x="118,0", que
            # en SVG es una LISTA de coordenadas — y solo se pintaba el primer carácter.
            etiqueta_valor = f"{v:.1f}".replace(".", ",") + " %"
            p.append(
                f'<text x="{x + barra / 2:.1f}" y="{y - 7:.1f}" font-size="12" '
                f'font-weight="600" text-anchor="middle" fill="{TINTA}">{etiqueta_valor}</text>'
            )
        # Etiqueta de la etapa (puede llevar salto de línea)
        for j, linea in enumerate(etapa.split("\n")):
            p.append(
                f'<text x="{centro:.1f}" y="{y_cero + 22 + j * 14}" font-size="12.5" '
                f'text-anchor="middle" fill="{TINTA if j == 0 else TINTA_SUAVE}">{linea}</text>'
            )

    # Eje base
    p.append(
        f'<line x1="{x0}" y1="{y_cero}" x2="{x1}" y2="{y_cero}" stroke="{TINTA_SUAVE}" '
        'stroke-width="1.5"/>'
    )

    # Leyenda (identidad nunca solo por color: hay etiqueta al lado de cada muestra)
    ly = alto - 52
    p.append(f'<rect x="{x0}" y="{ly - 9}" width="11" height="11" rx="2.5" fill="{AZUL}"/>')
    p.append(
        f'<text x="{x0 + 18}" y="{ly}" font-size="12.5" fill="{TINTA}">'
        "Recall@3 de chunk (¿trae la ficha correcta?)</text>"
    )
    p.append(
        f'<rect x="{x0 + 300}" y="{ly - 9}" width="11" height="11" rx="2.5" fill="{NARANJA}"/>'
    )
    p.append(
        f'<text x="{x0 + 318}" y="{ly}" font-size="12.5" fill="{TINTA}">'
        "Acierto de ruteo (¿RAG o conocimiento general?)</text>"
    )

    p.append(
        f'<text x="{x0}" y="{alto - 18}" font-size="11" fill="{TINTA_SUAVE}">'
        "Fuente: tabla comparativa del ADR-006 (corrida de solo-retrieval). "
        "El recall a nivel de fichero está saturado al 100 %, por eso gobierna el de chunk.</text>"
    )
    p += ["</g>", "</svg>"]
    return "\n".join(p)


# ---------------------------------------------------------------------------
# Gráfica 2 — latencia percibida
# ---------------------------------------------------------------------------
def latencia_percibida() -> str:
    # (etiqueta, p50, p95 o None, es_antes)
    filas = [
        ("Antes · el niño no veía nada hasta aquí", 3.88, 5.57, True),
        ("Ahora · empieza a leer", 0.92, 1.18, False),
        ("Ahora · empieza a oír", 2.30, 2.87, False),
        ("Ahora · respuesta y voz completas", 3.88, 5.57, False),
    ]

    ancho, alto = 780, 380
    x0, x1 = 300, 700
    y_primera, paso = 92, 56
    maximo = 6.0
    escala = (x1 - x0) / maximo

    p = _cabecera(
        ancho,
        alto,
        "Latencia percibida del chat antes y después del streaming",
        "Con streaming el niño empieza a leer a los 0,92 s (p50) en vez de esperar "
        "unos 3,9 s sin ver nada.",
    )

    p.append(
        f'<text x="30" y="30" font-size="17" font-weight="700" fill="{TINTA}">'
        "El streaming no acelera la respuesta: adelanta lo que se ve</text>"
    )
    p.append(
        f'<text x="30" y="49" font-size="12.5" fill="{TINTA_SUAVE}">'
        "Medido sobre 15 corridas reales · barra = mediana (p50) · marca clara = p95</text>"
    )

    # Rejilla vertical en segundos
    for s in range(0, 7):
        x = x0 + s * escala
        p.append(
            f'<line x1="{x:.1f}" y1="{y_primera - 26:.0f}" x2="{x:.1f}" '
            f'y2="{y_primera + paso * len(filas) - 30:.0f}" stroke="{REJILLA}" stroke-width="1"/>'
        )
        p.append(
            f'<text x="{x:.1f}" y="{y_primera + paso * len(filas) - 14:.0f}" font-size="11.5" '
            f'text-anchor="middle" fill="{TINTA_SUAVE}">{s} s</text>'
        )

    altura = 26
    for i, (etiqueta, p50, p95, es_antes) in enumerate(filas):
        y = y_primera + paso * i - altura
        color = NARANJA if es_antes else AZUL
        # p95: extensión clara detrás de la barra, para no inventar una segunda serie
        if p95:
            p.append(
                f'<rect x="{x0:.1f}" y="{y:.1f}" width="{p95 * escala:.1f}" height="{altura}" '
                f'rx="4" fill="{color}" opacity="0.22"/>'
            )
        p.append(
            f'<rect x="{x0:.1f}" y="{y:.1f}" width="{p50 * escala:.1f}" height="{altura}" '
            f'rx="4" fill="{color}"/>'
        )
        p.append(
            f'<text x="{x0 - 12}" y="{y + altura / 2 + 4.5:.1f}" font-size="12.5" '
            f'text-anchor="end" fill="{TINTA}">{etiqueta}</text>'
        )
        texto = f"{p50:.2f}".replace(".", ",")
        p.append(
            f'<text x="{x0 + p95 * escala + 8:.1f}" y="{y + altura / 2 + 4.5:.1f}" font-size="12.5" '
            f'font-weight="700" fill="{TINTA}">{texto} s</text>'
        )

    p.append(
        f'<line x1="{x0}" y1="{y_primera - 26:.0f}" x2="{x0}" '
        f'y2="{y_primera + paso * len(filas) - 30:.0f}" stroke="{TINTA_SUAVE}" stroke-width="1.5"/>'
    )

    p.append(
        f'<text x="30" y="{alto - 34}" font-size="11" fill="{TINTA_SUAVE}">'
        "Fuente: docs/mediciones/H8-latencia-streaming.md (n=15, Groq Llama-3.3-70B + "
        "ElevenLabs Flash).</text>"
    )
    p.append(
        f'<text x="30" y="{alto - 18}" font-size="11" fill="{TINTA_SUAVE}">'
        "La fila «Antes» no es una medición del sistema antiguo: es el TOTAL medido hoy, "
        "que es lo que se esperaba en blanco sin streaming.</text>"
    )
    p += ["</g>", "</svg>"]
    return "\n".join(p)


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    salidas = {
        "gr-01-progresion-retrieval.svg": progresion_retrieval(),
        "gr-02-latencia-percibida.svg": latencia_percibida(),
    }
    for nombre, contenido in salidas.items():
        ruta = DESTINO / nombre
        ruta.write_text(contenido, encoding="utf-8")
        print(f"{ruta}  ({len(contenido):,} bytes)")


if __name__ == "__main__":
    main()
