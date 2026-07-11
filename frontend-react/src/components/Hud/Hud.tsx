/**
 * Hud — Barra HUD superior
 * =========================
 *
 * Marca de la app + lectura de sistema ("● SISTEMA ONLINE"), vidas (♥♥♥) y
 * puntos, al estilo recreativa. Opcionalmente muestra el botón de diagnóstico
 * "Probar conexión" (solo en modo DEBUG), que se le pasa como acción.
 */

import styles from "./Hud.module.css";

interface Props {
  /** Contenido extra a la derecha (p. ej. el botón de diagnóstico en DEBUG). */
  onProbarConexion?: () => void;
}

export default function Hud({ onProbarConexion }: Props) {
  return (
    <header className={styles.hud}>
      <span className={styles.logo}>🕹️ MÁQUINA DEL TIEMPO</span>
      <div className={styles.readout}>
        <span className={`${styles.pill} ${styles.blink}`}>● SISTEMA ONLINE</span>
        <span className={styles.lives} aria-label="Vidas">
          ♥ ♥ ♥
        </span>
        <span className={styles.coin}>◉ 0000</span>
        {onProbarConexion && (
          <button type="button" className={styles.debug} onClick={onProbarConexion}>
            🔌 CONEXIÓN
          </button>
        )}
      </div>
    </header>
  );
}
