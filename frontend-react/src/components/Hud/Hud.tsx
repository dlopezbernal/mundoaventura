/**
 * Hud — Barra HUD superior
 * =========================
 *
 * Marca de la app (icono sci-fi + título "MundoAventura"), un saludo a la
 * familia con sesión iniciada (Hito 9.2) y, a la derecha, los accesos de adulto:
 * "Configuración" (ligero: gestionar el PIN), "Admin" (la config global y peligrosa)
 * y "Salir" (cierra la sesión de familia). El diagnóstico "Probar conexión" ya no
 * vive aquí: se movió a Admin → Sistema (solo tiene sentido para el administrador).
 *
 * Los accesos son botones de SOLO ICONO (más limpios/minimalistas): el texto vive
 * en `aria-label` (accesibilidad) y en `data-tip`, que la hoja de estilos muestra
 * como tooltip al pasar por encima o al enfocar con teclado.
 *
 * Los accesos (📖⚙️🛡️🚪) van PLEGADOS por defecto: un botón ☰ los muestra/oculta,
 * para que el niño no los vea salvo que un adulto los despliegue. El manual va en
 * el mismo grupo: la barra se mantiene con un único punto de entrada (☰) y el niño
 * ve una pantalla limpia.
 *
 * El interruptor de sonido 🔊/🔇 queda FUERA del plegado: es un control del niño
 * (silenciar los efectos de la interfaz), no un acceso de adulto, y tiene que
 * poder apagarse de un toque sin abrir ningún menú.
 */

import { useState } from "react";
import { activarSonido, sfx, sonidoActivo } from "../../audio/sfx";
import Marca from "../Marca/Marca";
import styles from "./Hud.module.css";

interface Props {
  /** Nombre de la familia con sesión iniciada (para el saludo). */
  nombreFamilia: string;
  /** Niño con perfil activo, si hay uno elegido (multi-perfil, H9.2c). */
  ninoActivo?: string | null;
  /** Reabre "¿quién juega?" para cambiar de niño (solo si hay varios). */
  onCambiarNino?: () => void;
  /** Abre el manual de usuario (guía de la app, para niño y adulto). */
  onAbrirManual: () => void;
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
  onAbrirManual,
  onAbrirConfig,
  onAbrirAdmin,
  onSalir,
}: Props) {
  const [abierto, setAbierto] = useState(false);
  // La preferencia vive en el módulo de sonido (y en localStorage); aquí solo se
  // refleja para repintar el icono.
  const [sonido, setSonido] = useState(sonidoActivo);

  function alternarSonido() {
    const encendido = !sonido;
    activarSonido(encendido); // al encender suena la confirmación
    setSonido(encendido);
  }

  return (
    <header className={`${styles.hud}${abierto ? ` ${styles.menuAbierto}` : ""}`}>
      <span className={styles.logo}>
        <Marca size={26} className={styles.logoMark} />
        <span className={styles.logoTexto}>MundoAventura</span>
      </span>
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
        {/* data-no-sfx: sería absurdo que el botón de silenciar hiciera clic. */}
        <button
          type="button"
          data-no-sfx
          className={`${styles.iconBtn} ${styles.sonido}`}
          data-tip={sonido ? "Silenciar los sonidos" : "Activar los sonidos"}
          aria-label={sonido ? "Silenciar los sonidos" : "Activar los sonidos"}
          aria-pressed={!sonido}
          onClick={alternarSonido}
        >
          {sonido ? "🔊" : "🔇"}
        </button>
        {abierto && (
          // data-no-sfx en los tres: abrir un panel suena con "open", que ya es
          // el matiz de esa acción; el "click" genérico encima sobraba.
          <>
            <button
              type="button"
              data-no-sfx
              className={styles.iconBtn}
              data-tip="Manual de usuario"
              aria-label="Manual de usuario"
              onClick={() => {
                sfx("open");
                onAbrirManual();
              }}
            >
              📖
            </button>
            <button
              type="button"
              data-no-sfx
              className={styles.iconBtn}
              data-tip="Configuración"
              aria-label="Configuración"
              onClick={() => {
                sfx("open");
                onAbrirConfig();
              }}
            >
              ⚙️
            </button>
            <button
              type="button"
              data-no-sfx
              className={styles.iconBtn}
              data-tip="Admin"
              aria-label="Admin"
              onClick={() => {
                sfx("open");
                onAbrirAdmin();
              }}
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
          </>
        )}
        <button
          type="button"
          className={styles.iconBtn}
          data-tip={abierto ? "Ocultar" : "Adultos"}
          aria-label={abierto ? "Ocultar menú de adultos" : "Menú de adultos"}
          aria-expanded={abierto}
          onClick={() => setAbierto((a) => !a)}
        >
          {abierto ? "✕" : "☰"}
        </button>
      </div>
    </header>
  );
}
