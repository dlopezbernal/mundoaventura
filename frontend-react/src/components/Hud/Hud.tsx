/**
 * Hud — Barra HUD superior
 * =========================
 *
 * Marca de la app (icono de máquina del tiempo sci-fi + título) y, a la derecha,
 * el botón de Configuración. Opcionalmente muestra el botón de diagnóstico
 * "Probar conexión" (solo en modo DEBUG), que se le pasa como acción.
 */

import styles from "./Hud.module.css";

interface Props {
  /** Abre la página de configuración de la aplicación. */
  onAbrirConfig: () => void;
  /** Contenido extra a la derecha (p. ej. el botón de diagnóstico en DEBUG). */
  onProbarConexion?: () => void;
}

export default function Hud({ onAbrirConfig, onProbarConexion }: Props) {
  return (
    <header className={styles.hud}>
      <span className={styles.logo}>🌀 MÁQUINA DEL TIEMPO</span>
      <div className={styles.readout}>
        {onProbarConexion && (
          <button type="button" className={styles.debug} onClick={onProbarConexion}>
            🔌 CONEXIÓN
          </button>
        )}
        <button type="button" className={styles.config} onClick={onAbrirConfig}>
          ⚙️ CONFIGURACIÓN
        </button>
      </div>
    </header>
  );
}
