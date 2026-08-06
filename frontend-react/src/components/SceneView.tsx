/**
 * SceneView — La escena generada
 * ===============================
 *
 * Muestra la imagen que devolvió el backend (PNG en base64) dentro de un marco
 * holográfico con un badge "IMAGEN GENERADA", una etiqueta "personaje · lugar"
 * debajo y los botones para seguir jugando.
 *
 * Responsive (mobile-first, ver el handoff de diseño):
 *   · móvil (< 641px)  — la escena grande NO cabe junto al chat, así que se
 *     reduce a una BARRA MINI (miniatura + caption + "⤢ Ver"); el visor que
 *     abre ese botón es el que enseña la imagen a tamaño grande y el que aloja
 *     los dos botones de acción, que en una pantalla estrecha no cabían.
 *   · tablet (641–959) — escena hero; los botones se quedan en SOLO ICONO y
 *     suben a la fila del StepTracker (posicionados sobre el contenedor del
 *     paso, ver SceneChat.module.css), y la caption se oculta: todo eso es
 *     altura que gana el chat.
 *   · PC (≥ 960px)     — escena, caption y botones con texto, como siempre.
 *
 * La escena y la barra mini se pintan SIEMPRE las dos: quién se ve lo decide el
 * CSS (`@media`), no JavaScript. El único estado nuevo es la apertura del visor.
 */

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
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

/**
 * Los dos botones de acción. Se pintan en dos sitios (inline bajo la escena y
 * dentro del visor de móvil), así que viven aquí una sola vez. El icono y el
 * texto van en spans separados porque en tablet el CSS esconde el texto y deja
 * el botón como icono; `aria-label`/`title` mantienen el nombre completo.
 */
function BotonesEscena({
  className,
  onCambiarLugar,
  onEmpezarDeNuevo,
}: {
  className: string;
  onCambiarLugar: () => void;
  onEmpezarDeNuevo: () => void;
}) {
  return (
    <div className={className}>
      <button
        type="button"
        className={styles.btnCta}
        onClick={onCambiarLugar}
        title="Cambiar de lugar"
        aria-label="Cambiar de lugar"
      >
        <span className={styles.btnIco} aria-hidden="true">
          🗺️
        </span>
        <span className={styles.btnLbl}>Cambiar de lugar</span>
      </button>
      <button
        type="button"
        className={styles.btnBack}
        onClick={onEmpezarDeNuevo}
        title="Empezar de nuevo"
        aria-label="Empezar de nuevo"
      >
        <span className={styles.btnIco} aria-hidden="true">
          🔄
        </span>
        <span className={styles.btnLbl}>Empezar de nuevo</span>
      </button>
    </div>
  );
}

export default function SceneView({
  escenaBase64,
  alt,
  caption,
  onEmpezarDeNuevo,
  onCambiarLugar,
}: Props) {
  // Visor "⤢ Ver" (solo móvil): la escena a tamaño grande, en un diálogo.
  const [ampliada, setAmpliada] = useState(false);
  const src = `data:${mimeDeBase64(escenaBase64)};base64,${escenaBase64}`;

  // Escape cierra el visor, como en cualquier diálogo de la app.
  useEffect(() => {
    if (!ampliada) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setAmpliada(false);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [ampliada]);

  return (
    <>
      {/* Escena grande: visible a partir de tablet (en móvil la tapa el CSS). */}
      <section className={styles.scene}>
        <div className={styles.marco}>
          <span className={styles.badge}>◉ IMAGEN GENERADA</span>
          <img className={styles.img} src={src} alt={alt} />
        </div>
        <p className={styles.caption}>{caption}</p>
        <BotonesEscena
          className={styles.botones}
          onCambiarLugar={onCambiarLugar}
          onEmpezarDeNuevo={onEmpezarDeNuevo}
        />
      </section>

      {/* Barra mini: solo móvil. Deja la pantalla entera para el chat sin perder
          de vista la escena, que se amplía con "⤢ Ver". */}
      <div className={styles.minibar}>
        <img className={styles.thumb} src={src} alt="" aria-hidden="true" />
        <span className={styles.miniInfo}>
          <span className={styles.miniCaption}>{caption}</span>
          <span className={styles.miniTag}>◉ IMAGEN GENERADA</span>
        </span>
        <button
          type="button"
          className={styles.miniVer}
          onClick={() => setAmpliada(true)}
          aria-label="Ver la escena en grande"
        >
          ⤢ Ver
        </button>
      </div>

      {ampliada &&
        createPortal(
          <div
            className={styles.visor}
            role="dialog"
            aria-modal="true"
            aria-label="Tu escena"
            onClick={() => setAmpliada(false)}
          >
            <div className={styles.visorPanel} onClick={(e) => e.stopPropagation()}>
              <header className={styles.visorHead}>
                <h3 className={styles.visorTitulo}>🖼️ Tu escena</h3>
                <button
                  type="button"
                  className={styles.visorCerrar}
                  onClick={() => setAmpliada(false)}
                  aria-label="Cerrar"
                >
                  ✕
                </button>
              </header>
              <div className={styles.marco}>
                <span className={styles.badge}>◉ IMAGEN GENERADA</span>
                <img className={styles.imgGrande} src={src} alt={alt} />
              </div>
              <p className={styles.caption}>{caption}</p>
              {/* En móvil los dos botones viven AQUÍ: no cabían en la barra mini. */}
              <BotonesEscena
                className={styles.botonesVisor}
                onCambiarLugar={() => {
                  setAmpliada(false);
                  onCambiarLugar();
                }}
                onEmpezarDeNuevo={() => {
                  setAmpliada(false);
                  onEmpezarDeNuevo();
                }}
              />
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
