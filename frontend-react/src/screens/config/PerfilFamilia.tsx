/**
 * PerfilFamilia — Edición del perfil de la familia (Hito 9.2c)
 * ============================================================
 *
 * Autoservicio de la familia ya logueada: cambiar el NOMBRE de la familia, gestionar
 * los NIÑOS (hermanos) que juegan, y poner/cambiar el PIN DE FAMILIA (4 dígitos) que
 * protege el consentimiento de la foto y la propia edición del perfil.
 *
 * No toca la config global (eso vive en Admin, tras su propia credencial).
 */

import { useState } from "react";
import {
  BackendError,
  familiaActualizarPerfil,
  familiaEliminarCuenta,
  familiaSetPin,
} from "../../api/client";
import type { FamiliaDTO, NinoDTO } from "../../api/types";
import { avatarNino } from "../avatar";
import styles from "../Settings.module.css";

interface Props {
  familia: FamiliaDTO;
  /** Se llama con la familia actualizada, para que App refresque su estado. */
  onActualizado: (fam: FamiliaDTO) => void;
  /** Se llama tras eliminar la cuenta (la sesión ya no existe → volver al login). */
  onEliminada: () => void;
}

export default function PerfilFamilia({ familia, onActualizado, onEliminada }: Props) {
  const [nombre, setNombre] = useState(familia.nombre_familia);
  const [ninos, setNinos] = useState<NinoDTO[]>(familia.ninos);
  const [nuevoNino, setNuevoNino] = useState("");
  const [nuevoSexo, setNuevoSexo] = useState<string>("");
  const [tienePin, setTienePin] = useState(familia.tiene_pin);
  const [pinActual, setPinActual] = useState("");
  const [pinNuevo, setPinNuevo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  function anadirNino() {
    const limpio = nuevoNino.trim();
    if (limpio && !ninos.some((n) => n.nombre === limpio)) {
      setNinos([...ninos, { nombre: limpio, sexo: nuevoSexo }]);
    }
    setNuevoNino("");
    setNuevoSexo("");
  }

  async function guardarPerfil() {
    setError(null);
    setOk(null);
    setOcupado(true);
    try {
      const fam = await familiaActualizarPerfil({ nombre_familia: nombre, ninos });
      setNinos(fam.ninos);
      onActualizado(fam);
      setOk("Perfil guardado.");
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  async function eliminarCuenta() {
    if (
      !window.confirm(
        `¿Eliminar la cuenta de la familia "${familia.nombre_familia}"? Se borrarán la cuenta, ` +
          "los perfiles de los niños y las sesiones. Esta acción no se puede deshacer.",
      )
    )
      return;
    setError(null);
    setOcupado(true);
    try {
      await familiaEliminarCuenta();
      onEliminada();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
      setOcupado(false);
    }
  }

  async function guardarPin() {
    setError(null);
    setOk(null);
    setOcupado(true);
    try {
      await familiaSetPin(pinNuevo, tienePin ? pinActual : undefined);
      setTienePin(true);
      setPinActual("");
      setPinNuevo("");
      onActualizado({ ...familia, nombre_familia: nombre, ninos, tiene_pin: true });
      setOk("PIN de familia guardado.");
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className={styles.cfgWrap}>
      {error && <p className={styles.testNo}>❌ {error}</p>}
      {ok && <p className={styles.testOk}>✅ {ok}</p>}

      {/* Nombre + niños */}
      <div className={styles.pjForm}>
        <h3 className={styles.pjFormTitulo}>👨‍👩‍👧‍👦 Perfil de la familia</h3>
        <label className={styles.pjLabel}>
          Nombre de la familia
          <input
            className={styles.input}
            type="text"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
          />
        </label>

        <p className={styles.filaAyuda}>
          Niños que juegan (hermanos). Aparecerán al entrar para elegir "¿quién juega?".
        </p>
        {ninos.length > 0 ? (
          <ul className={styles.ninosLista}>
            {ninos.map((nino) => (
              <li key={nino.nombre} className={styles.ninoItem}>
                <span>
                  {avatarNino(nino.sexo)} {nino.nombre}
                </span>
                <button
                  type="button"
                  className={styles.ninoQuitar}
                  onClick={() => setNinos(ninos.filter((n) => n.nombre !== nino.nombre))}
                  aria-label={`Quitar a ${nino.nombre}`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.filaAyuda}>Aún no hay ningún niño. Añade al menos uno.</p>
        )}

        <div className={styles.docsUrlFila}>
          <input
            className={styles.input}
            type="text"
            value={nuevoNino}
            placeholder="Nombre del niño"
            maxLength={30}
            onChange={(e) => setNuevoNino(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                anadirNino();
              }
            }}
          />
          <select
            className={styles.input}
            value={nuevoSexo}
            aria-label="Sexo del niño"
            onChange={(e) => setNuevoSexo(e.target.value)}
          >
            <option value="">🧒 Sin especificar</option>
            <option value="chico">👦 Chico</option>
            <option value="chica">👧 Chica</option>
          </select>
          <button type="button" className={styles.testBtn} onClick={anadirNino} disabled={!nuevoNino.trim()}>
            ＋ Añadir
          </button>
        </div>

        <div className={styles.footer}>
          <button
            type="button"
            className="btn btn-primario"
            onClick={() => void guardarPerfil()}
            disabled={ocupado || !nombre.trim()}
          >
            Guardar perfil
          </button>
        </div>
      </div>

      {/* PIN de familia */}
      <div className={styles.pjForm}>
        <h3 className={styles.pjFormTitulo}>🔐 PIN de familia (4 dígitos)</h3>
        <p className={styles.filaAyuda}>
          Protege el consentimiento de la foto y la edición de este perfil. No da acceso a
          la administración de la app. {tienePin ? "Ya hay un PIN configurado." : "Aún no has puesto un PIN."}
        </p>
        {tienePin && (
          <label className={styles.pjLabel}>
            PIN actual
            <input
              className={styles.input}
              type="password"
              inputMode="numeric"
              value={pinActual}
              maxLength={4}
              autoComplete="off"
              onChange={(e) => setPinActual(e.target.value.replace(/\D/g, ""))}
            />
          </label>
        )}
        <label className={styles.pjLabel}>
          {tienePin ? "PIN nuevo" : "Crear PIN"}
          <input
            className={styles.input}
            type="password"
            inputMode="numeric"
            value={pinNuevo}
            maxLength={4}
            autoComplete="off"
            onChange={(e) => setPinNuevo(e.target.value.replace(/\D/g, ""))}
          />
        </label>
        <div className={styles.footer}>
          <button
            type="button"
            className="btn btn-primario"
            onClick={() => void guardarPin()}
            disabled={ocupado || pinNuevo.length !== 4 || (tienePin && pinActual.length !== 4)}
          >
            {tienePin ? "Cambiar PIN" : "Crear PIN"}
          </button>
        </div>
      </div>

      {/* Zona peligrosa: borrado de cuenta (derecho de supresión RGPD) */}
      <div className={styles.pjForm}>
        <h3 className={styles.pjFormTitulo}>🗑️ Eliminar la cuenta</h3>
        <p className={styles.filaAyuda}>
          Borra la cuenta de la familia y todos sus datos (perfiles de los niños y sesiones).
          Es tu derecho de supresión (RGPD). No se puede deshacer.
        </p>
        <div className={styles.footer}>
          <button
            type="button"
            className="btn btn-secundario"
            onClick={() => void eliminarCuenta()}
            disabled={ocupado}
          >
            Eliminar cuenta de familia
          </button>
        </div>
      </div>
    </div>
  );
}
