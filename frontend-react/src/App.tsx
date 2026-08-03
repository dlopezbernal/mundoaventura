/**
 * App.tsx — Orquestador del asistente "Arcade Holo"
 * ==================================================
 *
 * Monta el armazón visual (fondo animado + HUD + línea de pasos) y, según el
 * paso actual de la máquina de estados (useFlow), muestra una de las tres
 * pantallas: elegir personaje → elegir mundo → escena + chat.
 *
 * Desde el Hito 4/6, los catálogos de personajes y ubicaciones se CARGAN POR API
 * (no de módulos estáticos): App los trae al arrancar, muestra un estado de carga
 * mientras tanto y, una vez disponibles, monta el flujo (useFlow vive en
 * <Asistente/>, que solo se renderiza con los catálogos ya cargados). Al cerrar la
 * configuración se recargan por si se crearon/borraron personajes o ubicaciones.
 */

import { useCallback, useEffect, useState } from "react";
import Background from "./components/Background/Background";
import Hud from "./components/Hud/Hud";
import Steps from "./components/Steps/Steps";
import CharacterSelect from "./screens/CharacterSelect";
import PlaceSelect from "./screens/PlaceSelect";
import SceneChat from "./screens/SceneChat";
import Admin from "./screens/Admin";
import Configuracion from "./screens/Configuracion";
import LoginFamilia from "./screens/LoginFamilia";
import {
  BackendError,
  checkHealth,
  familiaLogout,
  familiaMe,
  getPersonajes,
  getUbicaciones,
} from "./api/client";
import type { FamiliaDTO, PersonajeDTO, UbicacionDTO } from "./api/types";
import { useFlow } from "./state/useFlow";

// Modo desarrollo: muestra el botón "Probar conexión" en el HUD (como el DEBUG
// de la app Flet). En la build para el niño no se define y desaparece.
const DEBUG = import.meta.env.VITE_DEBUG === "true";

async function probarConexion() {
  try {
    const info = await checkHealth();
    window.alert(`✅ Backend OK\n${JSON.stringify(info, null, 2)}`);
  } catch (exc) {
    window.alert(`❌ ${exc instanceof Error ? exc.message : String(exc)}`);
  }
}

export default function App() {
  // Sesión de familia (Hito 9.2): la app va detrás del login de familia.
  // undefined = comprobando todavía; null = sin sesión (mostrar login).
  const [familia, setFamilia] = useState<FamiliaDTO | null | undefined>(undefined);
  // Catálogos cargados por API: null = cargando todavía.
  const [personajes, setPersonajes] = useState<PersonajeDTO[] | null>(null);
  const [ubicaciones, setUbicaciones] = useState<UbicacionDTO[] | null>(null);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  // Pantallas de adulto: sustituyen al flujo principal mientras están activas.
  // Configuración (⚙️) = gestionar el PIN; Admin (🛡️) = config global (H9.2).
  const [mostrarConfig, setMostrarConfig] = useState(false);
  const [mostrarAdmin, setMostrarAdmin] = useState(false);

  const cargarCatalogos = useCallback(async () => {
    setErrorCarga(null);
    try {
      const [pers, ubis] = await Promise.all([getPersonajes(), getUbicaciones()]);
      setPersonajes(pers);
      setUbicaciones(ubis);
    } catch (exc) {
      setErrorCarga(exc instanceof BackendError ? exc.message : String(exc));
    }
  }, []);

  // Al arrancar comprobamos si hay una sesión de familia persistida en el dispositivo.
  useEffect(() => {
    let vivo = true;
    void (async () => {
      try {
        const est = await familiaMe();
        if (vivo) setFamilia(est.autenticada ? (est.familia ?? null) : null);
      } catch {
        if (vivo) setFamilia(null);
      }
    })();
    return () => {
      vivo = false;
    };
  }, []);

  // Los catálogos solo se cargan una vez hay familia con sesión (jugar requiere login).
  useEffect(() => {
    if (familia) void cargarCatalogos();
  }, [familia, cargarCatalogos]);

  /** Al cerrar Admin, recargamos los catálogos (pudieron cambiar) y volvemos al flujo. */
  function cerrarAdmin() {
    setMostrarAdmin(false);
    void cargarCatalogos();
  }

  /** Cierra la sesión de familia y vuelve a la pantalla de login. */
  async function salirFamilia() {
    await familiaLogout();
    setMostrarAdmin(false);
    setMostrarConfig(false);
    setPersonajes(null);
    setUbicaciones(null);
    setFamilia(null);
  }

  // Mientras comprobamos la sesión, un estado de carga sobrio (sin HUD).
  if (familia === undefined) {
    return (
      <>
        <Background />
        <main className="holo-wrap">
          <section className="holo-cargando" role="status">
            <span className="holo-cargando-emoji" aria-hidden="true">
              ⏳
            </span>
            <p>Cargando…</p>
          </section>
          <div className="crt-scan" aria-hidden="true" />
        </main>
      </>
    );
  }

  // Sin sesión de familia: puerta de entrada (login / alta), sin HUD ni flujo.
  if (familia === null) {
    return (
      <>
        <Background />
        <main className="holo-wrap">
          <LoginFamilia onListo={setFamilia} />
          <div className="crt-scan" aria-hidden="true" />
        </main>
      </>
    );
  }

  return (
    <>
      <Background />
      <main className="holo-wrap">
        <Hud
          nombreFamilia={familia.nombre_familia}
          onAbrirConfig={() => setMostrarConfig(true)}
          onAbrirAdmin={() => setMostrarAdmin(true)}
          onSalir={() => void salirFamilia()}
          onProbarConexion={DEBUG ? probarConexion : undefined}
        />

        {mostrarAdmin ? (
          <Admin onCerrar={cerrarAdmin} />
        ) : mostrarConfig ? (
          <Configuracion onCerrar={() => setMostrarConfig(false)} />
        ) : errorCarga ? (
          <section className="holo-cargando" role="alert">
            <p>😢 No pude cargar el catálogo.</p>
            <p className="holo-cargando-detalle">{errorCarga}</p>
            <button type="button" className="btn btn-primario" onClick={() => void cargarCatalogos()}>
              Reintentar
            </button>
          </section>
        ) : !personajes || !ubicaciones ? (
          <section className="holo-cargando" role="status">
            <span className="holo-cargando-emoji" aria-hidden="true">
              ⏳
            </span>
            <p>Cargando…</p>
          </section>
        ) : personajes.length === 0 ? (
          <section className="holo-cargando" role="alert">
            <p>No hay personajes disponibles.</p>
            <p className="holo-cargando-detalle">
              Pide a un adulto que cree alguno desde la configuración (⚙️).
            </p>
          </section>
        ) : (
          // key por el conjunto de ids: si un catálogo cambia (alta/baja de
          // personaje o ubicación), el flujo se reinicia limpio; si no, conserva el progreso.
          <Asistente
            key={[...personajes.map((p) => p.id), "|", ...ubicaciones.map((u) => u.id)].join(",")}
            personajes={personajes}
            ubicaciones={ubicaciones}
          />
        )}

        {/* Scanlines CRT: dentro de .holo-wrap (mismo contexto de apilado que
            el contenido) para que la imagen generada pueda quedar por encima. */}
        <div className="crt-scan" aria-hidden="true" />
      </main>
    </>
  );
}

/**
 * Asistente — el flujo del niño en 3 pasos. Solo se monta con los catálogos ya
 * cargados, así useFlow siempre recibe una lista no vacía de personajes.
 */
function Asistente({
  personajes,
  ubicaciones,
}: {
  personajes: PersonajeDTO[];
  ubicaciones: UbicacionDTO[];
}) {
  const flow = useFlow(personajes, ubicaciones);
  const { estado, ubicacionLista, nombreLugar } = flow;
  const { paso } = estado;

  const porId = Object.fromEntries(personajes.map((p) => [p.id, p]));
  const personaje = porId[estado.personajeId];

  return (
    <>
      <Steps pasoActivo={paso} />

      {paso === 1 && (
        <CharacterSelect
          personajes={personajes}
          index={estado.personajeIdx}
          onMove={flow.moverPersonaje}
          onNext={() => flow.irPaso(2)}
        />
      )}

      {paso === 2 && (
        <PlaceSelect
          ubicaciones={ubicaciones}
          index={estado.ubicacionIdx}
          fotoFile={estado.fotoFile}
          ubicacionLista={ubicacionLista}
          onMove={flow.moverLugar}
          onElegirFoto={flow.elegirFoto}
          onNext={flow.confirmarLugar}
          onBack={() => flow.irPaso(1)}
        />
      )}

      {paso === 3 && personaje && (
        <SceneChat
          cargando={estado.cargando}
          error={estado.error}
          escenaBase64={estado.escenaBase64}
          chatKey={estado.generadoPara ?? estado.personajeId}
          personajeId={estado.personajeId}
          personajeNombre={personaje.nombre}
          personajeEmoji={personaje.emoji ?? "🎭"}
          nombreLugar={nombreLugar()}
          onReintentar={() =>
            estado.ubicacionId &&
            flow.generarEscena(estado.personajeId, estado.ubicacionId, estado.fotoFile)
          }
          onCambiarLugar={() => flow.irPaso(2)}
          onReiniciar={flow.reiniciar}
        />
      )}
    </>
  );
}
