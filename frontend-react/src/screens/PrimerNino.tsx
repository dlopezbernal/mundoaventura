/**
 * PrimerNino — Gate de bienvenida: alta del primer niño
 * ======================================================
 *
 * Una familia recién creada (típicamente justo después de validar el código del
 * correo) entra con CERO niños. Antes caía directa al flujo sin perfil, y el adulto
 * tenía que descubrir por su cuenta el camino ☰ → ⚙️ Configuración para dar de alta
 * al primero. Esta pantalla lo resuelve en el sitio: añade a uno o varios hermanos
 * sin salir de la bienvenida.
 *
 * Es un gate SALTABLE, no un muro: "Lo haré luego" entra igual (App recuerda el salto
 * por familia para no volver a interrumpir). La CTA sí exige al menos un niño, porque
 * pulsarla con la lista vacía no haría nada distinto de saltar.
 *
 * Reutiliza el chasis de "¿Quién juega?" (.gate/.gateCard) y el mismo endpoint que la
 * edición de perfil (PUT /api/familias/perfil, vía familiaActualizarPerfil), enviando
 * la lista completa de niños junto al nombre de familia actual. La Configuración
 * (PerfilFamilia) queda intacta: sigue siendo el sitio para editarlos después.
 */

import { useState } from "react";
import { BackendError, familiaActualizarPerfil } from "../api/client";
import type { FamiliaDTO, NinoDTO } from "../api/types";
import { avatarNino } from "./avatar";
import styles from "./Settings.module.css";

interface Props {
  familia: FamiliaDTO;
  /** Familia ya actualizada tras guardar (App refresca su estado y sigue al flujo). */
  onListo: (fam: FamiliaDTO) => void;
  /** "Lo haré luego": entra sin perfil y no vuelve a mostrarse. */
  onSaltar: () => void;
}

/** Opciones del segmentado de sexo (mismos valores que el editor de perfil). */
const SEXOS = [
  { valor: "", emoji: "🧒", etiqueta: "Sin especificar" },
  { valor: "chico", emoji: "👦", etiqueta: "Chico" },
  { valor: "chica", emoji: "👧", etiqueta: "Chica" },
] as const;

export default function PrimerNino({ familia, onListo, onSaltar }: Props) {
  const [ninos, setNinos] = useState<NinoDTO[]>([]);
  const [nuevoNino, setNuevoNino] = useState("");
  const [nuevoSexo, setNuevoSexo] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  function anadirNino() {
    const limpio = nuevoNino.trim();
    if (limpio && !ninos.some((n) => n.nombre === limpio)) {
      setNinos([...ninos, { nombre: limpio, sexo: nuevoSexo }]);
    }
    setNuevoNino("");
    setNuevoSexo("");
  }

  async function guardar() {
    setError(null);
    setOcupado(true);
    try {
      const fam = await familiaActualizarPerfil({
        nombre_familia: familia.nombre_familia,
        ninos,
      });
      onListo(fam);
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
      setOcupado(false);
    }
  }

  return (
    <div className={styles.gate}>
      <div className={styles.gateCard}>
        <span className={styles.gateIcono} aria-hidden="true">
          🎉
        </span>
        <p className={styles.obKicker}>◇ CUENTA ACTIVADA ◇</p>
        <h2 className={styles.gateTitulo}>¡Bienvenida, familia!</h2>
        <p className={styles.gateTexto}>
          ¿Quién va a jugar? Añade a los peques de la familia para empezar.
        </p>

        {ninos.length > 0 && (
          <ul className={styles.obLista}>
            {ninos.map((nino) => (
              <li key={nino.nombre} className={styles.obNino}>
                <span className={styles.obNinoAvatar} aria-hidden="true">
                  {avatarNino(nino.sexo)}
                </span>
                <span className={styles.obNinoNombre}>{nino.nombre}</span>
                <button
                  type="button"
                  className={styles.obNinoQuitar}
                  onClick={() => setNinos(ninos.filter((n) => n.nombre !== nino.nombre))}
                  aria-label={`Quitar a ${nino.nombre}`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className={styles.obAlta}>
          <input
            className={`${styles.input} ${styles.campoTexto}`}
            type="text"
            value={nuevoNino}
            placeholder="Nombre del niño"
            maxLength={30}
            autoFocus
            onChange={(e) => setNuevoNino(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                anadirNino();
              }
            }}
          />
          <div className={styles.obAltaFila}>
            <div className={styles.obSexo} role="radiogroup" aria-label="Sexo del niño">
              {SEXOS.map((s) => (
                <button
                  key={s.valor}
                  type="button"
                  role="radio"
                  aria-checked={nuevoSexo === s.valor}
                  aria-label={s.etiqueta}
                  title={s.etiqueta}
                  className={`${styles.obSexoBtn} ${nuevoSexo === s.valor ? styles.obSexoOn : ""}`}
                  onClick={() => setNuevoSexo(s.valor)}
                >
                  <span aria-hidden="true">{s.emoji}</span>
                </button>
              ))}
            </div>
            <button
              type="button"
              className={styles.obAnadir}
              onClick={anadirNino}
              disabled={!nuevoNino.trim()}
            >
              ＋ AÑADIR
            </button>
          </div>
        </div>

        {error && <p className={styles.testNo}>❌ {error}</p>}

        <button
          type="button"
          className={`btn btn-primario ${styles.obCta}`}
          onClick={() => void guardar()}
          disabled={ocupado || ninos.length === 0}
        >
          {ocupado ? "…" : "¡EMPEZAR LA AVENTURA! ▶"}
        </button>

        <p className={styles.gateTexto}>
          <button type="button" className={styles.linkBtn} onClick={onSaltar} disabled={ocupado}>
            Lo haré luego
          </button>
        </p>
        <p className={styles.obAyuda}>
          Puedes añadir o editar perfiles cuando quieras en <strong>☰ → ⚙️ Configuración</strong>.
        </p>
      </div>
    </div>
  );
}
