/**
 * CambiarPassword — Formulario para cambiar la CONTRASEÑA de administración (Hito 9.2)
 * ====================================================================================
 *
 * (Nació en el Hito 7 como "CambiarPin", cuando el acceso era un PIN numérico; desde el
 * Hito 9.2d la credencial de admin es una CONTRASEÑA ≥ 8 caracteres y el nombre lo dice.)
 *
 * Extraído de SistemaTab: el cambio de contraseña es lo que queda en la pestaña
 * "Sistema" de Admin. Requiere la contraseña actual y la nueva; al cambiarla el
 * backend invalida la sesión, así que hay que volver a entrar.
 */

import { useState } from "react";
import { adminChangePassword, BackendError } from "../../api/client";
import styles from "../Settings.module.css";

interface Props {
  /** Se llama tras cambiar la contraseña (el backend invalida la sesión → hay que reentrar). */
  onCambiado: () => void;
}

export default function CambiarPassword({ onCambiado }: Props) {
  const [passwordActual, setPasswordActual] = useState("");
  const [passwordNueva, setPasswordNueva] = useState("");
  const [passwordNueva2, setPasswordNueva2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function onCambiar() {
    setError(null);
    if (passwordNueva !== passwordNueva2) {
      setError("La contraseña nueva y su confirmación no coinciden.");
      return;
    }
    setOcupado(true);
    try {
      await adminChangePassword(passwordActual, passwordNueva);
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
          value={passwordActual}
          autoComplete="off"
          onChange={(e) => setPasswordActual(e.target.value)}
        />
      </label>
      <div className={styles.pjFila2}>
        <label className={styles.pjLabel}>
          Contraseña nueva
          <input
            className={styles.input}
            type="password"
            value={passwordNueva}
            autoComplete="off"
            onChange={(e) => setPasswordNueva(e.target.value)}
          />
        </label>
        <label className={styles.pjLabel}>
          Repite la contraseña nueva
          <input
            className={styles.input}
            type="password"
            value={passwordNueva2}
            autoComplete="off"
            onChange={(e) => setPasswordNueva2(e.target.value)}
          />
        </label>
      </div>
      <div className={styles.footer}>
        <button
          type="button"
          className="btn btn-primario"
          onClick={() => void onCambiar()}
          disabled={ocupado || !passwordActual || !passwordNueva}
        >
          Cambiar contraseña
        </button>
      </div>
    </div>
  );
}
