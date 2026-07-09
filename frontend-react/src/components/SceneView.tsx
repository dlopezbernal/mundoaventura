/**
 * SceneView — La escena generada
 * ===============================
 *
 * Muestra la imagen que devolvió el backend (PNG en base64) con una etiqueta
 * "personaje · lugar" debajo y los botones para seguir jugando. El chat con
 * el personaje se añadirá a su lado en el Hito 3.
 */

import "./SceneView.css";

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
    <section className="scene">
      <img
        className="scene-img"
        src={`data:image/png;base64,${escenaBase64}`}
        alt={alt}
      />
      <p className="scene-caption">{caption}</p>
      <div className="scene-botones">
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
