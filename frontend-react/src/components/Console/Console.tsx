/**
 * Console — Consola inferior de la máquina
 * =========================================
 *
 * Dial decorativo + línea de estado ("OBJETIVO FIJADO: ...") + barra de
 * progreso del viaje + botón CTA para avanzar. Opcionalmente un botón "atrás".
 * El texto de estado se pasa como nodo para poder resaltar partes en <b>.
 */

import type { CSSProperties, ReactNode } from "react";
import styles from "./Console.module.css";

interface Props {
  /** Línea de estado (admite <b> para resaltar el objetivo). */
  status: ReactNode;
  /** Progreso del viaje 0..1 (rellena la barra). */
  progress: number;
  /** Texto del botón principal. */
  ctaLabel: string;
  onCta: () => void;
  ctaDisabled?: boolean;
  /** Si se pasa, muestra un botón secundario "atrás". */
  onBack?: () => void;
  backLabel?: string;
}

export default function Console({
  status,
  progress,
  ctaLabel,
  onCta,
  ctaDisabled = false,
  onBack,
  backLabel = "◀ ATRÁS",
}: Props) {
  const pct = Math.max(0, Math.min(1, progress)) * 100;
  // El dial apunta según el progreso (de -50° a +50°), guiño decorativo.
  const dialRot = { "--dial-rot": `${-50 + progress * 100}deg` } as CSSProperties;

  return (
    <div className={styles.console}>
      <div className={styles.dial} style={dialRot} aria-hidden="true" />
      <div className={styles.status}>
        <div className={styles.line}>{status}</div>
        <div className={styles.progress}>
          <i style={{ width: `${pct}%` }} />
        </div>
      </div>
      {onBack ? (
        <button type="button" className={styles.back} onClick={onBack}>
          {backLabel}
        </button>
      ) : (
        <span />
      )}
      <button
        type="button"
        className={styles.cta}
        onClick={onCta}
        disabled={ctaDisabled}
      >
        {ctaLabel}
      </button>
    </div>
  );
}
