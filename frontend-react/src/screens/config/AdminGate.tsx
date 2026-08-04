/**
 * AdminGate — Puerta de adulto del menú de configuración (Hito 7)
 * ===============================================================
 *
 * Toda la zona de ajustes (claves API, personajes, documentos, borrados) va detrás
 * de una contraseña de administración (≥ 8 caracteres + 2FA opcional desde H9.2d),
 * porque la app la usan niños. Este componente:
 *
 *   - La PRIMERA vez (no hay contraseña) muestra "crear contraseña" (setup).
 *   - Si ya hay contraseña, muestra "introduce la contraseña" (login) + 2FA si procede.
 *   - Si la sesión ya está activa (token válido), llama a onListo() y desaparece.
 *
 * La contraseña nunca viaja en claro al almacenamiento del navegador: solo se envía al
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
  const [codigo, setCodigo] = useState(""); // segundo factor (2FA), si está activo
  const [pide2fa, setPide2fa] = useState(false);
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
      setError("La contraseña y su confirmación no coinciden.");
      return;
    }
    setOcupado(true);
    try {
      if (modo === "setup") {
        await adminSetup(pin);
      } else {
        // Login: si el backend pide 2FA, mostramos el campo de código y esperamos a
        // que el adulto lo introduzca (no entramos todavía).
        const requiere2fa = await adminLogin(pin, pide2fa ? codigo : undefined);
        if (requiere2fa) {
          setPide2fa(true);
          setOcupado(false);
          return;
        }
      }
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
          {pide2fa ? "📲" : "🔐"}
        </span>
        <h2 className={styles.gateTitulo}>
          {pide2fa
            ? "Verificación en dos pasos"
            : esSetup
              ? "Crea la contraseña de administración"
              : "Administración"}
        </h2>
        <p className={styles.gateTexto}>
          {pide2fa
            ? "Introduce el código de tu app de autenticación (o un código de recuperación)."
            : esSetup
              ? "Protege la administración con una contraseña (mínimo 8 caracteres). Se pedirá para entrar en esta zona."
              : "Introduce la contraseña de administración para entrar."}
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void enviar();
          }}
        >
          {pide2fa ? (
            <input
              className={`${styles.input} ${styles.campoTexto}`}
              type="text"
              inputMode="numeric"
              value={codigo}
              placeholder="Código de 6 dígitos"
              autoComplete="one-time-code"
              autoFocus
              onChange={(e) => setCodigo(e.target.value)}
            />
          ) : (
            <>
              <input
                className={styles.input}
                type="password"
                value={pin}
                placeholder={esSetup ? "Contraseña nueva" : "Contraseña"}
                autoComplete="off"
                autoFocus
                onChange={(e) => setPin(e.target.value)}
              />
              {esSetup && (
                <input
                  className={styles.input}
                  type="password"
                  value={pin2}
                  placeholder="Repite la contraseña"
                  autoComplete="off"
                  onChange={(e) => setPin2(e.target.value)}
                />
              )}
            </>
          )}

          {error && <p className={styles.testNo}>❌ {error}</p>}

          <button
            type="submit"
            className="btn btn-primario"
            disabled={ocupado || (pide2fa ? !codigo : !pin)}
          >
            {ocupado ? "…" : pide2fa ? "Verificar y entrar" : esSetup ? "Crear y entrar" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
