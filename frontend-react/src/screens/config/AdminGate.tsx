/**
 * AdminGate — Puerta de adulto del menú de configuración (Hito 7)
 * ===============================================================
 *
 * Toda la zona de ajustes (claves API, personajes, documentos, borrados) va
 * detrás de un PIN de adulto, porque la app la usan niños. Este componente:
 *
 *   - La PRIMERA vez (no hay PIN) muestra "crear PIN" (setup).
 *   - Si ya hay PIN, muestra "introduce el PIN" (login).
 *   - Si la sesión ya está activa (token válido), llama a onListo() y desaparece.
 *
 * El PIN nunca viaja en claro al almacenamiento del navegador: solo se envía al
 * backend, que devuelve un token de sesión temporal (ver api/client.ts).
 */

import { useEffect, useState } from "react";
import { adminLogin, adminSetup, adminStatus, BackendError } from "../../api/client";
import styles from "../Settings.module.css";

interface Props {
  /** Se llama cuando el adulto queda autenticado. */
  onListo: () => void;
}

type Modo = "cargando" | "setup" | "login";

export default function AdminGate({ onListo }: Props) {
  const [modo, setModo] = useState<Modo>("cargando");
  const [pin, setPin] = useState("");
  const [pin2, setPin2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    let vivo = true;
    void (async () => {
      try {
        const est = await adminStatus();
        if (!vivo) return;
        if (est.sesion_activa) onListo();
        else setModo(est.configurado ? "login" : "setup");
      } catch (exc) {
        if (vivo) {
          setError(exc instanceof BackendError ? exc.message : String(exc));
          setModo("login");
        }
      }
    })();
    return () => {
      vivo = false;
    };
  }, [onListo]);

  async function enviar() {
    setError(null);
    if (modo === "setup" && pin !== pin2) {
      setError("El PIN y su confirmación no coinciden.");
      return;
    }
    setOcupado(true);
    try {
      if (modo === "setup") await adminSetup(pin);
      else await adminLogin(pin);
      onListo();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  if (modo === "cargando") {
    return (
      <div className={styles.panel}>
        <p className={styles.filaAyuda}>Comprobando acceso…</p>
      </div>
    );
  }

  const esSetup = modo === "setup";

  return (
    <div className={styles.gate}>
      <div className={styles.gateCard}>
        <span className={styles.gateIcono} aria-hidden="true">
          🔐
        </span>
        <h2 className={styles.gateTitulo}>{esSetup ? "Crea un PIN de adulto" : "Zona de adultos"}</h2>
        <p className={styles.gateTexto}>
          {esSetup
            ? "Protege la configuración con un PIN (mínimo 4 caracteres). Lo pedirá cada vez que un adulto quiera entrar en los ajustes."
            : "Introduce el PIN de adulto para entrar en la configuración."}
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void enviar();
          }}
        >
          <input
            className={styles.input}
            type="password"
            value={pin}
            placeholder={esSetup ? "PIN nuevo" : "PIN"}
            autoComplete="off"
            autoFocus
            onChange={(e) => setPin(e.target.value)}
          />
          {esSetup && (
            <input
              className={styles.input}
              type="password"
              value={pin2}
              placeholder="Repite el PIN"
              autoComplete="off"
              onChange={(e) => setPin2(e.target.value)}
            />
          )}

          {error && <p className={styles.testNo}>❌ {error}</p>}

          <button type="submit" className="btn btn-primario" disabled={ocupado || !pin}>
            {ocupado ? "…" : esSetup ? "Crear PIN y entrar" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
