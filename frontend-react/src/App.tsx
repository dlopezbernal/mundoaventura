/**
 * App.tsx — Orquestador del asistente "Arcade Holo"
 * ==================================================
 *
 * Monta el armazón visual (fondo animado + HUD + línea de pasos) y, según el
 * paso actual de la máquina de estados (useFlow), muestra una de las tres
 * pantallas: elegir personaje → elegir mundo → escena + chat.
 *
 * Toda la lógica del flujo vive en state/useFlow.ts; aquí sólo se conecta el
 * estado con las pantallas presentacionales.
 */

import { useState } from "react";
import Background from "./components/Background/Background";
import Hud from "./components/Hud/Hud";
import Steps from "./components/Steps/Steps";
import CharacterSelect from "./screens/CharacterSelect";
import PlaceSelect from "./screens/PlaceSelect";
import SceneChat from "./screens/SceneChat";
import Settings from "./screens/Settings";
import { checkHealth } from "./api/client";
import { PERSONAJES } from "./data/personajes";
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
  const flow = useFlow();
  const { estado, ubicacionLista, nombreLugar } = flow;
  const { paso } = estado;
  const personaje = PERSONAJES[estado.personajeId];

  // Página de configuración: se abre desde el botón ⚙️ del HUD y sustituye al
  // flujo principal mientras está activa.
  const [mostrarConfig, setMostrarConfig] = useState(false);

  return (
    <>
      <Background />
      <main className="holo-wrap">
        <Hud
          onAbrirConfig={() => setMostrarConfig(true)}
          onProbarConexion={DEBUG ? probarConexion : undefined}
        />

        {mostrarConfig ? (
          <Settings onCerrar={() => setMostrarConfig(false)} />
        ) : (
          <>
        <Steps pasoActivo={paso} />

        {paso === 1 && (
          <CharacterSelect
            index={estado.personajeIdx}
            onMove={flow.moverPersonaje}
            onNext={() => flow.irPaso(2)}
          />
        )}

        {paso === 2 && (
          <PlaceSelect
            index={estado.ubicacionIdx}
            fotoFile={estado.fotoFile}
            ubicacionLista={ubicacionLista}
            onMove={flow.moverLugar}
            onElegirFoto={flow.elegirFoto}
            onNext={flow.confirmarLugar}
            onBack={() => flow.irPaso(1)}
          />
        )}

        {paso === 3 && (
          <SceneChat
            cargando={estado.cargando}
            error={estado.error}
            escenaBase64={estado.escenaBase64}
            chatKey={estado.generadoPara ?? estado.personajeId}
            personajeId={estado.personajeId}
            personajeNombre={personaje.label}
            personajeEmoji={personaje.emoji}
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
        )}

        {/* Scanlines CRT: dentro de .holo-wrap (mismo contexto de apilado que
            el contenido) para que la imagen generada pueda quedar por encima. */}
        <div className="crt-scan" aria-hidden="true" />
      </main>
    </>
  );
}
