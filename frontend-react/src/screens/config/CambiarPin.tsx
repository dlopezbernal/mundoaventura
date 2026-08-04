/**
 * CambiarPin — Formulario para cambiar la CONTRASEÑA de administración (Hito 9.2)
 * ==============================================================================
 *
 * (El nombre del fichero/componente es heredado del Hito 7, cuando el acceso era un
 * PIN; desde el Hito 9.2d la credencial de admin es una CONTRASEÑA ≥ 8 caracteres.)
 *
 * Extraído de SistemaTab: el cambio de contraseña es lo que queda en la pestaña
 * "Sistema" de Admin. Requiere la contraseña actual y la nueva; al cambiarla el
 * backend invalida la sesión, así que hay que volver a entrar.
 */

import { useState } from "react";
import { adminChangePin, BackendError } from "../../api/client";
import styles from "../Settings.module.css";

interface Props {
  /** Se llama tras cambiar la contraseña (el backend invalida la sesión → hay que reentrar). */
  onCambiado: () => void;
}

export default function CambiarPin({ onCambiado }: Props) {
  const [pinActual, setPinActual] = useState("");
  const [pinNuevo, setPinNuevo] = useState("");
  const [pinNuevo2, setPinNuevo2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function onCambiar() {
    setError(null);
    if (pinNuevo !== pinNuevo2) {
      setError("La contraseña nueva y su confirmación no coinciden.");
      return;
    }
    setOcupado(true);
    try {
      await adminChangePin(pinActual, pinNuevo);
      // Cambiar la contraseña invalida la sesión actual en el backend: hay que reentrar.
      window.alert("Contraseña cambiada. Vuelve a introducirla para seguir.");
      onCambiado();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className={styles.pjForm}>
      <h3 className={styles.pjFormTitulo}>🔐 Cambiar contraseña de administración</h3>
      <p className={styles.filaAyuda}>
        Esta contraseña protege la zona de Administración (config global de la app). El
        consentimiento de la foto usa el PIN de familia, aparte. Para cambiarla necesitas
        la actual.
      </p>
      {error && <p className={styles.testNo}>❌ {error}</p>}
      <label className={styles.pjLabel}>
        Contraseña actual
        <input
          className={styles.input}
          type="password"
          value={pinActual}
          autoComplete="off"
          onChange={(e) => setPinActual(e.target.value)}
        />
      </label>
      <div className={styles.pjFila2}>
        <label className={styles.pjLabel}>
          Contraseña nueva
          <input
            className={styles.input}
            type="password"
            value={pinNuevo}
            autoComplete="off"
            onChange={(e) => setPinNuevo(e.target.value)}
          />
        </label>
        <label className={styles.pjLabel}>
          Repite la contraseña nueva
          <input
            className={styles.input}
            type="password"
            value={pinNuevo2}
            autoComplete="off"
            onChange={(e) => setPinNuevo2(e.target.value)}
          />
        </label>
      </div>
      <div className={styles.footer}>
        <button
          type="button"
          className="btn btn-primario"
          onClick={() => void onCambiar()}
          disabled={ocupado || !pinActual || !pinNuevo}
        >
          Cambiar contraseña
        </button>
      </div>
    </div>
  );
}
