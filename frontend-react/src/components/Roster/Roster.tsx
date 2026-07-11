/**
 * Roster — Fila de selección rápida
 * ==================================
 *
 * Muestra todos los elementos del carrusel como miniaturas: la seleccionada
 * resaltada, y al final unos huecos "bloqueados" (?) que insinúan que vendrán
 * más personajes/lugares. Tocar una miniatura salta a ella en el carrusel.
 */

import type { HoloCardData } from "../../data/holo";
import styles from "./Roster.module.css";

interface Props {
  items: HoloCardData[];
  /** Índice del elemento seleccionado (carta central del carrusel). */
  index: number;
  /** Saltar al elemento j (el padre calcula el delta contra el índice actual). */
  onPick: (j: number) => void;
  /** Cuántos huecos "próximamente" mostrar al final. */
  lockedSlots?: number;
}

/** ¿El arte es una URL de imagen (futuro) o un emoji (hoy)? */
function esImagen(art: string): boolean {
  return /^(https?:|data:|\/)/.test(art);
}

export default function Roster({ items, index, onPick, lockedSlots = 2 }: Props) {
  const n = items.length;
  const i = ((index % n) + n) % n;

  return (
    <div className={styles.roster}>
      {items.map((carta, j) => (
        <button
          key={carta.id}
          type="button"
          className={`${styles.slot} ${j === i ? styles.on : ""}`}
          aria-label={carta.name}
          aria-pressed={j === i}
          onClick={() => onPick(j)}
        >
          {esImagen(carta.art) ? (
            <img className={styles.slotImg} src={carta.art} alt="" />
          ) : (
            <span aria-hidden="true">{carta.art}</span>
          )}
        </button>
      ))}
      {Array.from({ length: lockedSlots }, (_, k) => (
        <span
          key={`locked-${k}`}
          className={`${styles.slot} ${styles.locked}`}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}
