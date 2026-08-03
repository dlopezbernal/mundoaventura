/**
 * Hud — Barra HUD superior
 * =========================
 *
 * Marca de la app (icono de máquina del tiempo sci-fi + título), un saludo a la
 * familia con sesión iniciada (Hito 9.2) y, a la derecha, los accesos de adulto:
 * "Configuración" (ligero: gestionar el PIN), "Admin" (la config global y peligrosa)
 * y "Salir" (cierra la sesión de familia). Opcionalmente muestra el botón de
 * diagnóstico "Probar conexión" (solo en modo DEBUG), que se le pasa como acción.
 */

import styles from "./Hud.module.css";

interface Props {
  /** Nombre de la familia con sesión iniciada (para el saludo). */
  nombreFamilia: string;
  /** Abre la pantalla de Configuración del adulto (cambiar PIN). */
  onAbrirConfig: () => void;
  /** Abre la pantalla de Administración (config global y compartida). */
  onAbrirAdmin: () => void;
  /** Cierra la sesión de familia (vuelve a la pantalla de login). */
  onSalir: () => void;
  /** Contenido extra a la derecha (p. ej. el botón de diagnóstico en DEBUG). */
  onProbarConexion?: () => void;
}

export default function Hud({
  nombreFamilia,
  onAbrirConfig,
  onAbrirAdmin,
  onSalir,
  onProbarConexion,
}: Props) {
  return (
    <header className={styles.hud}>
      <span className={styles.logo}>🌀 MÁQUINA DEL TIEMPO</span>
      <div className={styles.readout}>
        <span className={styles.saludo}>Hola, {nombreFamilia}</span>
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
        <button type="button" className={styles.config} onClick={onSalir}>
          🚪 SALIR
        </button>
      </div>
    </header>
  );
}
