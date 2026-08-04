/**
 * SceneChat — Paso 3: escena generada + chat
 * ===========================================
 *
 * El chat se monta SIEMPRE a la derecha en cuanto se entra al paso 3, para que
 * el niño pueda empezar a hablar con el personaje MIENTRAS la imagen se genera
 * (así la espera se percibe mucho más corta). El panel izquierdo (la escena)
 * es el único que cambia de estado: barra de carga holo → error (con reintentar
 * / cambiar de lugar) → la imagen generada. Reutiliza SceneView y Chat.
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
  return (
    <div className={styles.layout}>
      {/* Panel izquierdo: carga → error → imagen. El chat (derecha) no espera. */}
      {cargando ? (
        <section className={styles.loading} role="status">
          <span className={styles.loadingEmoji} aria-hidden="true">
            🎨
          </span>
          <p className={styles.loadingText}>GENERANDO TU ESCENA…</p>
          <div className={styles.bar} aria-hidden="true" />
          <p className={styles.loadingHint}>
            Mientras tanto, ¡ya puedes hablar con {personajeNombre}! 👉
          </p>
        </section>
      ) : error ? (
        <section className={styles.error} role="alert">
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
      ) : escenaBase64 ? (
        <SceneView
          escenaBase64={escenaBase64}
          alt={`Escena de ${personajeNombre} en ${nombreLugar}`}
          caption={`${personajeEmoji}  ${personajeNombre} · ${nombreLugar}`}
          onEmpezarDeNuevo={onReiniciar}
          onCambiarLugar={onCambiarLugar}
        />
      ) : null}

      {/* key: al generar una escena nueva, el chat empieza de cero. Se monta ya
          (aunque la imagen aún se esté generando) para acortar la espera. */}
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
