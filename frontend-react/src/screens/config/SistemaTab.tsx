/**
 * SistemaTab — Pestaña "Sistema" del menú de configuración (Hito 7)
 * =================================================================
 *
 * Zona de mantenimiento del adulto ya autenticado:
 *   - Opciones generales de la aplicación (modo desarrollo/DEBUG).
 *   - Cambiar el PIN de adulto (pide el actual).
 *   - EXPORTAR la configuración a un archivo JSON (ajustes + personajes +
 *     ubicaciones; nunca las claves API).
 *   - IMPORTAR una configuración desde un JSON (el backend hace una copia de
 *     seguridad del SQLite antes de aplicar los cambios).
 *   - Cerrar sesión.
 */

import { useState } from "react";
import {
  adminChangePin,
  adminExport,
  adminImport,
  BackendError,
} from "../../api/client";
import styles from "../Settings.module.css";
import ConfigForm from "./ConfigForm";

interface Props {
  /** Cierra la sesión de adulto (vuelve a la pantalla del PIN). */
  onLogout: () => void;
}

export default function SistemaTab({ onLogout }: Props) {
  const [pinActual, setPinActual] = useState("");
  const [pinNuevo, setPinNuevo] = useState("");
  const [pinNuevo2, setPinNuevo2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function onCambiarPin() {
    setError(null);
    setOkMsg(null);
    if (pinNuevo !== pinNuevo2) {
      setError("El PIN nuevo y su confirmación no coinciden.");
      return;
    }
    setOcupado(true);
    try {
      await adminChangePin(pinActual, pinNuevo);
      // Cambiar el PIN invalida la sesión actual en el backend: hay que reentrar.
      window.alert("PIN cambiado. Vuelve a introducirlo para seguir.");
      onLogout();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  async function onExportar() {
    setError(null);
    setOkMsg(null);
    try {
      const data = await adminExport();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `configuracion-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setOkMsg("Configuración exportada (revisa tus descargas).");
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  async function onImportar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (
      !window.confirm(
        "Importar sobrescribe ajustes, personajes y ubicaciones con los del archivo. " +
          "Se hará una copia de seguridad automática antes. ¿Continuar?",
      )
    )
      return;
    setError(null);
    setOkMsg(null);
    setOcupado(true);
    try {
      const texto = await file.text();
      const parsed = JSON.parse(texto);
      const res = await adminImport(parsed);
      setOkMsg(
        `Importado: ${res.resumen.ajustes} ajuste(s), ${res.resumen.personajes} personaje(s), ` +
          `${res.resumen.ubicaciones} ubicación(es). Copia de seguridad creada.`,
      );
    } catch (exc) {
      if (exc instanceof SyntaxError) setError("El archivo no es un JSON válido.");
      else setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className={styles.cfgWrap}>
      {error && <p className={styles.testNo}>❌ {error}</p>}
      {okMsg && <p className={styles.testOk}>✅ {okMsg}</p>}

      {/* Opciones generales */}
      <ConfigForm categorias={["general"]} intro="Opciones generales de la aplicación." />

      {/* Cambiar PIN */}
      <div className={styles.pjForm}>
        <h3 className={styles.pjFormTitulo}>🔐 Cambiar PIN de adulto</h3>
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
            onClick={() => void onCambiarPin()}
            disabled={ocupado || !pinActual || !pinNuevo}
          >
            Cambiar PIN
          </button>
        </div>
      </div>

      {/* Copia / restauración */}
      <div className={styles.pjForm}>
        <h3 className={styles.pjFormTitulo}>💾 Copia de seguridad de la configuración</h3>
        <p className={styles.filaAyuda}>
          Exporta un archivo con los ajustes, personajes y ubicaciones (nunca las claves de
          las plataformas). Puedes volver a importarlo aquí; antes de aplicarlo se guarda una
          copia de seguridad automática.
        </p>
        <div className={styles.pjBarra}>
          <button type="button" className={styles.testBtn} onClick={() => void onExportar()} disabled={ocupado}>
            ⬇️ Exportar configuración
          </button>
          <label className={`${styles.testBtn} ${ocupado ? styles.docsDisabled : ""}`}>
            ⬆️ Importar configuración
            <input type="file" accept="application/json,.json" hidden disabled={ocupado} onChange={onImportar} />
          </label>
        </div>
      </div>

      {/* Privacidad */}
      <div className={styles.pjForm}>
        <h3 className={styles.pjFormTitulo}>📄 Privacidad y datos</h3>
        <p className={styles.filaAyuda}>
          Qué datos usa la app, a dónde van y con qué base legal (RGPD/LOPDGDD). Compártelo
          con las familias antes de usar la aplicación.
        </p>
        <div className={styles.pjBarra}>
          <a
            className={styles.testBtn}
            href="/privacidad.html"
            target="_blank"
            rel="noopener noreferrer"
          >
            📄 Ver política de privacidad
          </a>
        </div>
      </div>

      {/* Sesión */}
      <div className={styles.footer}>
        <button type="button" className="btn btn-secundario" onClick={onLogout}>
          🚪 Cerrar sesión de adulto
        </button>
      </div>
    </div>
  );
}
