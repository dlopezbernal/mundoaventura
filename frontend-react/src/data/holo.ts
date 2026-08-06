/**
 * data/holo.ts — Adaptador catálogo → carta-holograma
 * ====================================================
 *
 * Los catálogos (personajes y ubicaciones) son la fuente de verdad de QUÉ hay, y
 * llegan del backend por API (GET /api/personajes y GET /api/ubicaciones); ya no
 * hay ficheros de catálogo en el frontend. Aquí sólo los "vestimos" con los
 * adornos de juego que pide la estética Arcade Holo (nivel, nº de serie, energía,
 * tinte de la carta).
 *
 * Esos adornos son DECORATIVOS y deterministas: se derivan del id con un hash,
 * así una misma carta muestra siempre los mismos valores entre recargas sin
 * tener que guardarlos en el catálogo.
 *
 * `art` es hoy un emoji; el tipo deja la puerta abierta a que en el futuro sea
 * una URL de imagen (el HoloCard ya lo contempla).
 */

export interface HoloCardData {
  id: string;
  art: string; // emoji hoy; url en el futuro
  name: string;
  tag: string; // categoría / subtítulo en mayúsculas pixel
  level: number; // 1..9  (decorativo)
  serial: string; // "0088" (decorativo)
  energy: number; // 0..100 (decorativo)
  tint: string; // color de acento de la carta (var CSS)
}

/** Paleta de tintes para las cartas (variables definidas en tokens.css). */
const TINTES = [
  "var(--holo)",
  "var(--pink)",
  "var(--purple)",
  "var(--amber)",
  "var(--lime)",
];

/** Hash estable y pequeño de una cadena (no criptográfico). */
function hash(texto: string): number {
  let h = 0;
  for (let i = 0; i < texto.length; i++) {
    h = (h * 31 + texto.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

/**
 * Construye la carta-holograma a partir de los datos base del catálogo.
 * `tint`, si se pasa, fuerza el color (útil para agrupar por categoría);
 * si no, se elige de forma estable según el id.
 */
export function holoCard(
  base: { id: string; art: string; name: string; tag: string },
  tint?: string,
): HoloCardData {
  const h = hash(base.id);
  return {
    ...base,
    level: 1 + (h % 9),
    serial: String(1000 + (h % 9000)),
    energy: 60 + (h % 40),
    tint: tint ?? TINTES[h % TINTES.length],
  };
}
