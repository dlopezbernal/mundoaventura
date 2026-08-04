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

import { useMemo, useRef, useState } from "react";
import Console from "../components/Console/Console";
import ConsentModal from "../components/ConsentModal";
import Coverflow from "../components/Coverflow/Coverflow";
import Roster from "../components/Roster/Roster";
import { assetUrl } from "../api/client";
import type { UbicacionDTO } from "../api/types";
import { holoCard, type HoloCardData } from "../data/holo";
import { FOTO_ID } from "../state/useFlow";

interface Props {
  ubicaciones: UbicacionDTO[];
  index: number;
  fotoFile: File | null;
  ubicacionLista: boolean;
  onMove: (delta: number) => void;
  onElegirFoto: (file: File) => void;
  onNext: () => void;
  onBack: () => void;
}

export default function PlaceSelect({
  ubicaciones,
  index,
  fotoFile,
  ubicacionLista,
  onMove,
  onElegirFoto,
  onNext,
  onBack,
}: Props) {
  const fotoInputRef = useRef<HTMLInputElement>(null);
  // Consentimiento de adulto antes de subir la foto (Hito 9): la foto sale del
  // dispositivo hacia un tercero, así que un adulto debe autorizarlo primero.
  const [pidiendoConsentimiento, setPidiendoConsentimiento] = useState(false);
  // Claves del carrusel: "Mi foto" primera, luego las ubicaciones del catálogo.
  const lugarKeys = useMemo(() => [FOTO_ID, ...ubicaciones.map((u) => u.id)], [ubicaciones]);
  const n = lugarKeys.length;
  const i = ((index % n) + n) % n;
  const keyCentral = lugarKeys[i];

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
    const cartasLugar = ubicaciones.map((u) =>
      holoCard(
        {
          id: u.id,
          // Imagen generada (transparente) si la hay; si no, el emoji de siempre.
          art: u.avatar_url ? assetUrl(u.avatar_url) : (u.emoji ?? "🗺️"),
          name: u.nombre.toUpperCase(),
          tag: "MUNDO",
        },
        "var(--holo)",
      ),
    );
    return [fotoCard, ...cartasLugar];
  }, [fotoFile, ubicaciones]);

  function onFotoElegida(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onElegirFoto(file);
    event.target.value = ""; // permite reelegir el mismo archivo
  }

  /** Activar la central: "Mi foto" sin archivo pide consentimiento; si no, avanza. */
  function onSelectCenter() {
    if (keyCentral === FOTO_ID && !fotoFile) {
      setPidiendoConsentimiento(true); // primero, permiso de adulto (H9)
      return;
    }
    if (ubicacionLista) onNext();
  }

  /** El adulto autorizó: cerramos el aviso y abrimos el selector de archivo. */
  function onConsentir() {
    setPidiendoConsentimiento(false);
    fotoInputRef.current?.click();
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

      {/* Selector de foto oculto: se abre TRAS el consentimiento del adulto. */}
      <input
        ref={fotoInputRef}
        type="file"
        accept="image/png,image/jpeg,image/bmp,image/webp"
        hidden
        onChange={onFotoElegida}
      />

      {pidiendoConsentimiento && (
        <ConsentModal
          onConsentir={onConsentir}
          onCancelar={() => setPidiendoConsentimiento(false)}
        />
      )}
    </section>
  );
}
