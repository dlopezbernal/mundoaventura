/**
 * Background — Fondo animado "Arcade Holo"
 * =========================================
 *
 * Rejilla en perspectiva + partículas que suben. Es puramente decorativo
 * (aria-hidden, sin clics). Las partículas se generan una vez con posiciones/
 * retardos aleatorios, igual que el <script> del mockup.
 *
 * Las scanlines CRT ya NO viven aquí: se renderizan dentro de .holo-wrap (App)
 * para compartir contexto de apilado con la imagen generada y poder dejarla
 * nítida por encima. Ver .crt-scan en global.css.
 */

import { useMemo } from "react";
import styles from "./Background.module.css";

const NUM_PARTICULAS = 38;

export default function Background() {
  // Posiciones/retardos fijados una sola vez (no dependen del render).
  const particulas = useMemo(
    () =>
      Array.from({ length: NUM_PARTICULAS }, () => ({
        left: `${Math.random() * 100}%`,
        top: `${58 + Math.random() * 42}%`,
        animationDelay: `${Math.random() * 6}s`,
      })),
    [],
  );

  return (
    <div aria-hidden="true">
      <div className={styles.floor} />
      <div className={styles.dots}>
        {particulas.map((estilo, i) => (
          <i key={i} style={estilo} />
        ))}
      </div>
    </div>
  );
}
