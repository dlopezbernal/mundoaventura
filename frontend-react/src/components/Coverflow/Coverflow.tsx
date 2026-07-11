/**
 * Coverflow — Carrusel coverflow 3D reutilizable (el corazón del diseño)
 * =======================================================================
 *
 * Funciona con CUALQUIER número de cartas (N). La carta CENTRAL es la
 * seleccionada. Se controla por:
 *   - Flechas ◀ ▶.
 *   - Teclado (← / →) cuando el escenario tiene el foco.
 *   - Swipe táctil y arrastre con ratón (Pointer Events unificados).
 *   - Autoplay que gira solo despacio y se PAUSA al pasar el ratón o al
 *     interactuar (con botón para reanudar). Se desactiva con reduced-motion.
 *   - Puntos indicadores de posición (también navegables).
 *
 * Es CONTROLADO: el índice central vive fuera (en el estado del flujo) y aquí
 * sólo se pide moverlo (`onMove`) o activar la central (`onSelectCenter`).
 */

import { useEffect, useId, useRef, useState } from "react";
import type { HoloCardData } from "../../data/holo";
import HoloCard from "../HoloCard/HoloCard";
import styles from "./Coverflow.module.css";

interface Props {
  /** Textos de cabecera de la selección (kicker / título / subtítulo). */
  kicker: string;
  title: string;
  subtitle: string;
  /** Las cartas a mostrar (N ≥ 1). */
  items: HoloCardData[];
  /** Índice de la carta central (el componente hace el módulo circular). */
  index: number;
  /** ¿La carta central cuenta como seleccionada? (enciende su latido). */
  selected?: boolean;
  /** Girar el carrusel `delta` posiciones (±1, o ± lo que haga falta). */
  onMove: (delta: number) => void;
  /** Activar la carta central (avanzar de paso, abrir selector de foto...). */
  onSelectCenter: () => void;
  /** ¿Arrancar con autoplay? (por defecto sí). */
  autoplay?: boolean;
}

const AUTOPLAY_MS = 3500;
const UMBRAL_SWIPE = 40; // px mínimos de arrastre para contar como swipe

/** ¿El usuario pidió menos movimiento? (desactiva autoplay). */
function reducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

/** Desplazamiento circular con signo de j respecto a i, plegado a [-N/2, N/2]. */
function offset(j: number, i: number, n: number): number {
  let o = ((j - i) % n + n) % n; // 0..n-1
  if (o > n / 2) o -= n; // pliega la mitad lejana a negativo
  return o;
}

/** Clase de posición según el desplazamiento (0 centro, ±1, ±2, resto ocultas). */
function claseDe(o: number): string {
  switch (o) {
    case 0:
      return styles.c0;
    case -1:
      return styles.cl1;
    case 1:
      return styles.cr1;
    case -2:
      return styles.cl2;
    case 2:
      return styles.cr2;
    default:
      return o < 0 ? styles.hiddenL : styles.hiddenR;
  }
}

export default function Coverflow({
  kicker,
  title,
  subtitle,
  items,
  index,
  selected = false,
  onMove,
  onSelectCenter,
  autoplay = true,
}: Props) {
  const n = items.length;
  const i = ((index % n) + n) % n;
  const tituloId = useId();

  // Autoplay pausado a mano (botón). Empieza pausado si reduced-motion.
  const [pausado, setPausado] = useState(() => !autoplay || reducedMotion());
  // Refs para no reiniciar el intervalo por cada hover/arrastre.
  const hoverRef = useRef(false);
  const arrastre = useRef<{ x: number; movido: boolean } | null>(null);

  // Autoplay: mientras no esté pausado, gira una posición cada AUTOPLAY_MS,
  // saltándose los ticks en los que el ratón está encima o se está arrastrando.
  useEffect(() => {
    if (pausado) return;
    const id = window.setInterval(() => {
      if (!hoverRef.current && !arrastre.current) onMove(1);
    }, AUTOPLAY_MS);
    return () => window.clearInterval(id);
  }, [pausado, onMove]);

  /** Cualquier interacción manual pausa el autoplay (se reanuda con el botón). */
  function pausarPorInteraccion() {
    setPausado(true);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      pausarPorInteraccion();
      onMove(-1);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      pausarPorInteraccion();
      onMove(1);
    }
  }

  // --- Arrastre / swipe (Pointer Events: ratón y táctil por igual) ---
  function onPointerDown(e: React.PointerEvent) {
    arrastre.current = { x: e.clientX, movido: false };
  }
  function onPointerMove(e: React.PointerEvent) {
    const a = arrastre.current;
    if (a && Math.abs(e.clientX - a.x) > UMBRAL_SWIPE) a.movido = true;
  }
  function onPointerUp(e: React.PointerEvent) {
    const a = arrastre.current;
    arrastre.current = null;
    if (!a) return;
    const dx = e.clientX - a.x;
    if (Math.abs(dx) > UMBRAL_SWIPE) {
      pausarPorInteraccion();
      onMove(dx < 0 ? 1 : -1); // arrastrar a la izquierda avanza
    }
  }

  /** Clic en una carta: la central se activa; una lateral gira hasta ella.
   *  Si venía de un arrastre, se ignora el clic (no queremos "seleccionar"). */
  function onCartaClick(o: number) {
    if (arrastre.current?.movido) return;
    if (o === 0) {
      onSelectCenter();
    } else {
      pausarPorInteraccion();
      onMove(o);
    }
  }

  return (
    <div>
      <div className={styles.select}>
        <div className={styles.kicker}>{kicker}</div>
        <h2 className={styles.title} id={tituloId}>
          {title}
        </h2>
        <p className={styles.subtitle}>{subtitle}</p>
      </div>

      <div
        className={styles.stage}
        role="listbox"
        aria-label={title}
        aria-activedescendant={`${tituloId}-card-${i}`}
        tabIndex={0}
        onKeyDown={onKeyDown}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={() => {
          hoverRef.current = false;
          arrastre.current = null;
        }}
        onPointerEnter={() => {
          hoverRef.current = true;
        }}
      >
        <button
          type="button"
          className={`${styles.arw} ${styles.l}`}
          aria-label="Anterior"
          onClick={() => {
            pausarPorInteraccion();
            onMove(-1);
          }}
        >
          ◀
        </button>

        {items.map((carta, j) => {
          const o = offset(j, i, n);
          const central = o === 0;
          return (
            <div
              key={carta.id}
              id={`${tituloId}-card-${j}`}
              className={`${styles.flow} ${claseDe(o)}`}
              role="option"
              aria-selected={central}
              aria-label={carta.name}
              onClick={() => onCartaClick(o)}
            >
              <HoloCard data={carta} center={central} selected={central && selected} />
              {central && <span className={styles.beam} aria-hidden="true" />}
            </div>
          );
        })}

        <button
          type="button"
          className={`${styles.arw} ${styles.r}`}
          aria-label="Siguiente"
          onClick={() => {
            pausarPorInteraccion();
            onMove(1);
          }}
        >
          ▶
        </button>
      </div>

      <div className={styles.dots}>
        {items.map((carta, j) => (
          <button
            key={carta.id}
            type="button"
            className={`${styles.dot} ${j === i ? styles.dotOn : ""}`}
            aria-label={`Ir a ${carta.name}`}
            onClick={() => {
              pausarPorInteraccion();
              onMove(offset(j, i, n));
            }}
          />
        ))}
        <button
          type="button"
          className={styles.play}
          aria-label={pausado ? "Reanudar el giro automático" : "Pausar el giro automático"}
          title={pausado ? "Reanudar giro" : "Pausar giro"}
          onClick={() => setPausado((p) => !p)}
        >
          {pausado ? "▶" : "⏸"}
        </button>
      </div>
    </div>
  );
}
