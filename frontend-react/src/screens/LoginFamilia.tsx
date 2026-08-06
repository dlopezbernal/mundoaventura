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
 *
 * Dos accesos escapan a esta puerta, porque no dependen de tener cuenta de familia:
 * el MANUAL (leerlo antes de dar el correo) y la ADMINISTRACIÓN (credencial propia).
 */

import { useEffect, useState, useSyncExternalStore } from "react";
import {
  BackendError,
  familiaEstado,
  familiaLogin,
  familiaReenviar,
  familiaSignup,
  familiaVerificar,
} from "../api/client";
import type { FamiliaDTO } from "../api/types";
import Marca from "../components/Marca/Marca";
import { instalar, sePuedeInstalar, suscribirInstalacion } from "../pwa/instalar";
import styles from "./Settings.module.css";

/** ¿Es un Android? Solo cambia el rótulo y el icono de instalar, no el comportamiento. */
function esAndroid(): boolean {
  return typeof navigator !== "undefined" && /android/i.test(navigator.userAgent);
}

/**
 * El robot de Android, dibujado a mano en SVG (cúpula con dos ojos recortados por
 * `evenodd`, más las dos antenas). Sin librería de iconos ni fichero de imagen:
 * es el único icono de marca ajena que usa la app y no compensa nada de eso.
 * Decorativo — el texto de al lado ya dice "Android".
 */
function IconoAndroid({ size = 18 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="currentColor"
      stroke="currentColor"
      aria-hidden="true"
      focusable="false"
      style={{ display: "block" }}
    >
      <path
        fillRule="evenodd"
        d="M4 13a8 8 0 0 1 16 0z
           M8.6 9a1.1 1.1 0 1 0 2.2 0a1.1 1.1 0 1 0 -2.2 0
           M13.2 9a1.1 1.1 0 1 0 2.2 0a1.1 1.1 0 1 0 -2.2 0"
      />
      <line x1="7.6" y1="3.2" x2="9.3" y2="6.2" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="16.4" y1="3.2" x2="14.7" y2="6.2" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

interface Props {
  /** Se llama con la familia una vez autenticada (alta, login o verificación correctos). */
  onListo: (familia: FamiliaDTO) => void;
  /** Abre el manual de usuario SIN salir de la puerta de entrada (aún no hay sesión). */
  onAbrirManual: () => void;
  /** Abre la Administración SIN sesión de familia (tiene su propia credencial). */
  onAbrirAdmin: () => void;
}

type Modo = "cargando" | "login" | "signup" | "verificar";

export default function LoginFamilia({ onListo, onAbrirManual, onAbrirAdmin }: Props) {
  const [modo, setModo] = useState<Modo>("cargando");
  const [nombreFamilia, setNombreFamilia] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [codigo, setCodigo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  // ¿Puede el navegador instalar la app ahora mismo? Lo decide Chrome (ver
  // pwa/instalar.ts); en Safari y Firefox esto es siempre false y no hay botón.
  const puedeInstalar = useSyncExternalStore(
    suscribirInstalacion,
    sePuedeInstalar,
    () => false, // en servidor no hay navegador que pueda instalar
  );

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
      <div className={styles.marca}>
        <Marca size={92} className={styles.marcaMark} title="MundoAventura" />
        <h1 className={styles.marcaTitulo}>MundoAventura</h1>
        <p className={styles.marcaEslogan}>¡Descubre tu próxima aventura!</p>
      </div>

      {/* Instalar la app, como LÍNEA DE DISPONIBILIDAD justo bajo el eslogan.
          Instalar no es una acción administrativa, es parte de la presentación del
          producto ("esto puede vivir en tu móvil"): al pie, junto al acceso de
          Administración, se leía como un residuo. Aquí se ve nada más entrar y no
          compite con el formulario, que es a lo que viene el adulto.
          Solo se pinta si el navegador dice que se puede instalar (ver
          pwa/instalar.ts); si no, no hay nada, que es mejor que un botón muerto. */}
      {puedeInstalar && (
        <div className={styles.instalarLinea}>
          <span className={styles.instalarRotulo}>◇ INSTÁLALA EN TU DISPOSITIVO ◇</span>
          <button type="button" className={styles.instalarChip} onClick={() => void instalar()}>
            {/* El robot solo en Android: el evento de Chrome también salta en un PC,
                y ahí un icono de Android sería sencillamente falso. */}
            {esAndroid() ? <IconoAndroid /> : <span aria-hidden="true">📲</span>}
            {esAndroid() ? "Instalar en Android" : "Instalar la app"}
          </button>
        </div>
      )}

      {/* El manual, ANTES del formulario: para decidir si registras tu correo, primero
          hay que poder ver qué hace la app y cómo trata los datos. */}
      <button type="button" className={styles.manualAcceso} onClick={onAbrirManual}>
        <span className={styles.manualIcono} aria-hidden="true">
          📖
        </span>
        <span>
          <span className={styles.manualTitulo}>Manual de usuario</span>
          <span className={styles.manualTexto}>
            Cómo funciona la app, para el niño y para el adulto.
          </span>
        </span>
      </button>

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

      {/* La Administración NO cuelga de la sesión de familia: va detrás de su propia
          contraseña (+ 2FA opcional), así que el administrador de la instalación
          tiene que poder entrar sin crear ni usar una cuenta de familia. */}
      <button type="button" className={styles.adminAcceso} onClick={onAbrirAdmin}>
        🛡️ Administración de la aplicación
      </button>
    </div>
  );
}
