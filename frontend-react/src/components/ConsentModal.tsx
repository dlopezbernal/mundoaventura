/**
 * ConsentModal — Consentimiento de adulto antes de subir la foto (Hito 9 / 9.2c)
 * ==============================================================================
 *
 * Antes de que el niño suba una foto de su cuarto, un ADULTO debe autorizarlo,
 * porque la foto sale del dispositivo hacia un tercero (Replicate). La pantalla
 * explica QUÉ se hace con la foto, A QUIÉN se envía y que NO se almacena, y pide
 * confirmación de adulto con el PIN DE LA FAMILIA (Hito 9.2c):
 *   - Si la familia tiene PIN configurado, se pide ese PIN.
 *   - Si no hay PIN, una casilla "soy el adulto responsable".
 *
 * Es la barrera de RGPD/LOPDGDD (consentimiento parental para menores de 14).
 */

import { useEffect, useState } from "react";
import { BackendError, familiaMe, familiaVerificarPin } from "../api/client";
import { sfx } from "../audio/sfx";
import Modal from "./Modal/Modal";
import styles from "./ConsentModal.module.css";

interface Props {
  onConsentir: () => void;
  onCancelar: () => void;
}

type Modo = "cargando" | "pin" | "casilla";

export default function ConsentModal({ onConsentir, onCancelar }: Props) {
  const [modo, setModo] = useState<Modo>("cargando");
  const [pin, setPin] = useState("");
  const [casilla, setCasilla] = useState(false);
  const [error, setError] = useState("");
  const [verificando, setVerificando] = useState(false);

  // Al abrir, mira si la familia tiene PIN configurado (→ pedirlo) o no (→ casilla).
  useEffect(() => {
    let vivo = true;
    familiaMe()
      .then((s) => {
        if (!vivo) return;
        setModo(s.familia?.tiene_pin ? "pin" : "casilla");
      })
      .catch(() => vivo && setModo("casilla")); // sin sesión de familia legible: casilla
    return () => {
      vivo = false;
    };
  }, []);

  /** Autorización concedida: suena la confirmación y se abre el selector de foto. */
  function autorizar() {
    sfx("select");
    onConsentir();
  }

  async function confirmarConPin() {
    setVerificando(true);
    setError("");
    try {
      if (await familiaVerificarPin(pin)) autorizar();
      else {
        sfx("error");
        setError("El PIN no es correcto.");
      }
    } catch (exc) {
      sfx("error");
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

        {modo === "pin" && (
          <div className={styles.campo}>
            <label htmlFor="consent-pin">Escribe el PIN de la familia para autorizar:</label>
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
          {/* data-no-sfx: autorizar suena con "select" (o con "error" si el PIN
              falla), no con el "click" genérico. */}
          {modo === "pin" && (
            <button
              type="button"
              data-no-sfx
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
              data-no-sfx
              className="btn btn-primario"
              onClick={autorizar}
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
