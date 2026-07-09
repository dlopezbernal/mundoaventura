/**
 * App.tsx — Página mínima del Hito 1
 * ===================================
 *
 * Solo comprueba que el esqueleto funciona: título del proyecto y un botón
 * "Probar conexión" que llama a checkHealth() y pinta el JSON o el error.
 * El asistente por pasos (personaje → ubicación → escena) llega en el Hito 2.
 */

import { useState } from "react";
import { checkHealth } from "./api/client";
import "./App.css";

function App() {
  const [resultado, setResultado] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  async function probarConexion() {
    setCargando(true);
    setResultado("");
    setError("");
    try {
      const health = await checkHealth();
      setResultado(JSON.stringify(health, null, 2));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setCargando(false);
    }
  }

  return (
    <main className="app">
      <h1>🕰️ Máquina del Tiempo</h1>
      <p>Migración a React — Hito 1: esqueleto y conexión con el backend.</p>

      <button type="button" onClick={probarConexion} disabled={cargando}>
        {cargando ? "Conectando..." : "Probar conexión"}
      </button>

      {resultado && <pre className="resultado">{resultado}</pre>}
      {error && <p className="error">{error}</p>}
    </main>
  );
}

export default App;
