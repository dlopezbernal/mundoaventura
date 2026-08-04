/**
 * Marca — Isotipo "PORTAL-MUNDO" de MundoAventura (opción 1a)
 * ===========================================================
 *
 * El hexágono holográfico es la PUERTA (proyector holo), el círculo con meridiano
 * y ecuador es el MUNDO, y la aguja dorada es la AVENTURA. Sirve igual para Leonardo,
 * el T-Rex o Peter Pan. Diseño importado del proyecto de Claude Design.
 *
 * Los degradados llevan ids únicos por instancia (useId) para poder pintar la marca
 * varias veces en la misma página sin colisiones de id de SVG.
 */

import { useId } from "react";

interface Props {
  /** Lado del SVG en px (es cuadrado). */
  size?: number;
  className?: string;
  /** Si se pasa, la marca es una imagen con nombre accesible; si no, decorativa. */
  title?: string;
}

export default function Marca({ size = 32, className, title }: Props) {
  const uid = useId();
  const holo = `ma-holo-${uid}`;
  const holoV = `ma-holoV-${uid}`;
  return (
    <svg
      viewBox="0 0 120 120"
      width={size}
      height={size}
      className={className}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      style={{ display: "block" }}
    >
      <defs>
        <linearGradient id={holo} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5eead4" />
          <stop offset="0.55" stopColor="#38bdf8" />
          <stop offset="1" stopColor="#f472b6" />
        </linearGradient>
        <linearGradient id={holoV} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#5eead4" />
          <stop offset="1" stopColor="#f472b6" />
        </linearGradient>
      </defs>
      {/* Hexágono holo = la puerta / proyector */}
      <polygon
        points="60,7 105,33 105,87 60,113 15,87 15,33"
        fill="none"
        stroke={`url(#${holo})`}
        strokeWidth="5"
        strokeLinejoin="round"
      />
      {/* Globo = el mundo (círculo + meridiano + ecuador) */}
      <circle cx="60" cy="60" r="29" fill="none" stroke={`url(#${holo})`} strokeWidth="4.5" />
      <ellipse cx="60" cy="60" rx="11.5" ry="29" fill="none" stroke={`url(#${holoV})`} strokeWidth="3" />
      <line x1="31.5" y1="60" x2="88.5" y2="60" stroke={`url(#${holo})`} strokeWidth="3" />
      {/* Aguja dorada = la aventura */}
      <polygon points="60,25 67,60 60,95 53,60" fill="#fbbf24" />
      <polygon points="25,60 60,53 95,60 60,67" fill="#fbbf24" opacity="0.45" />
    </svg>
  );
}
