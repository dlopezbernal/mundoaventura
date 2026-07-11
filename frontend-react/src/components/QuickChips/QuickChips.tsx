/**
 * QuickChips — Preguntas rápidas
 * ===============================
 *
 * Atajos para que el niño pregunte con un toque sin escribir. Al pulsar un chip
 * se envía esa pregunta por el MISMO flujo que una escrita. Se desactivan
 * mientras el personaje piensa o se está grabando/transcribiendo.
 */

import styles from "./QuickChips.module.css";

/** Preguntas por defecto, pensadas para cualquier personaje. */
const PREGUNTAS_RAPIDAS = [
  "¿Qué comes?",
  "¿Dónde vives?",
  "¿Cómo es tu casa?",
  "¿Qué te gusta hacer?",
  "¿Tienes amigos?",
  "Cuéntame algo curioso",
];

interface Props {
  preguntas?: string[];
  disabled?: boolean;
  onElegir: (pregunta: string) => void;
}

export default function QuickChips({
  preguntas = PREGUNTAS_RAPIDAS,
  disabled = false,
  onElegir,
}: Props) {
  return (
    <div className={styles.chips} role="group" aria-label="Preguntas rápidas">
      {preguntas.map((pregunta) => (
        <button
          key={pregunta}
          type="button"
          className={styles.chip}
          disabled={disabled}
          onClick={() => onElegir(pregunta)}
        >
          {pregunta}
        </button>
      ))}
    </div>
  );
}
