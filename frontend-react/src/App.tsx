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
import Manual from "./screens/Manual";
import QuienJuega from "./screens/QuienJuega";
import {
  BackendError,
  familiaLogout,
  familiaMe,
  getPersonajes,
  getUbicaciones,
} from "./api/client";
import type { FamiliaDTO, NinoDTO, PersonajeDTO, UbicacionDTO } from "./api/types";
import { useFlow } from "./state/useFlow";

// Niño con perfil activo, recordado en el dispositivo (Hito 9.2c).
const NINO_KEY = "mdt_nino_activo";
function guardarNinoActivo(nino: string | null) {
  try {
    if (nino) localStorage.setItem(NINO_KEY, nino);
    else localStorage.removeItem(NINO_KEY);
  } catch {
    /* localStorage puede no estar disponible */
  }
}

export default function App() {
  // Sesión de familia (Hito 9.2): la app va detrás del login de familia.
  // undefined = comprobando todavía; null = sin sesión (mostrar login).
  const [familia, setFamilia] = useState<FamiliaDTO | null | undefined>(undefined);
  // Niño con perfil activo (multi-perfil, H9.2c). null = aún sin elegir.
  const [ninoActivo, setNinoActivo] = useState<NinoDTO | null>(null);
  // Catálogos cargados por API: null = cargando todavía.
  const [personajes, setPersonajes] = useState<PersonajeDTO[] | null>(null);
  const [ubicaciones, setUbicaciones] = useState<UbicacionDTO[] | null>(null);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  // Pantallas de adulto: sustituyen al flujo principal mientras están activas.
  // Configuración (⚙️) = gestionar el PIN; Admin (🛡️) = config global (H9.2).
  const [mostrarConfig, setMostrarConfig] = useState(false);
  const [mostrarAdmin, setMostrarAdmin] = useState(false);
  // Manual de usuario: se abre desde el HUD y TAMBIÉN desde el login (para poder
  // leerlo antes de dar el correo y crear la cuenta), así que vive aquí, fuera de
  // las dos ramas de render.
  const [mostrarManual, setMostrarManual] = useState(false);

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

  // Reconcilia el niño activo con la familia: recupera el recordado (por nombre) si
  // sigue existiendo, autoselecciona cuando hay uno solo, y lo limpia si ya no está.
  useEffect(() => {
    if (!familia) return;
    setNinoActivo((actual) => {
      const nombre = actual?.nombre ?? localStorage.getItem(NINO_KEY);
      const encontrado = nombre ? familia.ninos.find((n) => n.nombre === nombre) : undefined;
      if (encontrado) return encontrado;
      if (familia.ninos.length === 1) return familia.ninos[0];
      return null; // 0 niños, o varios sin selección válida (→ "¿quién juega?")
    });
  }, [familia]);

  /** Elige (o deselecciona) el niño que juega y lo recuerda en el dispositivo. */
  function elegirNino(nino: NinoDTO | null) {
    setNinoActivo(nino);
    guardarNinoActivo(nino?.nombre ?? null);
  }

  /** Al cerrar Admin, recargamos los catálogos (pudieron cambiar) y volvemos al flujo. */
  function cerrarAdmin() {
    setMostrarAdmin(false);
    void cargarCatalogos();
  }

  /** Limpia el estado y vuelve a la pantalla de login (sin tocar el backend). */
  function volverAlLogin() {
    setMostrarAdmin(false);
    setMostrarConfig(false);
    setMostrarManual(false);
    setPersonajes(null);
    setUbicaciones(null);
    elegirNino(null);
    setFamilia(null);
  }

  /** Cierra la sesión de familia (invalida el token en el backend) y vuelve al login. */
  async function salirFamilia() {
    await familiaLogout();
    volverAlLogin();
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
  // El manual sí es accesible desde aquí: el adulto debe poder saber qué es la app
  // ANTES de registrar su correo.
  if (familia === null) {
    return (
      <>
        <Background />
        <main className="holo-wrap">
          {mostrarManual ? (
            <Manual onCerrar={() => setMostrarManual(false)} />
          ) : (
            <LoginFamilia onListo={setFamilia} onAbrirManual={() => setMostrarManual(true)} />
          )}
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
          ninoActivo={ninoActivo?.nombre ?? null}
          onCambiarNino={familia.ninos.length > 1 ? () => elegirNino(null) : undefined}
          // Abrir una pantalla de adulto CIERRA la otra: si no, al alternar entre los
          // botones del HUD, Admin (que tiene prioridad en el render) se quedaba "clavado".
          onAbrirManual={() => {
            setMostrarAdmin(false);
            setMostrarConfig(false);
            setMostrarManual(true);
          }}
          onAbrirConfig={() => {
            setMostrarAdmin(false);
            setMostrarManual(false);
            setMostrarConfig(true);
          }}
          onAbrirAdmin={() => {
            setMostrarConfig(false);
            setMostrarManual(false);
            setMostrarAdmin(true);
          }}
          onSalir={() => void salirFamilia()}
        />

        {mostrarManual ? (
          <Manual onCerrar={() => setMostrarManual(false)} />
        ) : mostrarAdmin ? (
          <Admin onCerrar={cerrarAdmin} />
        ) : mostrarConfig ? (
          <Configuracion
            familia={familia}
            onActualizado={setFamilia}
            onCuentaEliminada={volverAlLogin}
            onCerrar={() => setMostrarConfig(false)}
          />
        ) : familia.ninos.length > 1 && ninoActivo === null ? (
          <QuienJuega
            nombreFamilia={familia.nombre_familia}
            ninos={familia.ninos}
            onElegir={elegirNino}
            onGestionar={() => setMostrarConfig(true)}
          />
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
            ninoActivo={ninoActivo}
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
  ninoActivo,
}: {
  personajes: PersonajeDTO[];
  ubicaciones: UbicacionDTO[];
  ninoActivo: NinoDTO | null;
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
          nombreNino={ninoActivo?.nombre ?? null}
          sexoNino={ninoActivo?.sexo ?? null}
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
