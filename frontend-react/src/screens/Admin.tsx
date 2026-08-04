/**
 * Admin — Área de ADMINISTRACIÓN de la aplicación (con pestañas)
 * ==============================================================
 *
 * Chasis "Arcade Holo" de la administración. Se abre desde el botón 🛡️ del HUD y
 * ocupa el lugar del flujo principal. Toda la config GLOBAL y COMPARTIDA vive aquí
 * (H9.2, Fase 1): cambiar algo afecta a TODOS los perfiles, y tocarla sin saber puede
 * romper la app — por eso se separó de "Configuración" (que solo gestiona el PIN de
 * familia). Va detrás de la contraseña de administración: hasta autenticarse se
 * muestra <AdminGate/>; luego, las pestañas:
 *
 *   - APIs         → claves de los proveedores (Hito 2).
 *   - IA           → motor de chat: recuperación, Evaluator/reranker, LLM y prompts.
 *   - Imagen       → modelos de generación, salida y estilo visual común de la escena.
 *   - Voz          → transcripción (STT) y voz de la respuesta (TTS).
 *   - Personajes   → CRUD de personajes + documentos del RAG (Hitos 4 y 5).
 *   - Ubicaciones  → CRUD de ubicaciones (Hito 6).
 *   - Sistema      → import/export y modo desarrollo/DEBUG + cerrar sesión (Hito 7).
 */

import { useCallback, useState } from "react";
import { adminLogout } from "../api/client";
import styles from "./Settings.module.css";
import AdminGate from "./config/AdminGate";
import ApisTab from "./config/ApisTab";
import AuditoriaTab from "./config/AuditoriaTab";
import ConfigForm from "./config/ConfigForm";
import PersonajesTab from "./config/PersonajesTab";
import SistemaTab from "./config/SistemaTab";
import UbicacionesTab from "./config/UbicacionesTab";

interface Props {
  /** Vuelve al flujo principal cerrando la administración. */
  onCerrar: () => void;
}

const PESTANAS = [
  { id: "apis", label: "APIs", emoji: "🔑" },
  { id: "ia", label: "IA", emoji: "🧠" },
  { id: "imagen", label: "Imagen", emoji: "🖼️" },
  { id: "voz", label: "Voz", emoji: "🎙️" },
  { id: "personajes", label: "Personajes", emoji: "🎭" },
  { id: "ubicaciones", label: "Ubicaciones", emoji: "🗺️" },
  { id: "correo", label: "Correo", emoji: "📧" },
  { id: "auditoria", label: "Auditoría", emoji: "🧾" },
  { id: "sistema", label: "Sistema", emoji: "🛠️" },
] as const;

type PestanaId = (typeof PESTANAS)[number]["id"];

export default function Admin({ onCerrar }: Props) {
  const [pestana, setPestana] = useState<PestanaId>("apis");
  // Sesión de adulto: hasta autenticarse se muestra la puerta (AdminGate).
  const [autenticado, setAutenticado] = useState(false);

  const cerrarSesion = useCallback(async () => {
    await adminLogout();
    setAutenticado(false);
  }, []);

  return (
    <section className={styles.page} aria-label="Administración de la aplicación">
      <header className={styles.head}>
        <div>
          <p className={styles.kicker}>🛡️ ADMINISTRACIÓN</p>
          <h1 className={styles.title}>ADMIN</h1>
        </div>
        <button type="button" className={styles.close} onClick={onCerrar}>
          ✕ Cerrar
        </button>
      </header>

      {!autenticado ? (
        <AdminGate onListo={() => setAutenticado(true)} />
      ) : (
        <>
          <nav className={styles.tabs} aria-label="Secciones de administración">
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
              intro="Ajusta el motor de conversación, agrupado por lógica: cómo se recuperan las fichas, cómo se decide RAG vs conocimiento general (reranker o Evaluator), el modelo de lenguaje y los prompts. Algunos ajustes se desactivan según otro (p. ej. con el reranker activo, el Evaluator por umbral coseno no interviene). Los cambios se aplican al instante, sin reiniciar."
            />
          )}
          {pestana === "imagen" && (
            <ConfigForm
              categorias={["imagen", "estilo_imagen"]}
              intro="Generación de la escena: modelos de Replicate, formato de salida y el estilo visual común a TODAS las imágenes (personajes y ubicaciones), para que se vea coherente sea cual sea la combinación. Los cambios se aplican al instante, sin reiniciar."
            />
          )}
          {pestana === "voz" && (
            <ConfigForm
              categorias={["voz"]}
              intro="Voz: la transcripción de la pregunta hablada (STT, seleccionable entre ElevenLabs, faster-whisper local o Groq) y la voz de la respuesta (TTS, ElevenLabs). Los ajustes de cada proveedor de STT se desactivan si no está elegido. Los cambios se aplican al instante, sin reiniciar."
            />
          )}
          {pestana === "personajes" && <PersonajesTab />}
          {pestana === "ubicaciones" && <UbicacionesTab />}
          {pestana === "correo" && (
            <ConfigForm
              categorias={["correo"]}
              intro="Servidor de correo (SMTP) para enviar el código de verificación al dar de alta una familia. Sin SMTP configurado (o en modo desarrollo), el código se muestra en la consola del backend. La CONTRASEÑA del SMTP es un secreto y se pone en la pestaña APIs (proveedor «SMTP»). Los cambios se aplican al instante."
            />
          )}
          {pestana === "auditoria" && <AuditoriaTab />}
          {pestana === "sistema" && <SistemaTab onLogout={() => void cerrarSesion()} />}
        </>
      )}

      <footer className={styles.footer}>
        <button type="button" className="btn btn-secundario" onClick={onCerrar}>
          Volver
        </button>
      </footer>
    </section>
  );
}
