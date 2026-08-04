/**
 * CharacterSelect — Paso 1: elegir personaje
 * ===========================================
 *
 * Coverflow de personajes (la carta central es el héroe elegido) + roster de
 * acceso rápido + consola con el CTA "SIGUIENTE". La carta central siempre
 * queda seleccionada, así que el paso está listo desde el primer momento.
 *
 * El catálogo llega por props (cargado por API en App, Hito 4): ya no depende
 * del módulo estático. La agrupación por categorías (GRUPOS) y los tintes sí
 * siguen siendo presentación estática.
 */

import { useMemo } from "react";
import Console from "../components/Console/Console";
import Coverflow from "../components/Coverflow/Coverflow";
import Roster from "../components/Roster/Roster";
import { assetUrl } from "../api/client";
import type { PersonajeDTO } from "../api/types";
import { holoCard, type HoloCardData } from "../data/holo";
import { GRUPOS } from "../data/personajes";

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

interface Props {
  personajes: PersonajeDTO[];
  index: number;
  onMove: (delta: number) => void;
  onNext: () => void;
}

export default function CharacterSelect({ personajes, index, onMove, onNext }: Props) {
  // Cartas de personaje derivadas del catálogo recibido por API.
  const cartas: HoloCardData[] = useMemo(
    () =>
      personajes.map((p) => {
        const categoria = p.categoria ?? "";
        // Avatar generado (imagen) si lo hay; si no, el emoji de siempre.
        const art = p.avatar_url ? assetUrl(p.avatar_url) : (p.emoji ?? "🎭");
        return holoCard(
          {
            id: p.id,
            art,
            name: p.nombre.toUpperCase(),
            tag: (CATEGORIA_LABEL[categoria] ?? categoria).toUpperCase(),
          },
          TINTE_CATEGORIA[categoria] ?? "var(--holo)",
        );
      }),
    [personajes],
  );

  const n = personajes.length;
  const i = ((index % n) + n) % n;
  const elegido = personajes[i];

  return (
    <section>
      <Coverflow
        kicker="◇ ESCANEANDO LÍNEA TEMPORAL ◇"
        title="SELECCIONA TU PERSONAJE"
        subtitle="Rota los hologramas con ◀ ▶ · el proyectado en el centro es tu héroe"
        items={cartas}
        index={index}
        selected
        onMove={onMove}
        onSelectCenter={onNext}
      />

      <Roster items={cartas} index={index} onPick={(j) => onMove(j - i)} lockedSlots={2} />

      <Console
        status={
          <>
            HÉROE FIJADO: <b>{elegido.nombre}</b> · sector{" "}
            {CATEGORIA_LABEL[elegido.categoria ?? ""] ?? elegido.categoria ?? "—"}
          </>
        }
        progress={0.33}
        ctaLabel="SIGUIENTE ▶"
        onCta={onNext}
      />
    </section>
  );
}
