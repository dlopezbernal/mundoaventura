/**
 * App.tsx — Asistente por pasos
 * ==============================
 *
 * Replica el flujo guiado de legacy/frontend-flet/main.py:
 *
 *   Paso 1 → Elegir CON QUIÉN hablar (carrusel de personajes).
 *   Paso 2 → Elegir un LUGAR (carrusel: "Mi foto" primero, id "__foto__").
 *   Paso 3 → Escena generada + chat con el personaje.
 *
 * Como en Flet, la carta CENTRADA del carrusel queda autoseleccionada: para
 * una ubicación real basta con centrarla; "Mi foto" necesita además un archivo.
 *
 * Todo el estado del asistente vive aquí, en un useReducer; los componentes
 * (StepBar, CardCarousel, SceneView, Chat) son presentacionales.
 */

import { useReducer, useRef } from "react";
import { BackendError, checkHealth, generate, generateOnPhoto } from "./api/client";
import { GRUPOS, PERSONAJES } from "./data/personajes";
import { UBICACIONES } from "./data/ubicaciones";
import CardCarousel, { type Carta } from "./components/CardCarousel";
import Chat from "./components/Chat";
import SceneView from "./components/SceneView";
import StepBar from "./components/StepBar";
import "./App.css";

/** Id especial (no es una ubicación real) para el modo "Usar mi foto". */
const FOTO_ID = "__foto__";

/** Catálogos como listas ordenadas para los carruseles (con vuelta circular). */
const PERSONAJE_KEYS = Object.keys(PERSONAJES);
const LUGAR_KEYS = [FOTO_ID, ...Object.keys(UBICACIONES)]; // "Mi foto" SIEMPRE primero

/** Mapa inverso categoría -> título de grupo legible ("prehistorico" -> "Prehistóricos"). */
const CATEGORIA_LABEL: Record<string, string> = Object.fromEntries(
  Object.entries(GRUPOS).flatMap(([titulo, cats]) => cats.map((c) => [c, titulo])),
);

// Modo desarrollo: muestra el botón "Probar conexión" en la cabecera (como el
// DEBUG de la app Flet). En la build para el niño no se define y desaparece.
const DEBUG = import.meta.env.VITE_DEBUG === "true";

// ---------------------------------------------------------------------------
// Estado del asistente (useReducer)
// ---------------------------------------------------------------------------

interface Estado {
  paso: 1 | 2 | 3;
  personajeIdx: number; // carta centrada en el carrusel de personajes
  ubicacionIdx: number; // carta centrada en el carrusel de lugares
  personajeId: string; // autoseleccionado: siempre el de la carta central
  ubicacionId: string | null; // ubicación real, FOTO_ID (con foto) o null
  fotoFile: File | null; // la foto subida (solo en modo FOTO_ID)
  escenaBase64: string | null; // última escena generada
  generadoPara: string | null; // clave de la selección de esa escena (evita regenerar)
  cargando: boolean;
  error: string | null;
}

const ESTADO_INICIAL: Estado = {
  paso: 1,
  personajeIdx: 0,
  ubicacionIdx: 0,
  personajeId: PERSONAJE_KEYS[0],
  ubicacionId: null, // la primera carta es "Mi foto", que sin archivo no selecciona
  fotoFile: null,
  escenaBase64: null,
  generadoPara: null,
  cargando: false,
  error: null,
};

type Accion =
  | { type: "MOVER_PERSONAJE"; delta: number }
  | { type: "MOVER_LUGAR"; delta: number }
  | { type: "ELEGIR_FOTO"; file: File }
  | { type: "IR_PASO"; paso: 1 | 2 | 3 }
  | { type: "GENERANDO" }
  | { type: "ESCENA_OK"; base64: string; clave: string }
  | { type: "ESCENA_ERROR"; mensaje: string }
  | { type: "REINICIAR" };

function reducer(estado: Estado, accion: Accion): Estado {
  switch (accion.type) {
    case "MOVER_PERSONAJE": {
      const n = PERSONAJE_KEYS.length;
      const idx = (((estado.personajeIdx + accion.delta) % n) + n) % n;
      return { ...estado, personajeIdx: idx, personajeId: PERSONAJE_KEYS[idx] };
    }
    case "MOVER_LUGAR": {
      const n = LUGAR_KEYS.length;
      const idx = (((estado.ubicacionIdx + accion.delta) % n) + n) % n;
      const key = LUGAR_KEYS[idx];
      if (key === FOTO_ID) {
        // "Mi foto" solo queda seleccionada si ya hay un archivo elegido.
        return {
          ...estado,
          ubicacionIdx: idx,
          ubicacionId: estado.fotoFile ? FOTO_ID : null,
        };
      }
      // Centrar una ubicación real la autoselecciona y sale del modo foto.
      return { ...estado, ubicacionIdx: idx, ubicacionId: key, fotoFile: null };
    }
    case "ELEGIR_FOTO":
      return {
        ...estado,
        ubicacionIdx: 0, // "Mi foto" es la primera carta del carrusel
        ubicacionId: FOTO_ID,
        fotoFile: accion.file,
      };
    case "IR_PASO":
      return { ...estado, paso: accion.paso, error: null };
    case "GENERANDO":
      return { ...estado, paso: 3, cargando: true, error: null, escenaBase64: null };
    case "ESCENA_OK":
      return {
        ...estado,
        cargando: false,
        escenaBase64: accion.base64,
        generadoPara: accion.clave,
      };
    case "ESCENA_ERROR":
      return { ...estado, cargando: false, error: accion.mensaje };
    case "REINICIAR":
      return ESTADO_INICIAL;
  }
}

/** Clave que identifica una selección completa; si no cambia, no se regenera. */
function claveSeleccion(pid: string, uid: string, foto: File | null): string {
  return `${pid}|${uid}|${foto ? `${foto.name}:${foto.lastModified}` : ""}`;
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

function App() {
  const [estado, dispatch] = useReducer(reducer, ESTADO_INICIAL);
  const fotoInputRef = useRef<HTMLInputElement>(null);
  // Guard anti doble clic: evita lanzar dos generaciones (dos cobros) seguidas.
  const generandoRef = useRef(false);

  const { paso, personajeId, ubicacionId, fotoFile } = estado;
  const personaje = PERSONAJES[personajeId];

  // ¿Hay una selección de lugar válida? (un lugar real, o "Mi foto" CON archivo)
  const ubicacionLista =
    ubicacionId !== null && (ubicacionId !== FOTO_ID || fotoFile !== null);

  function nombreLugar(): string {
    if (ubicacionId === FOTO_ID) return "tu foto";
    if (ubicacionId) return UBICACIONES[ubicacionId].label;
    return "";
  }

  // -- Generación de la escena ----------------------------------------------

  async function generarEscena(pid: string, uid: string, foto: File | null) {
    if (generandoRef.current) return; // ya hay una generación en vuelo
    generandoRef.current = true;
    dispatch({ type: "GENERANDO" });
    try {
      const resultado =
        uid === FOTO_ID
          ? await generateOnPhoto(foto as File, pid)
          : await generate(uid, pid);
      dispatch({
        type: "ESCENA_OK",
        base64: resultado.result_png_base64,
        clave: claveSeleccion(pid, uid, foto),
      });
    } catch (exc) {
      const mensaje =
        exc instanceof BackendError
          ? exc.message
          : "Algo no ha ido bien creando tu escena. Inténtalo otra vez.";
      dispatch({ type: "ESCENA_ERROR", mensaje });
    } finally {
      generandoRef.current = false;
    }
  }

  /** Confirmar el paso 2: reutiliza la escena si la selección no cambió. */
  function confirmarLugar() {
    if (!ubicacionId || !ubicacionLista) return;
    const clave = claveSeleccion(personajeId, ubicacionId, fotoFile);
    if (clave === estado.generadoPara && estado.escenaBase64) {
      dispatch({ type: "IR_PASO", paso: 3 }); // esa escena ya está hecha
      return;
    }
    void generarEscena(personajeId, ubicacionId, fotoFile);
  }

  // -- Selección de foto ------------------------------------------------------

  function onFotoElegida(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      dispatch({ type: "ELEGIR_FOTO", file });
    }
    // Permite volver a elegir el mismo archivo más tarde.
    event.target.value = "";
  }

  /** Clic en la carta central del carrusel de lugares (como en Flet):
   *  "Mi foto" sin archivo abre el selector; con selección válida, avanza. */
  function onCentroLugar() {
    const key = LUGAR_KEYS[estado.ubicacionIdx];
    if (key === FOTO_ID && !fotoFile) {
      fotoInputRef.current?.click();
      return;
    }
    confirmarLugar();
  }

  // -- Diagnóstico (solo DEBUG) ----------------------------------------------

  async function probarConexion() {
    try {
      const info = await checkHealth();
      window.alert(`✅ Backend OK\n${JSON.stringify(info, null, 2)}`);
    } catch (exc) {
      window.alert(`❌ ${exc instanceof Error ? exc.message : String(exc)}`);
    }
  }

  // -- Cartas de cada carrusel --------------------------------------------------

  const cartasPersonaje: Carta[] = PERSONAJE_KEYS.map((id) => ({
    id,
    emoji: PERSONAJES[id].emoji,
    label: PERSONAJES[id].label,
    sub: CATEGORIA_LABEL[PERSONAJES[id].categoria],
  }));

  const cartasLugar: Carta[] = LUGAR_KEYS.map((id) => {
    if (id === FOTO_ID) {
      return {
        id,
        emoji: "📷",
        label: ubicacionId === FOTO_ID && fotoFile ? "✓ ¡Foto lista!" : "Mi foto",
        sub: "Tu cuarto",
      };
    }
    return { id, emoji: UBICACIONES[id].emoji, label: UBICACIONES[id].label };
  });

  // -- Acciones de la cabecera (mismo patrón que la app Flet) ------------------

  const acciones: React.ReactNode[] = [];
  if (paso === 1) {
    acciones.push(
      <button
        key="siguiente"
        type="button"
        className="btn-header"
        onClick={() => dispatch({ type: "IR_PASO", paso: 2 })}
      >
        Siguiente →
      </button>,
    );
  } else if (paso === 2) {
    acciones.push(
      <button
        key="atras"
        type="button"
        className="btn-header"
        onClick={() => dispatch({ type: "IR_PASO", paso: 1 })}
      >
        ← Atrás
      </button>,
      <button
        key="siguiente"
        type="button"
        className="btn-header"
        disabled={!ubicacionLista}
        onClick={confirmarLugar}
      >
        Siguiente →
      </button>,
    );
  } else {
    acciones.push(
      <button
        key="atras"
        type="button"
        className="btn-header"
        disabled={estado.cargando}
        onClick={() => dispatch({ type: "IR_PASO", paso: 2 })}
      >
        ← Atrás
      </button>,
    );
  }

  // -- Render -----------------------------------------------------------------

  return (
    <main className="app">
      <header className="cabecera">
        <div className="cabecera-titulo">
          <h1>🕰️ Máquina del Tiempo</h1>
          <p>¡Viaja sin salir de tu cuarto!</p>
        </div>
        <div className="cabecera-acciones">
          {acciones}
          {DEBUG && (
            <button type="button" className="btn-header" onClick={probarConexion}>
              🔌 Probar conexión
            </button>
          )}
        </div>
      </header>

      <StepBar pasoActivo={paso} />

      {paso === 1 && (
        <section className="panel-paso panel-personaje">
          <h2>🎭 ¿Con quién quieres hablar?</h2>
          <CardCarousel
            cartas={cartasPersonaje}
            idx={estado.personajeIdx}
            seleccionadaCentral /* la carta central siempre es el elegido */
            accent="morado"
            etiqueta="Elige un personaje"
            onMover={(delta) => dispatch({ type: "MOVER_PERSONAJE", delta })}
            onCentro={() => dispatch({ type: "IR_PASO", paso: 2 })}
          />
        </section>
      )}

      {paso === 2 && (
        <section className="panel-paso panel-lugar">
          <h2>🗺️ Selecciona un lugar</h2>
          <CardCarousel
            cartas={cartasLugar}
            idx={estado.ubicacionIdx}
            seleccionadaCentral={ubicacionLista}
            accent="turquesa"
            etiqueta="Elige un lugar"
            onMover={(delta) => dispatch({ type: "MOVER_LUGAR", delta })}
            onCentro={onCentroLugar}
          />
          <p className="pista">📷 Si usas tu foto, ¡saca tu cuarto vacío! 😊</p>
          {/* Selector de foto oculto: lo abre la carta "Mi foto". */}
          <input
            ref={fotoInputRef}
            type="file"
            accept="image/png,image/jpeg,image/bmp,image/webp"
            hidden
            onChange={onFotoElegida}
          />
        </section>
      )}

      {paso === 3 && (
        <section className="panel-paso panel-escena">
          {estado.cargando && (
            <div className="loading-panel" role="status">
              <span className="loading-emoji" aria-hidden="true">
                🎨
              </span>
              <p className="loading-text">Creando tu escena</p>
              <div className="loading-bar" aria-hidden="true" />
            </div>
          )}

          {!estado.cargando && estado.error && (
            <div className="error-panel">
              <p>😢 {estado.error}</p>
              <div className="error-botones">
                <button
                  type="button"
                  className="btn btn-primario"
                  onClick={() =>
                    ubicacionId && generarEscena(personajeId, ubicacionId, fotoFile)
                  }
                >
                  🔁 Reintentar
                </button>
                <button
                  type="button"
                  className="btn btn-secundario"
                  onClick={() => dispatch({ type: "IR_PASO", paso: 2 })}
                >
                  ← Elegir otro lugar
                </button>
              </div>
            </div>
          )}

          {!estado.cargando && !estado.error && estado.escenaBase64 && (
            <div className="escena-y-chat">
              <SceneView
                escenaBase64={estado.escenaBase64}
                alt={`Escena de ${personaje.label} en ${nombreLugar()}`}
                caption={`${personaje.emoji}  ${personaje.label} · ${nombreLugar()}`}
                onEmpezarDeNuevo={() => dispatch({ type: "REINICIAR" })}
                onCambiarLugar={() => dispatch({ type: "IR_PASO", paso: 2 })}
              />
              {/* key: al generar una escena nueva, el chat empieza de cero. */}
              <Chat
                key={estado.generadoPara ?? personajeId}
                personajeId={personajeId}
                nombre={personaje.label}
                emoji={personaje.emoji}
              />
            </div>
          )}
        </section>
      )}
    </main>
  );
}

export default App;
