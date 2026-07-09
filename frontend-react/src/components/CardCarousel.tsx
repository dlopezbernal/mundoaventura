/**
 * CardCarousel — Carrusel "coverflow" (personajes y lugares)
 * ===========================================================
 *
 * Réplica del carrusel de la app Flet: la carta central grande y protagonista,
 * las vecinas asomando reducidas y semitransparentes a los lados (con vuelta
 * circular), flechas ‹ › y puntitos de posición debajo. Hecho con CSS
 * transforms + transition, sin librerías.
 *
 * - Tocar una vecina (o una flecha) gira el carrusel.
 * - Tocar la carta central dispara `onCentro` (avanzar de paso, abrir el
 *   selector de foto...), igual que en Flet.
 * - Navegable con teclado: ← → giran, Enter/Espacio activan la central.
 * - En móvil (<760px) las vecinas se ocultan por CSS: flecha + central + flecha.
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
  /** Índice de la carta centrada (el componente hace el módulo circular). */
  idx: number;
  /** ¿La carta central cuenta como seleccionada? (resaltado ámbar) */
  seleccionadaCentral: boolean;
  /** Colorea flechas y puntitos para distinguir cada paso. */
  accent: "morado" | "turquesa";
  /** Nombre del carrusel para lectores de pantalla. */
  etiqueta: string;
  onMover: (delta: number) => void;
  onCentro: () => void;
}

export default function CardCarousel({
  cartas,
  idx,
  seleccionadaCentral,
  accent,
  etiqueta,
  onMover,
  onCentro,
}: Props) {
  const n = cartas.length;
  const i = ((idx % n) + n) % n;
  const anterior = cartas[(i - 1 + n) % n];
  const central = cartas[i];
  const siguiente = cartas[(i + 1) % n];

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      onMover(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      onMover(1);
    }
  }

  function cartaVecina(carta: Carta, delta: -1 | 1) {
    return (
      <button
        type="button"
        className="carta carta-vecina"
        aria-label={`Ir a ${carta.label}`}
        tabIndex={-1} /* el teclado ya navega con ← → desde el carrusel */
        onClick={() => onMover(delta)}
      >
        <span className="carta-emoji" aria-hidden="true">
          {carta.emoji}
        </span>
        <span className="carta-label">{carta.label}</span>
      </button>
    );
  }

  return (
    <div
      className={`carrusel carrusel-${accent}`}
      role="group"
      aria-label={etiqueta}
      tabIndex={0}
      onKeyDown={onKeyDown}
    >
      <div className="carrusel-fila">
        <button
          type="button"
          className="carrusel-flecha"
          aria-label="Anterior"
          onClick={() => onMover(-1)}
        >
          ‹
        </button>

        {cartaVecina(anterior, -1)}

        {/* key={central.id}: al girar, la central "brota" (animación CSS). */}
        <button
          key={central.id}
          type="button"
          className={`carta carta-central${seleccionadaCentral ? " seleccionada" : ""}`}
          onClick={onCentro}
        >
          <span className="carta-emoji" aria-hidden="true">
            {central.emoji}
          </span>
          {central.sub && <span className="carta-sub">{central.sub}</span>}
          <span className="carta-label">{central.label}</span>
        </button>

        {cartaVecina(siguiente, 1)}

        <button
          type="button"
          className="carrusel-flecha"
          aria-label="Siguiente"
          onClick={() => onMover(1)}
        >
          ›
        </button>
      </div>

      <div className="carrusel-puntos" aria-hidden="true">
        {cartas.map((carta, j) => (
          <span
            key={carta.id}
            className={`punto${j === i ? " activo" : ""}`}
          />
        ))}
      </div>
    </div>
  );
}
