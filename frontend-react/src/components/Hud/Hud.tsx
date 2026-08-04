/**
 * Hud — Barra HUD superior
 * =========================
 *
 * Marca de la app (icono de máquina del tiempo sci-fi + título), un saludo a la
 * familia con sesión iniciada (Hito 9.2) y, a la derecha, los accesos de adulto:
 * "Configuración" (ligero: gestionar el PIN), "Admin" (la config global y peligrosa)
 * y "Salir" (cierra la sesión de familia). El diagnóstico "Probar conexión" ya no
 * vive aquí: se movió a Admin → Sistema (solo tiene sentido para el administrador).
 *
 * Los accesos son botones de SOLO ICONO (más limpios/minimalistas): el texto vive
 * en `aria-label` (accesibilidad) y en `data-tip`, que la hoja de estilos muestra
 * como tooltip al pasar por encima o al enfocar con teclado.
 */

import styles from "./Hud.module.css";

interface Props {
  /** Nombre de la familia con sesión iniciada (para el saludo). */
  nombreFamilia: string;
  /** Niño con perfil activo, si hay uno elegido (multi-perfil, H9.2c). */
  ninoActivo?: string | null;
  /** Reabre "¿quién juega?" para cambiar de niño (solo si hay varios). */
  onCambiarNino?: () => void;
  /** Abre la pantalla de Configuración del adulto (cambiar PIN). */
  onAbrirConfig: () => void;
  /** Abre la pantalla de Administración (config global y compartida). */
  onAbrirAdmin: () => void;
  /** Cierra la sesión de familia (vuelve a la pantalla de login). */
  onSalir: () => void;
}

export default function Hud({
  nombreFamilia,
  ninoActivo,
  onCambiarNino,
  onAbrirConfig,
  onAbrirAdmin,
  onSalir,
}: Props) {
  return (
    <header className={styles.hud}>
      <span className={styles.logo}>🌀 MÁQUINA DEL TIEMPO</span>
      <div className={styles.readout}>
        <span className={styles.saludo}>
          Hola, {ninoActivo ?? nombreFamilia}
          {onCambiarNino && (
            <button
              type="button"
              className={`${styles.iconBtn} ${styles.mini}`}
              data-tip="Cambiar de niño"
              aria-label="Cambiar de niño"
              onClick={onCambiarNino}
            >
              👥
            </button>
          )}
        </span>
        <button
          type="button"
          className={styles.iconBtn}
          data-tip="Configuración"
          aria-label="Configuración"
          onClick={onAbrirConfig}
        >
          ⚙️
        </button>
        <button
          type="button"
          className={styles.iconBtn}
          data-tip="Admin"
          aria-label="Admin"
          onClick={onAbrirAdmin}
        >
          🛡️
        </button>
        <button
          type="button"
          className={`${styles.iconBtn} ${styles.salir}`}
          data-tip="Salir"
          aria-label="Salir"
          onClick={onSalir}
        >
          🚪
        </button>
      </div>
    </header>
  );
}
