/**
 * CardCarousel — Selector de tarjetas reutilizable (personajes y lugares)
 * ========================================================================
 *
 * PRIMERA VERSIÓN (Hito 2): una parrilla simple de tarjetas grandes con
 * emoji + etiqueta de categoría + nombre, navegable con clic. El efecto
 * "coverflow" (carta central grande con vecinas asomando) llegará en el
 * Hito 5; la interfaz de este componente no cambiará.
 */

import "./CardCarousel.css";

export interface Carta {
  id: string;
  emoji: string;
  label: string;
  /** Etiqueta pequeña sobre el nombre (p. ej. la categoría del personaje). */
  sub?: string;
}

interface Props {
  cartas: Carta[];
  /** Id de la carta seleccionada (o null si aún no hay elección). */
  seleccionadaId: string | null;
  onElegir: (id: string) => void;
}

export default function CardCarousel({ cartas, seleccionadaId, onElegir }: Props) {
  return (
    <div className="card-grid">
      {cartas.map((carta) => {
        const seleccionada = carta.id === seleccionadaId;
        return (
          <button
            key={carta.id}
            type="button"
            className={`carta${seleccionada ? " seleccionada" : ""}`}
            aria-pressed={seleccionada}
            onClick={() => onElegir(carta.id)}
          >
            <span className="carta-emoji" aria-hidden="true">
              {carta.emoji}
            </span>
            {carta.sub && <span className="carta-sub">{carta.sub}</span>}
            <span className="carta-label">{carta.label}</span>
          </button>
        );
      })}
    </div>
  );
}
