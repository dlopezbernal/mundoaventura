/**
 * src/data/personajes.ts — Agrupación de categorías (presentación)
 * ================================================================
 *
 * Desde el Hito 4 el CATÁLOGO de personajes (nombre, emoji, categoría, prompt,
 * voz) ya no vive aquí: se carga por API desde el backend (GET /api/personajes,
 * ver api/client.ts y la tabla `personajes`). Este archivo solo conserva la
 * agrupación por categorías, que es pura presentación de la pantalla de selección.
 */

// Cómo agrupar el catálogo en la interfaz: título de sección -> categorías que incluye.
export const GRUPOS: Record<string, string[]> = {
  Prehistóricos: ["prehistorico"],
  Históricos: ["historico"],
  Ficticios: ["ficticio"],
};
