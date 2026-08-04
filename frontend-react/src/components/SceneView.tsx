/**
 * SceneView — La escena generada
 * ===============================
 *
 * Muestra la imagen que devolvió el backend (PNG en base64) dentro de un marco
 * holográfico con un badge "IMAGEN GENERADA", una etiqueta "personaje · lugar"
 * debajo y los botones para seguir jugando.
 */

import styles from "./SceneView.module.css";

/**
 * Deduce el tipo de imagen de los primeros bytes del base64, para no atarnos a un
 * formato: el backend puede devolver webp (por defecto, más ligero), png o jpg
 * (ajuste IMG_OUTPUT_FORMAT). webp empieza por "UklGR" (RIFF), jpg por "/9j/".
 */
function mimeDeBase64(b64: string): string {
  if (b64.startsWith("UklGR")) return "image/webp";
  if (b64.startsWith("/9j/")) return "image/jpeg";
  return "image/png";
}

interface Props {
  /** La escena generada, tal como llega del backend (imagen en base64). */
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
          src={`data:${mimeDeBase64(escenaBase64)};base64,${escenaBase64}`}
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
