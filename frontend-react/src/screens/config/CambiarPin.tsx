/**
 * CambiarPin — Formulario para cambiar el PIN de adulto (Hito 9.2)
 * ================================================================
 *
 * Extraído de SistemaTab: en la reorganización de accesos (H9.2, Fase 1) el cambio
 * de PIN es lo ÚNICO que queda en la pantalla "Configuración" (autoservicio seguro),
 * mientras que la config global peligrosa vive en "Admin". Requiere el PIN actual y
 * el nuevo; al cambiarlo el backend invalida la sesión, así que hay que volver a entrar.
 */

import { useState } from "react";
import { adminChangePin, BackendError } from "../../api/client";
import styles from "../Settings.module.css";

interface Props {
  /** Se llama tras cambiar el PIN (el backend invalida la sesión → hay que reentrar). */
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
      setError("El PIN nuevo y su confirmación no coinciden.");
      return;
    }
    setOcupado(true);
    try {
      await adminChangePin(pinActual, pinNuevo);
      // Cambiar el PIN invalida la sesión actual en el backend: hay que reentrar.
      window.alert("PIN cambiado. Vuelve a introducirlo para seguir.");
      onCambiado();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className={styles.pjForm}>
      <h3 className={styles.pjFormTitulo}>🔐 Cambiar PIN de adulto</h3>
      <p className={styles.filaAyuda}>
        El PIN protege la zona de adultos (consentimiento de la foto y la administración).
        Para cambiarlo necesitas el actual.
      </p>
      {error && <p className={styles.testNo}>❌ {error}</p>}
      <label className={styles.pjLabel}>
        PIN actual
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
          PIN nuevo
          <input
            className={styles.input}
            type="password"
            value={pinNuevo}
            autoComplete="off"
            onChange={(e) => setPinNuevo(e.target.value)}
          />
        </label>
        <label className={styles.pjLabel}>
          Repite el PIN nuevo
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
          Cambiar PIN
        </button>
      </div>
    </div>
  );
}
