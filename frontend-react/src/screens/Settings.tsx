/**
 * Settings — Área de configuración de la aplicación (con pestañas)
 * ================================================================
 *
 * Chasis "Arcade Holo" del menú de configuración. Se abre desde el botón ⚙️ del
 * HUD y ocupa el lugar del flujo principal. Organiza los ajustes en pestañas:
 *
 *   - APIs         → claves de los proveedores (Hito 2, funcional).
 *   - IA           → parámetros del motor: RAG, troceado, LLM y prompts (Hito 3).
 *   - General      → modo desarrollo/DEBUG (Hito 3).
 *   - Personajes   → CRUD de personajes (Hito 4).
 *   - Ubicaciones  → CRUD de ubicaciones (Hito 6).
 *
 * "APIs", "IA" y "General" ya son operativas; el resto muestra un aviso de
 * "próximo hito". La antigua plantilla presentacional (volumen, brillo…) se ha
 * retirado: se reaprovecha el estilo, no aquel contenido.
 */

import { useState } from "react";
import styles from "./Settings.module.css";
import ApisTab from "./config/ApisTab";
import ConfigForm from "./config/ConfigForm";

interface Props {
  /** Vuelve al flujo principal cerrando la configuración. */
  onCerrar: () => void;
}

const PESTANAS = [
  { id: "apis", label: "APIs", emoji: "🔑" },
  { id: "ia", label: "IA", emoji: "🧠" },
  { id: "general", label: "General", emoji: "⚙️" },
  { id: "personajes", label: "Personajes", emoji: "🎭" },
  { id: "ubicaciones", label: "Ubicaciones", emoji: "🗺️" },
] as const;

type PestanaId = (typeof PESTANAS)[number]["id"];

export default function Settings({ onCerrar }: Props) {
  const [pestana, setPestana] = useState<PestanaId>("apis");

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

      <nav className={styles.tabs} aria-label="Secciones de configuración">
        {PESTANAS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`${styles.tab} ${pestana === t.id ? styles.tabOn : ""}`}
            onClick={() => setPestana(t.id)}
            aria-current={pestana === t.id}
          >
            <span aria-hidden="true">{t.emoji}</span> {t.label}
          </button>
        ))}
      </nav>

      {pestana === "apis" && <ApisTab />}
      {pestana === "ia" && (
        <ConfigForm
          categorias={["rag", "chunking", "llm", "prompts"]}
          intro="Ajusta el motor de conversación: cómo decide el Evaluator (RAG vs conocimiento general), cuántas fichas recupera, el modelo de lenguaje, el troceado de documentos y los prompts de sistema. Los cambios se aplican al instante, sin reiniciar."
        />
      )}
      {pestana === "general" && (
        <ConfigForm
          categorias={["general"]}
          intro="Opciones generales de la aplicación."
        />
      )}
      {(pestana === "personajes" || pestana === "ubicaciones") && (
        <div className={styles.panel}>
          <h2 className={styles.panelTitle}>Próximamente</h2>
          <p className={styles.filaAyuda}>
            Esta sección se habilita en un próximo hito del menú de configuración.
          </p>
        </div>
      )}

      <footer className={styles.footer}>
        <button type="button" className="btn btn-secundario" onClick={onCerrar}>
          Volver
        </button>
      </footer>
    </section>
  );
}
