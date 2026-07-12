/**
 * UbicacionesTab — Pestaña "Ubicaciones" del menú de configuración (Hito 6)
 * =========================================================================
 *
 * CRUD del catálogo de lugares SIN tocar código, gemelo (más simple) de la
 * pestaña de personajes: crear/editar/borrar ubicaciones (id, nombre, emoji y la
 * descripción en inglés para generar el fondo). Cualquier personaje puede aparecer
 * en cualquier ubicación (combinación libre).
 */

import { useEffect, useState } from "react";
import {
  BackendError,
  createUbicacion,
  deleteUbicacion,
  getUbicaciones,
  updateUbicacion,
} from "../../api/client";
import type { UbicacionDTO } from "../../api/types";
import styles from "../Settings.module.css";

interface FormState {
  id: string;
  nombre: string;
  emoji: string;
  prompt_imagen: string;
  activo: boolean;
}

const FORM_VACIO: FormState = { id: "", nombre: "", emoji: "", prompt_imagen: "", activo: true };

function aForm(u: UbicacionDTO): FormState {
  return {
    id: u.id,
    nombre: u.nombre,
    emoji: u.emoji ?? "",
    prompt_imagen: u.prompt_imagen,
    activo: u.activo,
  };
}

export default function UbicacionesTab() {
  const [ubicaciones, setUbicaciones] = useState<UbicacionDTO[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [editando, setEditando] = useState<string | null>(null);

  async function cargar() {
    setError(null);
    try {
      setUbicaciones(await getUbicaciones(true)); // incluye inactivas (vista admin)
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  useEffect(() => {
    void cargar();
  }, []);

  async function onSubmit(form: FormState, esNuevo: boolean) {
    setError(null);
    setOkMsg(null);
    try {
      if (esNuevo) {
        const creada = await createUbicacion({
          id: form.id.trim(),
          nombre: form.nombre.trim(),
          prompt_imagen: form.prompt_imagen.trim(),
          emoji: form.emoji.trim() || null,
          activo: form.activo,
        });
        setOkMsg(`Ubicación "${creada.nombre}" creada.`);
      } else {
        await updateUbicacion(form.id, {
          nombre: form.nombre.trim(),
          prompt_imagen: form.prompt_imagen.trim(),
          emoji: form.emoji.trim() || null,
          activo: form.activo,
        });
        setOkMsg(`Cambios guardados en "${form.nombre}".`);
      }
      setEditando(null);
      await cargar();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  async function onBorrar(u: UbicacionDTO) {
    if (!window.confirm(`¿Seguro que quieres borrar "${u.nombre}"? Esto la quita del catálogo.`))
      return;
    setError(null);
    setOkMsg(null);
    try {
      await deleteUbicacion(u.id);
      setOkMsg(`Ubicación "${u.nombre}" borrada.`);
      await cargar();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  if (error && !ubicaciones) {
    return (
      <div className={styles.panel}>
        <p className={styles.filaAyuda}>No se pudo cargar el catálogo: {error}</p>
        <button type="button" className="btn btn-secundario" onClick={() => void cargar()}>
          Reintentar
        </button>
      </div>
    );
  }

  if (!ubicaciones) {
    return (
      <div className={styles.panel}>
        <p className={styles.filaAyuda}>Cargando…</p>
      </div>
    );
  }

  return (
    <div className={styles.cfgWrap}>
      <p className={styles.apisIntro}>
        Crea y personaliza los mundos donde aparece el personaje. Cualquier personaje
        puede ir en cualquier ubicación (¡un T-Rex en un laboratorio!).
      </p>

      {error && <p className={styles.testNo}>❌ {error}</p>}
      {okMsg && <p className={styles.testOk}>✅ {okMsg}</p>}

      {editando === "__nuevo__" ? (
        <UbicacionForm
          inicial={FORM_VACIO}
          esNuevo
          onCancelar={() => setEditando(null)}
          onGuardar={(f) => onSubmit(f, true)}
        />
      ) : (
        <button
          type="button"
          className="btn btn-primario"
          onClick={() => {
            setOkMsg(null);
            setError(null);
            setEditando("__nuevo__");
          }}
        >
          ➕ Nueva ubicación
        </button>
      )}

      <div className={styles.pjLista}>
        {ubicaciones.map((u) =>
          editando === u.id ? (
            <UbicacionForm
              key={u.id}
              inicial={aForm(u)}
              esNuevo={false}
              onCancelar={() => setEditando(null)}
              onGuardar={(f) => onSubmit(f, false)}
            />
          ) : (
            <div key={u.id} className={styles.pjCard}>
              <span className={styles.pjEmoji} aria-hidden="true">
                {u.emoji ?? "🗺️"}
              </span>
              <div className={styles.pjInfo}>
                <span className={styles.pjNombre}>
                  {u.nombre}
                  {!u.activo && <span className={styles.pjInactivo}> · oculta</span>}
                </span>
                <span className={styles.pjMeta}>
                  <code>{u.id}</code>
                </span>
              </div>
              <div className={styles.pjAcciones}>
                <button
                  type="button"
                  className={styles.testBtn}
                  onClick={() => {
                    setOkMsg(null);
                    setError(null);
                    setEditando(u.id);
                  }}
                >
                  ✏️ Editar
                </button>
                <button type="button" className={styles.pjBorrar} onClick={() => void onBorrar(u)}>
                  🗑
                </button>
              </div>
            </div>
          ),
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Formulario compartido de alta/edición.
// ---------------------------------------------------------------------------
interface FormProps {
  inicial: FormState;
  esNuevo: boolean;
  onCancelar: () => void;
  onGuardar: (form: FormState) => void | Promise<void>;
}

function UbicacionForm({ inicial, esNuevo, onCancelar, onGuardar }: FormProps) {
  const [form, setForm] = useState<FormState>(inicial);
  const [guardando, setGuardando] = useState(false);

  function set<K extends keyof FormState>(campo: K, valor: FormState[K]) {
    setForm((prev) => ({ ...prev, [campo]: valor }));
  }

  async function submit() {
    setGuardando(true);
    try {
      await onGuardar(form);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className={styles.pjForm}>
      <h3 className={styles.pjFormTitulo}>
        {esNuevo ? "Nueva ubicación" : `Editando: ${inicial.nombre}`}
      </h3>

      {esNuevo && (
        <label className={styles.pjLabel}>
          Id (no se puede cambiar luego)
          <input
            className={styles.input}
            value={form.id}
            placeholder="antiguo_egipto"
            spellCheck={false}
            onChange={(e) => set("id", e.target.value)}
          />
          <span className={styles.filaAyuda}>Minúsculas, números, guion (-) o guion bajo (_).</span>
        </label>
      )}

      <div className={styles.pjFila2}>
        <label className={styles.pjLabel}>
          Nombre
          <input
            className={styles.input}
            value={form.nombre}
            placeholder="Antiguo Egipto"
            onChange={(e) => set("nombre", e.target.value)}
          />
        </label>
        <label className={styles.pjLabel}>
          Emoji
          <input
            className={styles.input}
            value={form.emoji}
            placeholder="🏜️"
            onChange={(e) => set("emoji", e.target.value)}
          />
        </label>
      </div>

      <label className={styles.pjLabel}>
        Descripción del fondo (en inglés)
        <textarea
          className={styles.textarea}
          value={form.prompt_imagen}
          rows={3}
          placeholder="inside an ancient Egyptian temple with hieroglyphs and golden statues"
          spellCheck={false}
          onChange={(e) => set("prompt_imagen", e.target.value)}
        />
        <span className={styles.filaAyuda}>
          Describe el escenario para un render 3D estilo Pixar (colorido y amable).
        </span>
      </label>

      <label className={styles.pjToggleFila}>
        <span className={styles.filaEtiqueta}>Activa (visible para el niño)</span>
        <button
          type="button"
          className={`${styles.toggle} ${form.activo ? styles.toggleOn : ""}`}
          onClick={() => set("activo", !form.activo)}
          role="switch"
          aria-checked={form.activo}
          aria-label="Activa"
        >
          <span className={styles.toggleKnob} />
        </button>
      </label>

      <div className={styles.footer}>
        <button type="button" className="btn btn-secundario" onClick={onCancelar} disabled={guardando}>
          Cancelar
        </button>
        <button type="button" className="btn btn-primario" onClick={() => void submit()} disabled={guardando}>
          {guardando ? "Guardando…" : esNuevo ? "Crear ubicación" : "Guardar cambios"}
        </button>
      </div>
    </div>
  );
}
