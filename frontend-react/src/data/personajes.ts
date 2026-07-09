/**
 * src/data/personajes.ts — Catálogo de personajes
 * ================================================
 *
 * Aquí definimos QUÉ personajes puede elegir el niño y cómo se muestran en el
 * catálogo (portado de legacy/frontend-flet/personajes.py). Cada uno tiene:
 *   - label     : nombre que se muestra en pantalla.
 *   - categoria : para agrupar en la interfaz (prehistórico / histórico / ficticio).
 *   - emoji     : miniatura provisional (sin necesidad de archivos de imagen).
 *
 * Los `id` (las claves) deben coincidir con los de backend/personajes.py, que
 * es quien tiene el prompt real para la generación.
 */

export interface Personaje {
  label: string;
  categoria: "prehistorico" | "historico" | "ficticio";
  emoji: string;
}

export const PERSONAJES: Record<string, Personaje> = {
  // --- Prehistóricos ---
  triceratops: {
    label: "Triceratops",
    categoria: "prehistorico",
    emoji: "🦕",
  },
  "t-rex": {
    label: "T-Rex",
    categoria: "prehistorico",
    emoji: "🦖",
  },

  // --- Personajes Históricos
  leonardo_da_vinci: {
    label: "Leonardo da Vinci",
    categoria: "historico",
    emoji: "🎨",
  },

  // --- Personajes Ficticios
  sherlock_holmes: {
    label: "Sherlock Holmes",
    categoria: "ficticio",
    emoji: "🕵️",
  },
  peter_pan: {
    label: "Peter Pan",
    categoria: "ficticio",
    emoji: "👦",
  },
};

// Cómo agrupar el catálogo en la interfaz: título de sección -> categorías que incluye.
export const GRUPOS: Record<string, string[]> = {
  Prehistóricos: ["prehistorico"],
  Históricos: ["historico"],
  Ficticios: ["ficticio"],
};

/** Devuelve [id, datos][] de los personajes cuyas categorías están en la lista. */
export function personajesDeGrupo(categorias: string[]): [string, Personaje][] {
  return Object.entries(PERSONAJES).filter(([, datos]) =>
    categorias.includes(datos.categoria),
  );
}
