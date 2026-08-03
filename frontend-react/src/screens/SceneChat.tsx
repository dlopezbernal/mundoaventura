/**
 * SceneChat — Paso 3: escena generada + chat
 * ===========================================
 *
 * Muestra el estado de carga (barra holo), el error (con reintentar / cambiar
 * de lugar), o el resultado: la imagen generada a la izquierda y el chat con el
 * personaje a la derecha. Reutiliza los componentes SceneView y Chat existentes
 * (su estilado fino se aborda en la segunda tanda).
 */

import Chat from "../components/Chat";
import SceneView from "../components/SceneView";
import styles from "./SceneChat.module.css";

interface Props {
  cargando: boolean;
  error: string | null;
  escenaBase64: string | null;
  /** key para remontar el chat al cambiar de escena (empieza de cero). */
  chatKey: string;
  personajeId: string;
  personajeNombre: string;
  personajeEmoji: string;
  nombreLugar: string;
  /** Nombre del niño que juega (multi-perfil, H9.2c): personaliza el chat. */
  nombreNino?: string | null;
  /** Sexo del niño ('chico'/'chica'/''): personaliza el género en el chat. */
  sexoNino?: string | null;
  onReintentar: () => void;
  onCambiarLugar: () => void;
  onReiniciar: () => void;
}

export default function SceneChat({
  cargando,
  error,
  escenaBase64,
  chatKey,
  personajeId,
  personajeNombre,
  personajeEmoji,
  nombreLugar,
  nombreNino,
  sexoNino,
  onReintentar,
  onCambiarLugar,
  onReiniciar,
}: Props) {
  if (cargando) {
    return (
      <section className={styles.loading} role="status">
        <span className={styles.loadingEmoji} aria-hidden="true">
          🎨
        </span>
        <p className={styles.loadingText}>GENERANDO TU ESCENA…</p>
        <div className={styles.bar} aria-hidden="true" />
      </section>
    );
  }

  if (error) {
    return (
      <section className={styles.error}>
        <p className={styles.loadingText}>😢 {error}</p>
        <div className={styles.errorBotones}>
          <button
            type="button"
            className={`${styles.btn} ${styles.btnPrimario}`}
            onClick={onReintentar}
          >
            🔁 Reintentar
          </button>
          <button
            type="button"
            className={`${styles.btn} ${styles.btnSecundario}`}
            onClick={onCambiarLugar}
          >
            ← Elegir otro mundo
          </button>
        </div>
      </section>
    );
  }

  if (!escenaBase64) return null;

  return (
    <div className={styles.layout}>
      <SceneView
        escenaBase64={escenaBase64}
        alt={`Escena de ${personajeNombre} en ${nombreLugar}`}
        caption={`${personajeEmoji}  ${personajeNombre} · ${nombreLugar}`}
        onEmpezarDeNuevo={onReiniciar}
        onCambiarLugar={onCambiarLugar}
      />
      {/* key: al generar una escena nueva, el chat empieza de cero. */}
      <Chat
        key={chatKey}
        personajeId={personajeId}
        nombre={personajeNombre}
        emoji={personajeEmoji}
        nombreNino={nombreNino}
        sexoNino={sexoNino}
      />
    </div>
  );
}
