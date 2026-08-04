/**
 * Seguridad2FA — Verificación en dos pasos del Admin (Hito 9.2d)
 * ==============================================================
 *
 * Toggle del 2FA (TOTP) para la zona de Administración. Por defecto está DESACTIVADO
 * (un clon nuevo y el tribunal entran solo con la contraseña); se activa aquí con un
 * clic: enrolar (QR + clave) → confirmar con un código → guardar los códigos de
 * recuperación. Desactivar exige la contraseña actual.
 */

import { useEffect, useState } from "react";
import {
  admin2faConfirmar,
  admin2faDesactivar,
  admin2faEnrolar,
  adminStatus,
  BackendError,
} from "../../api/client";
import type { Admin2FAEnrol } from "../../api/types";
import styles from "../Settings.module.css";

export default function Seguridad2FA() {
  const [activo, setActivo] = useState<boolean | null>(null); // null = cargando
  const [enrol, setEnrol] = useState<Admin2FAEnrol | null>(null);
  const [codigo, setCodigo] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [pinDesactivar, setPinDesactivar] = useState("");
  const [desactivando, setDesactivando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    adminStatus()
      .then((s) => setActivo(s.dos_factor_activo))
      .catch(() => setActivo(false));
  }, []);

  async function activar() {
    setError(null);
    setOcupado(true);
    try {
      setEnrol(await admin2faEnrolar());
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  async function confirmar() {
    setError(null);
    setOcupado(true);
    try {
      setRecovery(await admin2faConfirmar(codigo));
      setActivo(true);
      setEnrol(null);
      setCodigo("");
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  async function desactivar() {
    setError(null);
    setOcupado(true);
    try {
      await admin2faDesactivar(pinDesactivar);
      setActivo(false);
      setDesactivando(false);
      setPinDesactivar("");
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className={styles.pjForm}>
      <h3 className={styles.pjFormTitulo}>📲 Verificación en dos pasos (2FA)</h3>
      <p className={styles.filaAyuda}>
        Añade un segundo factor (una app de autenticación) para entrar en Administración.
        Recomendado si expones la aplicación a internet. Por defecto está desactivado.
      </p>

      {error && <p className={styles.testNo}>❌ {error}</p>}

      {/* Códigos de recuperación recién generados: se muestran UNA sola vez. */}
      {recovery && (
        <div>
          <p className={styles.testOk}>
            ✅ 2FA activado. Guarda estos códigos de recuperación en un lugar seguro: sirven
            para entrar si pierdes el móvil y solo se muestran ahora.
          </p>
          <ul className={styles.recoveryLista}>
            {recovery.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <div className={styles.footer}>
            <button type="button" className="btn btn-primario" onClick={() => setRecovery(null)}>
              Ya los he guardado
            </button>
          </div>
        </div>
      )}

      {/* Enrolamiento en curso: QR + clave + confirmación. */}
      {!recovery && enrol && (
        <div>
          <p className={styles.filaAyuda}>
            Escanea este QR con tu app de autenticación (Google Authenticator, Aegis…) o
            introduce la clave a mano. Luego escribe el código que te muestre.
          </p>
          <img className={styles.qr} src={enrol.qr_svg} alt="Código QR para configurar el 2FA" />
          <p className={styles.claveManual}>
            Clave: <code>{enrol.secret}</code>
          </p>
          <label className={styles.pjLabel}>
            Código de 6 dígitos
            <input
              className={`${styles.input} ${styles.campoTexto}`}
              type="text"
              inputMode="numeric"
              value={codigo}
              autoComplete="one-time-code"
              onChange={(e) => setCodigo(e.target.value)}
            />
          </label>
          <div className={styles.pjBarra}>
            <button
              type="button"
              className="btn btn-primario"
              onClick={() => void confirmar()}
              disabled={ocupado || !codigo}
            >
              Confirmar y activar
            </button>
            <button
              type="button"
              className="btn btn-secundario"
              onClick={() => {
                setEnrol(null);
                setCodigo("");
              }}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Estado en reposo: activar (si off) o desactivar (si on). */}
      {!recovery && !enrol && activo !== null && (
        <>
          {activo ? (
            <>
              <p className={styles.testOk}>✅ El 2FA está activado.</p>
              {!desactivando ? (
                <div className={styles.footer}>
                  <button
                    type="button"
                    className="btn btn-secundario"
                    onClick={() => setDesactivando(true)}
                  >
                    Desactivar 2FA
                  </button>
                </div>
              ) : (
                <>
                  <label className={styles.pjLabel}>
                    Confirma con tu contraseña de administración
                    <input
                      className={styles.input}
                      type="password"
                      value={pinDesactivar}
                      autoComplete="off"
                      onChange={(e) => setPinDesactivar(e.target.value)}
                    />
                  </label>
                  <div className={styles.pjBarra}>
                    <button
                      type="button"
                      className="btn btn-primario"
                      onClick={() => void desactivar()}
                      disabled={ocupado || !pinDesactivar}
                    >
                      Desactivar
                    </button>
                    <button
                      type="button"
                      className="btn btn-secundario"
                      onClick={() => {
                        setDesactivando(false);
                        setPinDesactivar("");
                      }}
                    >
                      Cancelar
                    </button>
                  </div>
                </>
              )}
            </>
          ) : (
            <div className={styles.footer}>
              <button
                type="button"
                className="btn btn-primario"
                onClick={() => void activar()}
                disabled={ocupado}
              >
                Activar 2FA
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
