/**
 * ConsentModal — Consentimiento de adulto antes de subir la foto (Hito 9)
 * ========================================================================
 *
 * Antes de que el niño suba una foto de su cuarto, un ADULTO debe autorizarlo,
 * porque la foto sale del dispositivo hacia un tercero (Replicate). La pantalla
 * explica QUÉ se hace con la foto, A QUIÉN se envía y que NO se almacena, y pide
 * confirmación de adulto:
 *   - Si ya hay una sesión de adulto abierta (PIN), basta con confirmar.
 *   - Si hay PIN pero no hay sesión, se pide el PIN.
 *   - Si no hay PIN configurado, una casilla "soy el adulto responsable".
 *
 * Es la barrera de RGPD/LOPDGDD (consentimiento parental para menores de 14).
 */

import { useEffect, useState } from "react";
import { adminLogin, adminStatus, BackendError } from "../api/client";
import Modal from "./Modal/Modal";
import styles from "./ConsentModal.module.css";

interface Props {
  onConsentir: () => void;
  onCancelar: () => void;
}

type Modo = "cargando" | "adulto-ok" | "pin" | "casilla";

export default function ConsentModal({ onConsentir, onCancelar }: Props) {
  const [modo, setModo] = useState<Modo>("cargando");
  const [pin, setPin] = useState("");
  const [casilla, setCasilla] = useState(false);
  const [error, setError] = useState("");
  const [verificando, setVerificando] = useState(false);

  // Al abrir, averigua si hay PIN configurado y/o sesión de adulto activa.
  useEffect(() => {
    let vivo = true;
    adminStatus()
      .then((s) => {
        if (!vivo) return;
        if (s.sesion_activa) setModo("adulto-ok");
        else if (s.configurado) setModo("pin");
        else setModo("casilla");
      })
      .catch(() => vivo && setModo("casilla")); // sin backend de admin: casilla
    return () => {
      vivo = false;
    };
  }, []);

  async function confirmarConPin() {
    setVerificando(true);
    setError("");
    try {
      await adminLogin(pin);
      onConsentir();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : "No pude comprobar el PIN.");
    } finally {
      setVerificando(false);
    }
  }

  return (
    <Modal titulo="🔒 Permiso de un adulto" onCerrar={onCancelar}>
      <div className={styles.contenido}>
        <p>
          Vas a subir una <b>foto de tu cuarto</b> para crear tu escena. Es importante
          que lo sepa un adulto:
        </p>
        <ul className={styles.lista}>
          <li>La foto se envía a <b>Replicate</b> (un servicio en la nube) <b>solo</b> para
            dibujar la escena.</li>
          <li><b>No se guarda</b> en ningún sitio: se usa y se descarta.</li>
          <li>La voz y las preguntas del niño se procesan aparte (ver privacidad).</li>
        </ul>

        <p className={styles.enlacePrivacidad}>
          <a href="/privacidad.html" target="_blank" rel="noopener noreferrer">
            📄 Leer la política de privacidad completa
          </a>
        </p>

        {modo === "cargando" && <p className={styles.cargando}>Un momento…</p>}

        {modo === "adulto-ok" && (
          <p className={styles.ok}>✅ Hay una sesión de adulto abierta. Puedes continuar.</p>
        )}

        {modo === "pin" && (
          <div className={styles.campo}>
            <label htmlFor="consent-pin">Escribe el PIN de adulto para autorizar:</label>
            <input
              id="consent-pin"
              type="password"
              inputMode="numeric"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              className={styles.input}
              autoFocus
            />
          </div>
        )}

        {modo === "casilla" && (
          <label className={styles.casilla}>
            <input
              type="checkbox"
              checked={casilla}
              onChange={(e) => setCasilla(e.target.checked)}
            />
            Soy el adulto responsable y doy mi consentimiento para subir la foto.
          </label>
        )}

        {error && <p className={styles.error}>{error}</p>}

        <div className={styles.botones}>
          <button type="button" className="btn btn-secundario" onClick={onCancelar}>
            Cancelar
          </button>
          {modo === "adulto-ok" && (
            <button type="button" className="btn btn-primario" onClick={onConsentir}>
              Subir la foto
            </button>
          )}
          {modo === "pin" && (
            <button
              type="button"
              className="btn btn-primario"
              onClick={confirmarConPin}
              disabled={!pin || verificando}
            >
              {verificando ? "Comprobando…" : "Autorizar y subir"}
            </button>
          )}
          {modo === "casilla" && (
            <button
              type="button"
              className="btn btn-primario"
              onClick={onConsentir}
              disabled={!casilla}
            >
              Autorizar y subir
            </button>
          )}
        </div>
      </div>
    </Modal>
  );
}
