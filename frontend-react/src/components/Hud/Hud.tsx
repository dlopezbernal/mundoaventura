/**
 * Hud — Barra HUD superior
 * =========================
 *
 * Marca de la app (icono de máquina del tiempo sci-fi + título) y, a la derecha,
 * dos accesos de adulto (H9.2): "Configuración" (ligero: gestionar el PIN) y "Admin"
 * (la config global y peligrosa). Opcionalmente muestra el botón de diagnóstico
 * "Probar conexión" (solo en modo DEBUG), que se le pasa como acción.
 */

import styles from "./Hud.module.css";

interface Props {
  /** Abre la pantalla de Configuración del adulto (cambiar PIN). */
  onAbrirConfig: () => void;
  /** Abre la pantalla de Administración (config global y compartida). */
  onAbrirAdmin: () => void;
  /** Contenido extra a la derecha (p. ej. el botón de diagnóstico en DEBUG). */
  onProbarConexion?: () => void;
}

export default function Hud({ onAbrirConfig, onAbrirAdmin, onProbarConexion }: Props) {
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
        <button type="button" className={styles.config} onClick={onAbrirAdmin}>
          🛡️ ADMIN
        </button>
      </div>
    </header>
  );
}
