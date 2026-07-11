/**
 * SceneView — La escena generada
 * ===============================
 *
 * Muestra la imagen que devolvió el backend (PNG en base64) dentro de un marco
 * holográfico con un badge "IMAGEN GENERADA", una etiqueta "personaje · lugar"
 * debajo y los botones para seguir jugando.
 */

import styles from "./SceneView.module.css";

interface Props {
  /** La escena generada, tal como llega del backend (PNG en base64). */
  escenaBase64: string;
  /** Texto alternativo de la imagen (accesibilidad). */
  alt: string;
  /** Etiqueta bajo la imagen: "emoji Personaje · lugar". */
  caption: string;
  onEmpezarDeNuevo: () => void;
  onCambiarLugar: () => void;
}

export default function SceneView({
  escenaBase64,
  alt,
  caption,
  onEmpezarDeNuevo,
  onCambiarLugar,
}: Props) {
  return (
    <section className={styles.scene}>
      <div className={styles.marco}>
        <span className={styles.badge}>◉ IMAGEN GENERADA</span>
        <img
          className={styles.img}
          src={`data:image/png;base64,${escenaBase64}`}
          alt={alt}
        />
      </div>
      <p className={styles.caption}>{caption}</p>
      <div className={styles.botones}>
        <button type="button" className="btn btn-primario" onClick={onCambiarLugar}>
          🗺️ Cambiar de lugar
        </button>
        <button type="button" className="btn btn-secundario" onClick={onEmpezarDeNuevo}>
          🔄 Empezar de nuevo
        </button>
      </div>
    </section>
  );
}
