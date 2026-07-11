/**
 * CharacterSelect — Paso 1: elegir personaje
 * ===========================================
 *
 * Coverflow de personajes (la carta central es el héroe elegido) + roster de
 * acceso rápido + consola con el CTA "SIGUIENTE". La carta central siempre
 * queda seleccionada, así que el paso está listo desde el primer momento.
 */

import Console from "../components/Console/Console";
import Coverflow from "../components/Coverflow/Coverflow";
import Roster from "../components/Roster/Roster";
import { holoCard, type HoloCardData } from "../data/holo";
import { GRUPOS, PERSONAJES } from "../data/personajes";
import { PERSONAJE_KEYS } from "../state/useFlow";

/** categoría → título de grupo legible ("prehistorico" → "Prehistóricos"). */
const CATEGORIA_LABEL: Record<string, string> = Object.fromEntries(
  Object.entries(GRUPOS).flatMap(([titulo, cats]) => cats.map((c) => [c, titulo])),
);

/** Tinte de la carta según la categoría del personaje. */
const TINTE_CATEGORIA: Record<string, string> = {
  prehistorico: "var(--amber)",
  historico: "var(--holo)",
  ficticio: "var(--purple)",
};

/** Cartas de personaje (estáticas: derivadas del catálogo). */
const CARTAS: HoloCardData[] = PERSONAJE_KEYS.map((id) => {
  const p = PERSONAJES[id];
  return holoCard(
    {
      id,
      art: p.emoji,
      name: p.label.toUpperCase(),
      tag: CATEGORIA_LABEL[p.categoria]?.toUpperCase() ?? p.categoria.toUpperCase(),
    },
    TINTE_CATEGORIA[p.categoria],
  );
});

interface Props {
  index: number;
  onMove: (delta: number) => void;
  onNext: () => void;
}

export default function CharacterSelect({ index, onMove, onNext }: Props) {
  const n = PERSONAJE_KEYS.length;
  const i = ((index % n) + n) % n;
  const elegido = PERSONAJES[PERSONAJE_KEYS[i]];

  return (
    <section>
      <Coverflow
        kicker="◇ ESCANEANDO LÍNEA TEMPORAL ◇"
        title="SELECCIONA TU PERSONAJE"
        subtitle="Rota los hologramas con ◀ ▶ · el proyectado en el centro es tu héroe"
        items={CARTAS}
        index={index}
        selected
        onMove={onMove}
        onSelectCenter={onNext}
      />

      <Roster
        items={CARTAS}
        index={index}
        onPick={(j) => onMove(j - i)}
        lockedSlots={2}
      />

      <Console
        status={
          <>
            HÉROE FIJADO: <b>{elegido.label}</b> · sector{" "}
            {CATEGORIA_LABEL[elegido.categoria] ?? elegido.categoria}
          </>
        }
        progress={0.33}
        ctaLabel="SIGUIENTE ▶"
        onCta={onNext}
      />
    </section>
  );
}
