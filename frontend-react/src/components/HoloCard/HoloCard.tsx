/**
 * HoloCard — Cara de la carta-holograma
 * ======================================
 *
 * Pinta el interior de una carta del coverflow: arte (emoji o imagen), nombre,
 * tag, nivel, nº de serie y barra de energía, más los adornos de la central
 * (etiqueta "◉ FIJADO" y haz de luz) cuando es la carta protagonista.
 *
 * No maneja posición ni transforms: de eso se ocupa el Coverflow. Aquí sólo
 * está el contenido visual, para poder reutilizarlo en cualquier posición.
 */

import type { CSSProperties } from "react";
import type { HoloCardData } from "../../data/holo";
import styles from "./HoloCard.module.css";

interface Props {
  data: HoloCardData;
  /** ¿Es la carta central (fijada)? Añade borde vivo y la etiqueta de fijado. */
  center?: boolean;
  /** ¿La central cuenta como seleccionada? Enciende el latido cian→rosa. */
  selected?: boolean;
}

/** ¿El arte es una URL de imagen (futuro) o un emoji (hoy)? */
function esImagen(art: string): boolean {
  return /^(https?:|data:|\/)/.test(art);
}

export default function HoloCard({ data, center = false, selected = false }: Props) {
  const estilo = { "--tint": data.tint } as CSSProperties;
  const clases = [styles.card, center && styles.center, selected && styles.selected]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={clases} style={estilo}>
      {center && <span className={styles.lock}>◉ FIJADO</span>}

      <div className={styles.art}>
        {esImagen(data.art) ? (
          <img className={styles.artImg} src={data.art} alt="" />
        ) : (
          <>
            <span className={styles.bg} aria-hidden="true">
              {data.art}
            </span>
            {data.art}
          </>
        )}
      </div>

      <span className={styles.corner}>LVL {data.level}</span>

      <div className={styles.cap}>
        <div className={styles.tag}>{data.tag}</div>
        <div className={styles.nm}>{data.name}</div>
        <div className={styles.id}>ID · {data.serial}</div>
        <div className={styles.ebar}>
          <i style={{ width: `${data.energy}%` }} />
        </div>
      </div>
    </div>
  );
}
