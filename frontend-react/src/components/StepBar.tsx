/**
 * StepBar — Barra de progreso del asistente (3 pasos)
 * ====================================================
 *
 * Muestra en qué punto del viaje está el niño: Personaje → Lugar → ¡Tu escena!
 * El paso activo se resalta y los ya completados se marcan con ✓.
 */

import "./StepBar.css";

const PASOS = ["Personaje", "Lugar", "¡Tu escena!"];

interface Props {
  /** Paso actual del asistente (1, 2 o 3). */
  pasoActivo: number;
}

export default function StepBar({ pasoActivo }: Props) {
  return (
    <nav className="stepbar" aria-label="Pasos del asistente">
      {PASOS.map((nombre, i) => {
        const n = i + 1;
        const clase =
          n === pasoActivo ? "activo" : n < pasoActivo ? "hecho" : "pendiente";
        return (
          <div
            key={nombre}
            className={`stepbar-paso ${clase}`}
            aria-current={n === pasoActivo ? "step" : undefined}
          >
            <span className="stepbar-num">{n < pasoActivo ? "✓" : n}</span>
            <span className="stepbar-nombre">{nombre}</span>
          </div>
        );
      })}
    </nav>
  );
}
