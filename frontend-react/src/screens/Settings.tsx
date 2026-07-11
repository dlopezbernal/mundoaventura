/**
 * Settings — Página de configuración de la aplicación
 * ====================================================
 *
 * Plantilla completa de ajustes en clave "Arcade Holo": cuenta, audio y voz,
 * apariencia, accesibilidad, idioma, contenido y conexión. Se abre desde el
 * botón ⚙️ del HUD y ocupa el lugar del flujo principal (personaje→mundo→escena).
 *
 * Es una PLANTILLA presentacional: los controles guardan su estado en memoria
 * (útil para prototipar la UI) pero todavía no se persisten ni se aplican al
 * backend. El cableado real (guardar preferencias, aplicar tema, etc.) queda
 * pendiente; los sitios marcados con TODO indican dónde engancharlo.
 */

import { useState } from "react";
import styles from "./Settings.module.css";

interface Props {
  /** Vuelve al flujo principal cerrando la configuración. */
  onCerrar: () => void;
}

/** Estado local de la plantilla (aún no se persiste; ver TODO en el docstring). */
interface Ajustes {
  jugador: string;
  edad: string;
  voz: boolean;
  volumen: number;
  velocidadVoz: number;
  efectos: boolean;
  scanlines: boolean;
  animaciones: boolean;
  brillo: number;
  reducirMovimiento: boolean;
  tamanoTexto: string;
  altoContraste: boolean;
  idioma: string;
  dificultad: string;
  controlParental: boolean;
  backendUrl: string;
  modoDesarrollo: boolean;
}

const AJUSTES_INICIALES: Ajustes = {
  jugador: "",
  edad: "8-10",
  voz: true,
  volumen: 80,
  velocidadVoz: 100,
  efectos: true,
  scanlines: true,
  animaciones: true,
  brillo: 100,
  reducirMovimiento: false,
  tamanoTexto: "normal",
  altoContraste: false,
  idioma: "es",
  dificultad: "media",
  controlParental: true,
  backendUrl: import.meta.env.VITE_BACKEND_URL ?? "http://127.0.0.1:8000",
  modoDesarrollo: import.meta.env.VITE_DEBUG === "true",
};

export default function Settings({ onCerrar }: Props) {
  const [aj, setAj] = useState<Ajustes>(AJUSTES_INICIALES);

  // Actualiza un campo del estado de forma tipada.
  function set<K extends keyof Ajustes>(clave: K, valor: Ajustes[K]) {
    setAj((prev) => ({ ...prev, [clave]: valor }));
  }

  function guardar() {
    // TODO: persistir preferencias (localStorage / backend) y aplicarlas al tema,
    // audio, accesibilidad y api_client. De momento es una plantilla visual.
    onCerrar();
  }

  return (
    <section className={styles.page} aria-label="Configuración de la aplicación">
      <header className={styles.head}>
        <div>
          <p className={styles.kicker}>⚙️ AJUSTES</p>
          <h1 className={styles.title}>CONFIGURACIÓN</h1>
        </div>
        <button type="button" className={styles.close} onClick={onCerrar}>
          ✕ Cerrar
        </button>
      </header>

      <div className={styles.grid}>
        {/* --- Cuenta / Perfil --- */}
        <Panel icono="🎮" titulo="Perfil del jugador">
          <Fila etiqueta="Nombre" ayuda="Cómo te llamará tu personaje">
            <input
              className={styles.input}
              type="text"
              placeholder="Escribe tu nombre…"
              value={aj.jugador}
              onChange={(e) => set("jugador", e.target.value)}
            />
          </Fila>
          <Fila etiqueta="Edad" ayuda="Ajusta el contenido a tu edad">
            <Select
              valor={aj.edad}
              onCambio={(v) => set("edad", v)}
              opciones={[
                ["8-10", "8 a 10 años"],
                ["11-12", "11 a 12 años"],
              ]}
            />
          </Fila>
        </Panel>

        {/* --- Audio y voz --- */}
        <Panel icono="🔊" titulo="Audio y voz">
          <Fila etiqueta="Voz del personaje" ayuda="El personaje te responde hablando">
            <Toggle activo={aj.voz} onCambio={(v) => set("voz", v)} />
          </Fila>
          <Fila etiqueta="Volumen">
            <Slider valor={aj.volumen} onCambio={(v) => set("volumen", v)} />
          </Fila>
          <Fila etiqueta="Velocidad de la voz">
            <Slider
              valor={aj.velocidadVoz}
              min={50}
              max={150}
              onCambio={(v) => set("velocidadVoz", v)}
            />
          </Fila>
          <Fila etiqueta="Efectos de sonido">
            <Toggle activo={aj.efectos} onCambio={(v) => set("efectos", v)} />
          </Fila>
        </Panel>

        {/* --- Apariencia --- */}
        <Panel icono="✨" titulo="Apariencia">
          <Fila etiqueta="Efecto CRT (líneas)" ayuda="Las scanlines tipo TV antigua">
            <Toggle activo={aj.scanlines} onCambio={(v) => set("scanlines", v)} />
          </Fila>
          <Fila etiqueta="Animaciones de fondo">
            <Toggle activo={aj.animaciones} onCambio={(v) => set("animaciones", v)} />
          </Fila>
          <Fila etiqueta="Brillo holográfico">
            <Slider
              valor={aj.brillo}
              min={50}
              max={150}
              onCambio={(v) => set("brillo", v)}
            />
          </Fila>
        </Panel>

        {/* --- Accesibilidad --- */}
        <Panel icono="♿" titulo="Accesibilidad">
          <Fila etiqueta="Reducir movimiento" ayuda="Menos animaciones en pantalla">
            <Toggle
              activo={aj.reducirMovimiento}
              onCambio={(v) => set("reducirMovimiento", v)}
            />
          </Fila>
          <Fila etiqueta="Tamaño del texto">
            <Select
              valor={aj.tamanoTexto}
              onCambio={(v) => set("tamanoTexto", v)}
              opciones={[
                ["normal", "Normal"],
                ["grande", "Grande"],
                ["enorme", "Enorme"],
              ]}
            />
          </Fila>
          <Fila etiqueta="Alto contraste">
            <Toggle activo={aj.altoContraste} onCambio={(v) => set("altoContraste", v)} />
          </Fila>
        </Panel>

        {/* --- Idioma --- */}
        <Panel icono="🌍" titulo="Idioma">
          <Fila etiqueta="Idioma de la interfaz">
            <Select
              valor={aj.idioma}
              onCambio={(v) => set("idioma", v)}
              opciones={[
                ["es", "Español"],
                ["en", "English"],
                ["fr", "Français"],
              ]}
            />
          </Fila>
        </Panel>

        {/* --- Contenido y seguridad --- */}
        <Panel icono="🛡️" titulo="Contenido y seguridad">
          <Fila etiqueta="Nivel de dificultad" ayuda="Cómo de complejas son las respuestas">
            <Select
              valor={aj.dificultad}
              onCambio={(v) => set("dificultad", v)}
              opciones={[
                ["facil", "Fácil"],
                ["media", "Media"],
                ["avanzada", "Avanzada"],
              ]}
            />
          </Fila>
          <Fila etiqueta="Control parental" ayuda="Filtra el contenido para peques">
            <Toggle
              activo={aj.controlParental}
              onCambio={(v) => set("controlParental", v)}
            />
          </Fila>
        </Panel>

        {/* --- Conexión / Avanzado --- */}
        <Panel icono="📡" titulo="Conexión (avanzado)">
          <Fila etiqueta="URL del servidor" ayuda="Dónde vive el backend">
            <input
              className={styles.input}
              type="text"
              value={aj.backendUrl}
              onChange={(e) => set("backendUrl", e.target.value)}
            />
          </Fila>
          <Fila etiqueta="Modo desarrollo" ayuda="Muestra herramientas de diagnóstico">
            <Toggle activo={aj.modoDesarrollo} onCambio={(v) => set("modoDesarrollo", v)} />
          </Fila>
        </Panel>

        {/* --- Acerca de --- */}
        <Panel icono="ℹ️" titulo="Acerca de">
          <Fila etiqueta="Aplicación">
            <span className={styles.dato}>Máquina del Tiempo</span>
          </Fila>
          <Fila etiqueta="Versión">
            <span className={styles.dato}>1.0.0 · Arcade Holo</span>
          </Fila>
          <button
            type="button"
            className={styles.reset}
            onClick={() => setAj(AJUSTES_INICIALES)}
          >
            ↺ Restablecer valores
          </button>
        </Panel>
      </div>

      <footer className={styles.footer}>
        <button type="button" className="btn btn-secundario" onClick={onCerrar}>
          Cancelar
        </button>
        <button type="button" className="btn btn-primario" onClick={guardar}>
          💾 Guardar cambios
        </button>
      </footer>
    </section>
  );
}

/* ---------------------------------------------------------------------------
 * Primitivas de UI de la página (solo se usan aquí).
 * ------------------------------------------------------------------------- */

function Panel({
  icono,
  titulo,
  children,
}: {
  icono: string;
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <div className={styles.panel}>
      <h2 className={styles.panelTitle}>
        <span aria-hidden="true">{icono}</span> {titulo}
      </h2>
      <div className={styles.panelBody}>{children}</div>
    </div>
  );
}

function Fila({
  etiqueta,
  ayuda,
  children,
}: {
  etiqueta: string;
  ayuda?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={styles.fila}>
      <div className={styles.filaTexto}>
        <span className={styles.filaEtiqueta}>{etiqueta}</span>
        {ayuda && <span className={styles.filaAyuda}>{ayuda}</span>}
      </div>
      <div className={styles.filaControl}>{children}</div>
    </div>
  );
}

function Toggle({
  activo,
  onCambio,
}: {
  activo: boolean;
  onCambio: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      className={`${styles.toggle} ${activo ? styles.toggleOn : ""}`}
      onClick={() => onCambio(!activo)}
    >
      <span className={styles.toggleKnob} />
    </button>
  );
}

function Slider({
  valor,
  onCambio,
  min = 0,
  max = 100,
}: {
  valor: number;
  onCambio: (v: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <div className={styles.sliderWrap}>
      <input
        className={styles.slider}
        type="range"
        min={min}
        max={max}
        value={valor}
        onChange={(e) => onCambio(Number(e.target.value))}
      />
      <span className={styles.sliderVal}>{valor}</span>
    </div>
  );
}

function Select({
  valor,
  onCambio,
  opciones,
}: {
  valor: string;
  onCambio: (v: string) => void;
  opciones: [string, string][];
}) {
  return (
    <select
      className={styles.select}
      value={valor}
      onChange={(e) => onCambio(e.target.value)}
    >
      {opciones.map(([v, etiqueta]) => (
        <option key={v} value={v}>
          {etiqueta}
        </option>
      ))}
    </select>
  );
}
