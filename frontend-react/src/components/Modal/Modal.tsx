/**
 * Modal — Diálogo genérico a pantalla completa (portal + backdrop)
 * ==================================================================
 *
 * Se usa para aislar por completo el contexto de una edición (p. ej. "qué
 * personaje estoy editando") del resto de la pantalla: mientras está abierto,
 * el título queda fijo arriba (cabecera sticky dentro del propio scroll del
 * panel) y todo lo de detrás del backdrop queda visualmente oscurecido e
 * inerte (el backdrop intercepta los clics).
 *
 * `bloqueado` añade una segunda capa de protección para operaciones que no se
 * pueden interrumpir a medias (p. ej. subir/traducir/reindexar un documento):
 * mientras está activo, ni el botón "✕", ni el backdrop, ni Escape cierran el
 * modal, y se muestra un overlay con spinner sobre el cuerpo (la cabecera
 * sigue visible, para no perder el contexto de qué se está procesando).
 */

import { useEffect } from "react";
import { createPortal } from "react-dom";
import styles from "./Modal.module.css";

/**
 * Mensaje único para CUALQUIER operación que no se puede interrumpir a medias
 * (subir/traducir/reindexar un documento, reindexar todo el catálogo…), tanto
 * dentro de este Modal como en indicadores propios de otras pantallas — para
 * que el adulto vea siempre el mismo aviso y no parezca que la app se congeló.
 */
export const MENSAJE_PROCESANDO = "Procesando… no cierres esta ventana.";

interface Props {
  titulo: React.ReactNode;
  onCerrar: () => void;
  bloqueado?: boolean;
  mensajeBloqueo?: string;
  /** Progreso 0-100 opcional: pinta una barra bajo el mensaje de bloqueo (p. ej. reindexado global). */
  progreso?: number;
  children: React.ReactNode;
}

export default function Modal({
  titulo,
  onCerrar,
  bloqueado = false,
  mensajeBloqueo,
  progreso,
  children,
}: Props) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !bloqueado) onCerrar();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [bloqueado, onCerrar]);

  return createPortal(
    <div className={styles.backdrop} onClick={() => !bloqueado && onCerrar()}>
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-label={typeof titulo === "string" ? titulo : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.header}>
          <h3 className={styles.titulo}>{titulo}</h3>
          <button
            type="button"
            className={styles.cerrar}
            onClick={() => !bloqueado && onCerrar()}
            disabled={bloqueado}
            aria-label="Cerrar"
          >
            ✕
          </button>
        </header>
        <div className={styles.cuerpo}>
          {children}
          {bloqueado && (
            <div className={styles.overlay}>
              <span className={styles.spinner} aria-hidden="true" />
              <p>{mensajeBloqueo ?? MENSAJE_PROCESANDO}</p>
              {progreso !== undefined && (
                <div
                  className={styles.barraProgreso}
                  role="progressbar"
                  aria-valuenow={Math.round(progreso)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div className={styles.barraProgresoRelleno} style={{ width: `${Math.round(progreso)}%` }} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
