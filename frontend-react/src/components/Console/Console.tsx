/**
 * Console — Barra inferior de acciones del flujo
 * ===============================================
 *
 * Línea de estado (qué has elegido) + barra de progreso del viaje + botón para
 * avanzar, y opcionalmente uno para retroceder. El estado se pasa como nodo para
 * poder resaltar el nombre elegido en <b>.
 *
 * Nació como la "consola de la máquina", con un dial decorativo y rótulos tipo
 * "PERSONAJE FIJADO: …". En móvil y tablet ocupaba demasiado para lo que dice, así
 * que se quedó con la información y se fue la escenografía: el dial ya no está y el
 * estado es solo el nombre elegido. Los botones también adelgazaron (sin el corte
 * angulado ni el halo grande) para no dominar la pantalla.
 */

import type { ReactNode } from "react";
import { sfx } from "../../audio/sfx";
import styles from "./Console.module.css";

interface Props {
  /** Línea de estado (admite <b> para resaltar lo elegido). */
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

  return (
    <div className={styles.console}>
      <div className={styles.status}>
        <div className={styles.line}>{status}</div>
        <div className={styles.progress}>
          <i style={{ width: `${pct}%` }} />
        </div>
      </div>
      {/* Los botones van juntos en su propia caja: así, cuando no hay "atrás", el
          principal ocupa el ancho en móvil sin necesitar un hueco de relleno.
          Son los dos avances del flujo del niño (SIGUIENTE ▶ / ¡GENERAR! ▶ y
          ◀ ATRÁS), así que llevan su propio sonido con matiz — de ahí el
          `data-no-sfx`, que evita que suene ADEMÁS el "click" global. */}
      <div className={styles.acciones}>
        {onBack && (
          <button
            type="button"
            data-no-sfx
            className={styles.back}
            onClick={() => {
              sfx("back");
              onBack();
            }}
          >
            {backLabel}
          </button>
        )}
        <button
          type="button"
          data-no-sfx
          className={styles.cta}
          onClick={() => {
            sfx("select");
            onCta();
          }}
          disabled={ctaDisabled}
        >
          {ctaLabel}
        </button>
      </div>
    </div>
  );
}
