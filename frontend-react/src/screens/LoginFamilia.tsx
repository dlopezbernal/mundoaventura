/**
 * LoginFamilia — Puerta de entrada de la aplicación (Hito 9.2)
 * ============================================================
 *
 * Con el multi-perfil, la app deja de ser anónima: cada FAMILIA tiene una cuenta
 * (email + contraseña + nombre de familia) y una sesión persistente en el dispositivo.
 * Esta pantalla es la puerta: hasta que no hay una sesión de familia válida, no se
 * puede jugar.
 *
 *   - Si YA hay familias registradas → arranca en "Entrar" (login).
 *   - Si es la primera vez (sin familias) → arranca en "Crear cuenta" (alta).
 *   - Si el servidor exige verificar el correo (toggle EMAIL_VERIFICACION), tras el
 *     alta se pasa a "Verificar": el adulto teclea el código recibido por email.
 *
 * La contraseña solo viaja al backend (que la guarda hasheada); aquí guardamos el
 * TOKEN de sesión que devuelve, en localStorage, para no volver a pedir login.
 */

import { useEffect, useState } from "react";
import {
  BackendError,
  familiaEstado,
  familiaLogin,
  familiaReenviar,
  familiaSignup,
  familiaVerificar,
} from "../api/client";
import type { FamiliaDTO } from "../api/types";
import styles from "./Settings.module.css";

interface Props {
  /** Se llama con la familia una vez autenticada (alta, login o verificación correctos). */
  onListo: (familia: FamiliaDTO) => void;
}

type Modo = "cargando" | "login" | "signup" | "verificar";

export default function LoginFamilia({ onListo }: Props) {
  const [modo, setModo] = useState<Modo>("cargando");
  const [nombreFamilia, setNombreFamilia] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [codigo, setCodigo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  // Al arrancar: si no hay ninguna familia aún, empezamos por el alta; si ya
  // las hay, por el login. (La sesión existente se comprueba en App, no aquí.)
  useEffect(() => {
    let vivo = true;
    void (async () => {
      try {
        const est = await familiaEstado();
        if (vivo) setModo(est.hay_familias ? "login" : "signup");
      } catch {
        if (vivo) setModo("login");
      }
    })();
    return () => {
      vivo = false;
    };
  }, []);

  function cambiarModo(nuevo: Modo) {
    setError(null);
    setAviso(null);
    setPassword("");
    setPassword2("");
    setCodigo("");
    setModo(nuevo);
  }

  async function enviar() {
    setError(null);
    setAviso(null);
    const esSignup = modo === "signup";
    if (esSignup && password !== password2) {
      setError("La contraseña y su confirmación no coinciden.");
      return;
    }
    setOcupado(true);
    try {
      if (esSignup) {
        const res = await familiaSignup(email, password, nombreFamilia);
        if (res.verificacion_requerida) {
          cambiarModo("verificar");
          setAviso(
            res.canal === "consola"
              ? "Modo desarrollo: el código está en la consola del backend."
              : "Te hemos enviado un código a tu correo. Escríbelo aquí para terminar.",
          );
        } else if (res.familia) {
          onListo(res.familia);
        }
      } else {
        const res = await familiaLogin(email, password);
        onListo(res.familia);
      }
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  async function verificar() {
    setError(null);
    setAviso(null);
    setOcupado(true);
    try {
      const res = await familiaVerificar(email, codigo);
      onListo(res.familia);
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  async function reenviar() {
    setError(null);
    setAviso(null);
    setOcupado(true);
    try {
      const res = await familiaReenviar(email);
      setAviso(
        res.canal === "consola"
          ? "Código reenviado (míralo en la consola del backend)."
          : "Te hemos reenviado un código nuevo a tu correo.",
      );
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  if (modo === "cargando") {
    return (
      <div className={styles.gate}>
        <div className={styles.gateCard}>
          <p className={styles.gateTexto}>Cargando…</p>
        </div>
      </div>
    );
  }

  // --- Paso de verificación del correo (OTP) ---
  if (modo === "verificar") {
    return (
      <div className={styles.gate}>
        <div className={styles.gateCard}>
          <span className={styles.gateIcono} aria-hidden="true">
            📩
          </span>
          <h2 className={styles.gateTitulo}>Verifica tu correo</h2>
          <p className={styles.gateTexto}>
            Escribe el código que hemos enviado a <strong>{email}</strong>.
          </p>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void verificar();
            }}
          >
            <input
              className={styles.input}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={codigo}
              placeholder="Código de 6 dígitos"
              maxLength={6}
              autoFocus
              onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))}
            />

            {aviso && <p className={styles.gateTexto}>{aviso}</p>}
            {error && <p className={styles.testNo}>❌ {error}</p>}

            <button type="submit" className="btn btn-primario" disabled={ocupado || codigo.length < 6}>
              {ocupado ? "…" : "Verificar y entrar"}
            </button>
          </form>

          <p className={styles.gateTexto}>
            ¿No te ha llegado?{" "}
            <button
              type="button"
              className={styles.linkBtn}
              onClick={() => void reenviar()}
              disabled={ocupado}
            >
              Reenviar código
            </button>
          </p>
          <p className={styles.gateTexto}>
            <button type="button" className={styles.linkBtn} onClick={() => cambiarModo("login")}>
              ← Volver
            </button>
          </p>
        </div>
      </div>
    );
  }

  const esSignup = modo === "signup";

  return (
    <div className={styles.gate}>
      <div className={styles.gateCard}>
        <span className={styles.gateIcono} aria-hidden="true">
          {esSignup ? "👨‍👩‍👧‍👦" : "👋"}
        </span>
        <h2 className={styles.gateTitulo}>
          {esSignup ? "Crear cuenta de familia" : "¡Hola de nuevo!"}
        </h2>
        <p className={styles.gateTexto}>
          {esSignup
            ? "Crea una cuenta para tu familia. Usaremos el correo de un adulto para entrar y para el consentimiento de uso."
            : "Entra con el correo y la contraseña de tu familia."}
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void enviar();
          }}
        >
          {esSignup && (
            <input
              className={`${styles.input} ${styles.campoTexto}`}
              type="text"
              value={nombreFamilia}
              placeholder="Nombre de la familia (p. ej. Los García)"
              autoComplete="off"
              autoFocus
              onChange={(e) => setNombreFamilia(e.target.value)}
            />
          )}
          <input
            className={`${styles.input} ${styles.campoTexto}`}
            type="email"
            value={email}
            placeholder="Correo de un adulto"
            autoComplete="email"
            autoFocus={!esSignup}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            className={`${styles.input} ${styles.campoTexto}`}
            type="password"
            value={password}
            placeholder={esSignup ? "Contraseña (mínimo 8 caracteres)" : "Contraseña"}
            autoComplete={esSignup ? "new-password" : "current-password"}
            onChange={(e) => setPassword(e.target.value)}
          />
          {esSignup && (
            <input
              className={`${styles.input} ${styles.campoTexto}`}
              type="password"
              value={password2}
              placeholder="Repite la contraseña"
              autoComplete="new-password"
              onChange={(e) => setPassword2(e.target.value)}
            />
          )}

          {aviso && <p className={styles.gateTexto}>{aviso}</p>}
          {error && <p className={styles.testNo}>❌ {error}</p>}

          <button
            type="submit"
            className="btn btn-primario"
            disabled={ocupado || !email || !password || (esSignup && !nombreFamilia)}
          >
            {ocupado ? "…" : esSignup ? "Crear cuenta y entrar" : "Entrar"}
          </button>
        </form>

        <p className={styles.gateTexto}>
          {esSignup ? (
            <>
              ¿Ya tenéis cuenta?{" "}
              <button type="button" className={styles.linkBtn} onClick={() => cambiarModo("login")}>
                Iniciar sesión
              </button>
            </>
          ) : (
            <>
              ¿Primera vez?{" "}
              <button type="button" className={styles.linkBtn} onClick={() => cambiarModo("signup")}>
                Crear cuenta de familia
              </button>
            </>
          )}
        </p>

        <p className={styles.gateTexto}>
          <a href="/privacidad.html" target="_blank" rel="noopener noreferrer">
            Política de privacidad
          </a>
        </p>
      </div>
    </div>
  );
}
