/**
 * Steps — Línea temporal de 3 pasos
 * ==================================
 *
 * Muestra en qué punto del viaje está el niño: 1·PERSONAJE → 2·MUNDO → 3·¡JUGAR!
 * El paso actual se enciende en holo y los ya superados quedan marcados.
 */

import styles from "./Steps.module.css";

const PASOS = ["1 · PERSONAJE", "2 · MUNDO", "3 · ¡JUGAR!"];

interface Props {
  /** Paso actual (1, 2 o 3). */
  pasoActivo: number;
}

export default function Steps({ pasoActivo }: Props) {
  return (
    <nav className={styles.steps} aria-label="Pasos">
      {PASOS.map((texto, i) => {
        const n = i + 1;
        const claseNodo =
          n === pasoActivo ? styles.on : n < pasoActivo ? styles.done : "";
        return (
          <span key={texto} style={{ display: "contents" }}>
            {i > 0 && (
              <span
                className={`${styles.bar} ${n <= pasoActivo ? styles.barOn : ""}`}
              />
            )}
            <span
              className={`${styles.node} ${claseNodo}`}
              aria-current={n === pasoActivo ? "step" : undefined}
            >
              <span className={styles.label}>{texto}</span>
            </span>
          </span>
        );
      })}
    </nav>
  );
}
