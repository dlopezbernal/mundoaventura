/**
 * QuienJuega — Selector de perfil de niño tras el login (Hito 9.2c)
 * =================================================================
 *
 * Cuando una familia tiene VARIOS niños (hermanos), al entrar se elige quién juega,
 * para personalizar la experiencia ("¡Hola, Marco!") y, más adelante, el chat. Con un
 * solo niño la app lo selecciona sola y no muestra esta pantalla; con ninguno, se
 * entra como familia. La elección se recuerda en el dispositivo (App).
 */

import type { NinoDTO } from "../api/types";
import { avatarNino } from "./avatar";
import styles from "./Settings.module.css";

interface Props {
  nombreFamilia: string;
  ninos: NinoDTO[];
  /** Se llama con el niño elegido. */
  onElegir: (nino: NinoDTO) => void;
  /** Abre la Configuración de la familia (para añadir/editar los niños). */
  onGestionar: () => void;
}

export default function QuienJuega({ nombreFamilia, ninos, onElegir, onGestionar }: Props) {
  return (
    <div className={styles.gate}>
      <div className={styles.gateCard}>
        <span className={styles.gateIcono} aria-hidden="true">
          🎮
        </span>
        <h2 className={styles.gateTitulo}>¿Quién juega?</h2>
        <p className={styles.gateTexto}>Familia {nombreFamilia} — elige tu perfil.</p>

        <div className={styles.perfilLista}>
          {ninos.map((nino) => (
            <button
              key={nino.nombre}
              type="button"
              className={styles.perfilBtn}
              onClick={() => onElegir(nino)}
            >
              <span className={styles.perfilEmoji} aria-hidden="true">
                {avatarNino(nino.sexo)}
              </span>
              <span className={styles.perfilNombre}>{nino.nombre}</span>
            </button>
          ))}
        </div>

        <p className={styles.gateTexto}>
          <button type="button" className={styles.linkBtn} onClick={onGestionar}>
            Gestionar perfiles
          </button>
        </p>
      </div>
    </div>
  );
}
