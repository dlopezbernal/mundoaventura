/**
 * PlaceSelect — Paso 2: elegir mundo (lugar)
 * ===========================================
 *
 * Mismo Coverflow reutilizable, ahora con lugares. La primera carta es siempre
 * "Mi foto" (el niño sube una foto de su cuarto): sin archivo, tocarla abre el
 * selector; con archivo (o sobre un lugar real), la central queda lista y el
 * CTA genera la escena. El resto del flujo (generación, reutilización) lo
 * gobierna useFlow desde App.
 */

import { useMemo, useRef } from "react";
import Console from "../components/Console/Console";
import Coverflow from "../components/Coverflow/Coverflow";
import Roster from "../components/Roster/Roster";
import { holoCard, type HoloCardData } from "../data/holo";
import { UBICACIONES } from "../data/ubicaciones";
import { FOTO_ID, LUGAR_KEYS } from "../state/useFlow";

/** Cartas de lugares reales (estáticas). "Mi foto" se construye en cada render. */
const CARTAS_LUGAR: Record<string, HoloCardData> = Object.fromEntries(
  Object.entries(UBICACIONES).map(([id, u]) => [
    id,
    holoCard({ id, art: u.emoji, name: u.label.toUpperCase(), tag: "MUNDO" }, "var(--holo)"),
  ]),
);

interface Props {
  index: number;
  fotoFile: File | null;
  ubicacionLista: boolean;
  onMove: (delta: number) => void;
  onElegirFoto: (file: File) => void;
  onNext: () => void;
  onBack: () => void;
}

export default function PlaceSelect({
  index,
  fotoFile,
  ubicacionLista,
  onMove,
  onElegirFoto,
  onNext,
  onBack,
}: Props) {
  const fotoInputRef = useRef<HTMLInputElement>(null);
  const n = LUGAR_KEYS.length;
  const i = ((index % n) + n) % n;
  const keyCentral = LUGAR_KEYS[i];

  // Lista completa: la carta "Mi foto" primero (su nombre refleja si ya hay foto).
  const cartas: HoloCardData[] = useMemo(() => {
    const fotoCard = holoCard(
      {
        id: FOTO_ID,
        art: "📷",
        name: fotoFile ? "¡FOTO LISTA!" : "MI FOTO",
        tag: "TU MUNDO",
      },
      "var(--pink)",
    );
    return LUGAR_KEYS.map((id) => (id === FOTO_ID ? fotoCard : CARTAS_LUGAR[id]));
  }, [fotoFile]);

  function onFotoElegida(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onElegirFoto(file);
    event.target.value = ""; // permite reelegir el mismo archivo
  }

  /** Activar la central: "Mi foto" sin archivo abre el selector; si no, avanza. */
  function onSelectCenter() {
    if (keyCentral === FOTO_ID && !fotoFile) {
      fotoInputRef.current?.click();
      return;
    }
    if (ubicacionLista) onNext();
  }

  const nombreCentral = cartas[i].name;

  return (
    <section>
      <Coverflow
        kicker="◇ CALIBRANDO COORDENADAS ◇"
        title="SELECCIONA TU MUNDO"
        subtitle="Gira los destinos · o sube una foto de tu cuarto para viajar desde casa"
        items={cartas}
        index={index}
        selected={ubicacionLista}
        onMove={onMove}
        onSelectCenter={onSelectCenter}
      />

      <Roster items={cartas} index={index} onPick={(j) => onMove(j - i)} lockedSlots={2} />

      <Console
        status={
          ubicacionLista ? (
            <>
              MUNDO FIJADO: <b>{nombreCentral}</b> · listo para saltar
            </>
          ) : (
            <>
              📷 Elige un mundo o sube tu foto para continuar
            </>
          )
        }
        progress={0.66}
        ctaLabel="¡GENERAR! ▶"
        onCta={onNext}
        ctaDisabled={!ubicacionLista}
        onBack={onBack}
      />

      {/* Selector de foto oculto: lo abre la carta "Mi foto". */}
      <input
        ref={fotoInputRef}
        type="file"
        accept="image/png,image/jpeg,image/bmp,image/webp"
        hidden
        onChange={onFotoElegida}
      />
    </section>
  );
}
