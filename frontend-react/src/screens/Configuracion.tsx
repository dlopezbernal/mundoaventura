/**
 * Configuracion — Perfil de la familia (autoservicio del adulto, Hito 9.2c)
 * =========================================================================
 *
 * Tras el multi-perfil (H9.2c), "Configuración" (⚙️) es el AUTOSERVICIO de la familia
 * ya logueada: editar el nombre de la familia, gestionar los niños y poner/cambiar el
 * PIN de familia. No toca la config global de la app (eso vive en "Admin" 🛡️, tras su
 * propia credencial).
 *
 * Si la familia tiene PIN configurado, se pide antes de mostrar el editor (proteger la
 * edición del perfil es justamente uno de los papeles del PIN). Si no hay PIN, se entra
 * directo (y el editor invita a crear uno).
 */

import { useState } from "react";
import { BackendError, familiaVerificarPin } from "../api/client";
import type { FamiliaDTO } from "../api/types";
import styles from "./Settings.module.css";
import PerfilFamilia from "./config/PerfilFamilia";

interface Props {
  familia: FamiliaDTO;
  /** Notifica a App la familia actualizada (nombre/niños/PIN). */
  onActualizado: (fam: FamiliaDTO) => void;
  /** Se llama tras eliminar la cuenta (volver al login). */
  onCuentaEliminada: () => void;
  /** Cierra la pantalla y vuelve al flujo. */
  onCerrar: () => void;
}

export default function Configuracion({
  familia,
  onActualizado,
  onCuentaEliminada,
  onCerrar,
}: Props) {
  // Si no hay PIN, no hay puerta: se entra directo.
  const [desbloqueado, setDesbloqueado] = useState(!familia.tiene_pin);
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [verificando, setVerificando] = useState(false);

  async function comprobarPin() {
    setError(null);
    setVerificando(true);
    try {
      if (await familiaVerificarPin(pin)) setDesbloqueado(true);
      else setError("El PIN no es correcto.");
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setVerificando(false);
    }
  }

  return (
    <section className={styles.page} aria-label="Configuración de la familia">
      <header className={styles.head}>
        <div>
          <p className={styles.kicker}>⚙️ FAMILIA</p>
          <h1 className={styles.title}>CONFIGURACIÓN</h1>
        </div>
        <button type="button" className={styles.close} onClick={onCerrar}>
          ✕ Cerrar
        </button>
      </header>

      {!desbloqueado ? (
        <div className={styles.gate}>
          <div className={styles.gateCard}>
            <span className={styles.gateIcono} aria-hidden="true">
              🔐
            </span>
            <h2 className={styles.gateTitulo}>PIN de familia</h2>
            <p className={styles.gateTexto}>Introduce el PIN de la familia para editar el perfil.</p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void comprobarPin();
              }}
            >
              <input
                className={styles.input}
                type="password"
                inputMode="numeric"
                value={pin}
                placeholder="PIN"
                maxLength={4}
                autoComplete="off"
                autoFocus
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
              />
              {error && <p className={styles.testNo}>❌ {error}</p>}
              <button type="submit" className="btn btn-primario" disabled={verificando || pin.length !== 4}>
                {verificando ? "…" : "Entrar"}
              </button>
            </form>
          </div>
        </div>
      ) : (
        <PerfilFamilia
          familia={familia}
          onActualizado={onActualizado}
          onEliminada={onCuentaEliminada}
        />
      )}
    </section>
  );
}
