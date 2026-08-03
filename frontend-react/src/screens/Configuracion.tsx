/**
 * Configuracion — Pantalla ligera de autoservicio del adulto (Hito 9.2, Fase 1)
 * ==============================================================================
 *
 * Tras la reorganización de accesos (H9.2), "Configuración" deja de contener los
 * ajustes que pueden romper la app: eso vive ahora en "Admin". Aquí queda solo lo
 * seguro de gestionar por cualquier adulto — de momento, CAMBIAR EL PIN (en la Fase 2
 * se añadirá aquí el nombre de los niños del perfil).
 *
 * Va detrás del PIN igualmente (el endpoint de cambio exige sesión de adulto): primero
 * <AdminGate/> (crear o introducir PIN) y luego el formulario de cambio.
 */

import { useState } from "react";
import { adminLogout } from "../api/client";
import styles from "./Settings.module.css";
import AdminGate from "./config/AdminGate";
import CambiarPin from "./config/CambiarPin";

interface Props {
  /** Vuelve al flujo principal cerrando la pantalla. */
  onCerrar: () => void;
}

export default function Configuracion({ onCerrar }: Props) {
  const [autenticado, setAutenticado] = useState(false);

  async function volverAlGate() {
    // El cambio de PIN invalida la sesión: cerramos y mostramos de nuevo la puerta.
    await adminLogout();
    setAutenticado(false);
  }

  return (
    <section className={styles.page} aria-label="Configuración del adulto">
      <header className={styles.head}>
        <div>
          <p className={styles.kicker}>⚙️ AJUSTES</p>
          <h1 className={styles.title}>CONFIGURACIÓN</h1>
        </div>
        <button type="button" className={styles.close} onClick={onCerrar}>
          ✕ Cerrar
        </button>
      </header>

      {!autenticado ? (
        <AdminGate onListo={() => setAutenticado(true)} />
      ) : (
        <CambiarPin onCambiado={() => void volverAlGate()} />
      )}

      <footer className={styles.footer}>
        <button type="button" className="btn btn-secundario" onClick={onCerrar}>
          Volver
        </button>
      </footer>
    </section>
  );
}
