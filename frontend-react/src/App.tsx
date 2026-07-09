/**
 * App.tsx — Asistente por pasos (Hito 2)
 * =======================================
 *
 * Replica el flujo guiado de legacy/frontend-flet/main.py:
 *
 *   Paso 1 → Elegir CON QUIÉN hablar (personaje, agrupado por categorías).
 *   Paso 2 → Elegir un LUGAR (o subir "Mi foto", id especial "__foto__").
 *   Paso 3 → Escena generada (el chat con el personaje llega en el Hito 3).
 *
 * Todo el estado del asistente vive aquí, en un useReducer; los componentes
 * (StepBar, CardCarousel, SceneView) son presentacionales.
 */

import { useReducer, useRef } from "react";
import { BackendError, checkHealth, generate, generateOnPhoto } from "./api/client";
import { GRUPOS, PERSONAJES, personajesDeGrupo } from "./data/personajes";
import { UBICACIONES } from "./data/ubicaciones";
import CardCarousel, { type Carta } from "./components/CardCarousel";
import SceneView from "./components/SceneView";
import StepBar from "./components/StepBar";
import "./App.css";

/** Id especial (no es una ubicación real) para el modo "Usar mi foto". */
const FOTO_ID = "__foto__";

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
  personajeId: string | null;
  ubicacionId: string | null; // ubicación real o FOTO_ID
  fotoFile: File | null; // la foto subida (solo en modo FOTO_ID)
  escenaBase64: string | null; // última escena generada
  generadoPara: string | null; // clave de la selección de esa escena (evita regenerar)
  cargando: boolean;
  error: string | null;
}

const ESTADO_INICIAL: Estado = {
  paso: 1,
  personajeId: null,
  ubicacionId: null,
  fotoFile: null,
  escenaBase64: null,
  generadoPara: null,
  cargando: false,
  error: null,
};

type Accion =
  | { type: "ELEGIR_PERSONAJE"; id: string }
  | { type: "ELEGIR_UBICACION"; id: string }
  | { type: "ELEGIR_FOTO"; file: File }
  | { type: "IR_PASO"; paso: 1 | 2 | 3 }
  | { type: "GENERANDO" }
  | { type: "ESCENA_OK"; base64: string; clave: string }
  | { type: "ESCENA_ERROR"; mensaje: string }
  | { type: "REINICIAR" };

function reducer(estado: Estado, accion: Accion): Estado {
  switch (accion.type) {
    case "ELEGIR_PERSONAJE":
      return { ...estado, personajeId: accion.id };
    case "ELEGIR_UBICACION":
      // Elegir un lugar real saca del modo foto (como en la app Flet).
      return { ...estado, ubicacionId: accion.id, fotoFile: null };
    case "ELEGIR_FOTO":
      return { ...estado, ubicacionId: FOTO_ID, fotoFile: accion.file };
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

  const { paso, personajeId, ubicacionId, fotoFile } = estado;
  const personaje = personajeId ? PERSONAJES[personajeId] : null;

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
    }
  }

  /** Confirmar el paso 2: reutiliza la escena si la selección no cambió. */
  function confirmarLugar() {
    if (!personajeId || !ubicacionId || !ubicacionLista) return;
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

  function onElegirLugar(id: string) {
    if (id === FOTO_ID) {
      // "Mi foto" abre el selector (también para cambiar la foto ya elegida).
      fotoInputRef.current?.click();
    } else {
      dispatch({ type: "ELEGIR_UBICACION", id });
    }
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

  // -- Cartas de cada paso -----------------------------------------------------

  const cartasLugar: Carta[] = [
    {
      id: FOTO_ID,
      emoji: "📷",
      label: ubicacionId === FOTO_ID && fotoFile ? "✓ ¡Foto lista!" : "Mi foto",
      sub: "Tu cuarto",
    },
    ...Object.entries(UBICACIONES).map(([id, datos]) => ({
      id,
      emoji: datos.emoji,
      label: datos.label,
    })),
  ];

  // -- Acciones de la cabecera (mismo patrón que la app Flet) ------------------

  const acciones: React.ReactNode[] = [];
  if (paso === 1) {
    acciones.push(
      <button
        key="siguiente"
        type="button"
        className="btn-header"
        disabled={!personajeId}
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
          {Object.entries(GRUPOS).map(([titulo, categorias]) => (
            <div key={titulo} className="grupo">
              <h3 className="grupo-titulo">{titulo}</h3>
              <CardCarousel
                cartas={personajesDeGrupo(categorias).map(([id, datos]) => ({
                  id,
                  emoji: datos.emoji,
                  label: datos.label,
                  sub: CATEGORIA_LABEL[datos.categoria],
                }))}
                seleccionadaId={personajeId}
                onElegir={(id) => dispatch({ type: "ELEGIR_PERSONAJE", id })}
              />
            </div>
          ))}
        </section>
      )}

      {paso === 2 && (
        <section className="panel-paso panel-lugar">
          <h2>🗺️ Selecciona un lugar</h2>
          <CardCarousel
            cartas={cartasLugar}
            seleccionadaId={ubicacionLista ? ubicacionId : null}
            onElegir={onElegirLugar}
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
                    personajeId &&
                    ubicacionId &&
                    generarEscena(personajeId, ubicacionId, fotoFile)
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

          {!estado.cargando && !estado.error && estado.escenaBase64 && personaje && (
            <SceneView
              escenaBase64={estado.escenaBase64}
              alt={`Escena de ${personaje.label} en ${nombreLugar()}`}
              caption={`${personaje.emoji}  ${personaje.label} · ${nombreLugar()}`}
              onEmpezarDeNuevo={() => dispatch({ type: "REINICIAR" })}
              onCambiarLugar={() => dispatch({ type: "IR_PASO", paso: 2 })}
            />
          )}
        </section>
      )}
    </main>
  );
}

export default App;
