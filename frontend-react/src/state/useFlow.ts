/**
 * state/useFlow.ts — Máquina de estados del asistente (3 pasos)
 * =============================================================
 *
 * Gobierna el flujo personaje → mundo → escena+chat. Es la misma lógica que
 * antes vivía en App.tsx (useReducer), extraída aquí para que las pantallas
 * (screens/) sean puramente presentacionales.
 *
 * La carta CENTRAL del carrusel queda autoseleccionada: para un lugar real
 * basta con centrarlo; "Mi foto" (id __foto__) necesita además un archivo.
 * Guarda un guard anti doble generación (evita dos cobros seguidos) y reutiliza
 * la escena si la selección no cambió.
 */

import { useMemo, useReducer, useRef } from "react";
import { BackendError, generate, generateOnPhoto } from "../api/client";
import type { PersonajeDTO, UbicacionDTO } from "../api/types";

/** Id especial (no es una ubicación real) para el modo "Usar mi foto". */
export const FOTO_ID = "__foto__";

interface Estado {
  paso: 1 | 2 | 3;
  personajeIdx: number;
  ubicacionIdx: number;
  personajeId: string;
  ubicacionId: string | null; // ubicación real, FOTO_ID (con foto) o null
  fotoFile: File | null;
  escenaBase64: string | null;
  generadoPara: string | null; // clave de la selección de esa escena
  cargando: boolean;
  error: string | null;
}

/** Estado inicial (el personaje 0 del catálogo recibido queda autoseleccionado). */
function estadoInicial(personajeKeys: string[]): Estado {
  return {
    paso: 1,
    personajeIdx: 0,
    ubicacionIdx: 0,
    personajeId: personajeKeys[0],
    ubicacionId: null,
    fotoFile: null,
    escenaBase64: null,
    generadoPara: null,
    cargando: false,
    error: null,
  };
}

type Accion =
  | { type: "MOVER_PERSONAJE"; delta: number }
  | { type: "MOVER_LUGAR"; delta: number }
  | { type: "ELEGIR_FOTO"; file: File }
  | { type: "IR_PASO"; paso: 1 | 2 | 3 }
  | { type: "GENERANDO"; clave: string }
  | { type: "ESCENA_OK"; base64: string }
  | { type: "ESCENA_ERROR"; mensaje: string }
  | { type: "REINICIAR" };

/**
 * Fábrica del reducer: recibe las claves de los catálogos (que ahora llegan por
 * API, no de módulos estáticos) y devuelve el reducer que las usa para los
 * carruseles de personaje y de lugar.
 */
function crearReducer(personajeKeys: string[], lugarKeys: string[]) {
  return function reducer(estado: Estado, accion: Accion): Estado {
  switch (accion.type) {
    case "MOVER_PERSONAJE": {
      const n = personajeKeys.length;
      const idx = (((estado.personajeIdx + accion.delta) % n) + n) % n;
      return { ...estado, personajeIdx: idx, personajeId: personajeKeys[idx] };
    }
    case "MOVER_LUGAR": {
      const n = lugarKeys.length;
      const idx = (((estado.ubicacionIdx + accion.delta) % n) + n) % n;
      const key = lugarKeys[idx];
      if (key === FOTO_ID) {
        // "Mi foto" sólo queda seleccionada si ya hay un archivo elegido.
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
        ubicacionIdx: 0, // "Mi foto" es la primera carta
        ubicacionId: FOTO_ID,
        fotoFile: accion.file,
      };
    case "IR_PASO":
      return { ...estado, paso: accion.paso, error: null };
    case "GENERANDO":
      // Fijamos ya la clave del chat (generadoPara): el chat se monta a la vez
      // que arranca la generación, y esta clave estable evita que se remonte
      // (perdiendo la conversación) cuando la imagen llegue con ESCENA_OK.
      return {
        ...estado,
        paso: 3,
        cargando: true,
        error: null,
        escenaBase64: null,
        generadoPara: accion.clave,
      };
    case "ESCENA_OK":
      return { ...estado, cargando: false, escenaBase64: accion.base64 };
    case "ESCENA_ERROR":
      return { ...estado, cargando: false, error: accion.mensaje };
    case "REINICIAR":
      return estadoInicial(personajeKeys);
  }
  };
}

/** Clave que identifica una selección completa; si no cambia, no se regenera. */
function claveSeleccion(pid: string, uid: string, foto: File | null): string {
  return `${pid}|${uid}|${foto ? `${foto.name}:${foto.lastModified}` : ""}`;
}

/**
 * Máquina de estados del asistente. Recibe los CATÁLOGOS de personajes y de
 * ubicaciones (cargados por API en App), de los que salen las claves de los
 * carruseles, el personaje inicial y el nombre del lugar elegido.
 */
export function useFlow(personajes: PersonajeDTO[], ubicaciones: UbicacionDTO[]) {
  const personajeKeys = useMemo(() => personajes.map((p) => p.id), [personajes]);
  // "Mi foto" va primera, luego las ubicaciones del catálogo.
  const lugarKeys = useMemo(() => [FOTO_ID, ...ubicaciones.map((u) => u.id)], [ubicaciones]);
  // Nombre visible por id de ubicación (para el mensaje "MUNDO FIJADO: …").
  const nombrePorLugar = useMemo(
    () => Object.fromEntries(ubicaciones.map((u) => [u.id, u.nombre])),
    [ubicaciones],
  );
  const reducer = useMemo(
    () => crearReducer(personajeKeys, lugarKeys),
    [personajeKeys, lugarKeys],
  );
  const [estado, dispatch] = useReducer(reducer, personajeKeys, estadoInicial);
  // Guard anti doble clic: evita lanzar dos generaciones (dos cobros) seguidas.
  const generandoRef = useRef(false);

  const { personajeId, ubicacionId, fotoFile } = estado;

  /** ¿Hay una selección de lugar válida? (un lugar real, o "Mi foto" CON foto) */
  const ubicacionLista =
    ubicacionId !== null && (ubicacionId !== FOTO_ID || fotoFile !== null);

  function nombreLugar(): string {
    if (ubicacionId === FOTO_ID) return "tu foto";
    if (ubicacionId) return nombrePorLugar[ubicacionId] ?? "";
    return "";
  }

  async function generarEscena(pid: string, uid: string, foto: File | null) {
    if (generandoRef.current) return; // ya hay una generación en vuelo
    generandoRef.current = true;
    dispatch({ type: "GENERANDO", clave: claveSeleccion(pid, uid, foto) });
    try {
      const resultado =
        uid === FOTO_ID
          ? await generateOnPhoto(foto as File, pid)
          : await generate(uid, pid);
      dispatch({ type: "ESCENA_OK", base64: resultado.result_png_base64 });
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

  return {
    estado,
    ubicacionLista,
    nombreLugar,
    // acciones
    moverPersonaje: (delta: number) => dispatch({ type: "MOVER_PERSONAJE", delta }),
    moverLugar: (delta: number) => dispatch({ type: "MOVER_LUGAR", delta }),
    elegirFoto: (file: File) => dispatch({ type: "ELEGIR_FOTO", file }),
    irPaso: (paso: 1 | 2 | 3) => dispatch({ type: "IR_PASO", paso }),
    reiniciar: () => dispatch({ type: "REINICIAR" }),
    confirmarLugar,
    generarEscena,
  };
}
