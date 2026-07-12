/**
 * PersonajesTab — Pestaña "Personajes" del menú de configuración (Hito 4)
 * =======================================================================
 *
 * CRUD del catálogo de personajes SIN tocar código. Un adulto puede:
 *   - Ver todos los personajes (activos e inactivos).
 *   - Crear uno nuevo: al guardarlo, el backend genera de golpe todas las piezas
 *     del invariante (fila en BBDD + carpeta backend/documentos/<id>/ para el RAG).
 *   - Editar nombre, categoría, emoji, descripción de imagen, voz y si está activo.
 *   - Borrarlo.
 *
 * La VOZ se elige de un desplegable con las voces de ElevenLabs (GET /api/voices).
 * Si la clave no permite listar voces, se puede escribir el ID de la voz a mano.
 * Un personaje sin voz responde solo en texto (degradación válida).
 */

import { useEffect, useState } from "react";
import {
  BackendError,
  createPersonaje,
  deletePersonaje,
  getPersonajes,
  getVoices,
  reindexGlobal,
  updatePersonaje,
} from "../../api/client";
import type { PersonajeDTO, VozDTO } from "../../api/types";
import styles from "../Settings.module.css";
import DocumentosPanel from "./DocumentosPanel";

const CATEGORIAS = [
  { valor: "prehistorico", label: "Prehistórico" },
  { valor: "historico", label: "Histórico" },
  { valor: "ficticio", label: "Ficticio" },
];

/** Estado de formulario (create/edit). En edición, `id` es de solo lectura. */
interface FormState {
  id: string;
  nombre: string;
  categoria: string;
  emoji: string;
  prompt_imagen: string;
  voz_id: string;
  activo: boolean;
}

const FORM_VACIO: FormState = {
  id: "",
  nombre: "",
  categoria: "historico",
  emoji: "",
  prompt_imagen: "",
  voz_id: "",
  activo: true,
};

function aForm(p: PersonajeDTO): FormState {
  return {
    id: p.id,
    nombre: p.nombre,
    categoria: p.categoria ?? "",
    emoji: p.emoji ?? "",
    prompt_imagen: p.prompt_imagen,
    voz_id: p.voz_id ?? "",
    activo: p.activo,
  };
}

export default function PersonajesTab() {
  const [personajes, setPersonajes] = useState<PersonajeDTO[] | null>(null);
  const [voces, setVoces] = useState<VozDTO[]>([]);
  const [vocesMsg, setVocesMsg] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  // "__nuevo__" = formulario de alta; un id = editando ese personaje; null = nada.
  const [editando, setEditando] = useState<string | null>(null);

  async function cargar() {
    setError(null);
    try {
      setPersonajes(await getPersonajes(true)); // incluye inactivos (vista admin)
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  async function cargarVoces() {
    try {
      const res = await getVoices();
      setVoces(res.voces);
      setVocesMsg(res.disponible ? "" : res.mensaje);
    } catch (exc) {
      setVocesMsg(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  useEffect(() => {
    void cargar();
    void cargarVoces();
  }, []);

  async function guardarNuevo(form: FormState) {
    const creado = await createPersonaje({
      id: form.id.trim(),
      nombre: form.nombre.trim(),
      prompt_imagen: form.prompt_imagen.trim(),
      categoria: form.categoria || null,
      emoji: form.emoji.trim() || null,
      voz_id: form.voz_id.trim() || null,
      activo: form.activo,
    });
    setOkMsg(`Personaje "${creado.nombre}" creado. Ya puedes subirle documentos del RAG.`);
  }

  async function guardarEdicion(form: FormState) {
    await updatePersonaje(form.id, {
      nombre: form.nombre.trim(),
      prompt_imagen: form.prompt_imagen.trim(),
      categoria: form.categoria || null,
      emoji: form.emoji.trim() || null,
      voz_id: form.voz_id.trim() || null,
      activo: form.activo,
    });
    setOkMsg(`Cambios guardados en "${form.nombre}".`);
  }

  async function onSubmit(form: FormState, esNuevo: boolean) {
    setError(null);
    setOkMsg(null);
    try {
      if (esNuevo) await guardarNuevo(form);
      else await guardarEdicion(form);
      setEditando(null);
      await cargar();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  async function onReindexTodo() {
    setError(null);
    setOkMsg(null);
    try {
      const r = await reindexGlobal();
      setOkMsg(
        `Reindexado global: ${r.archivos} archivo(s) → ${r.chunks} fragmento(s) de ${r.personajes} personaje(s).`,
      );
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  async function onBorrar(p: PersonajeDTO) {
    if (!window.confirm(`¿Seguro que quieres borrar a "${p.nombre}"? Esto lo quita del catálogo.`))
      return;
    setError(null);
    setOkMsg(null);
    try {
      await deletePersonaje(p.id);
      setOkMsg(`Personaje "${p.nombre}" borrado.`);
      await cargar();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  if (error && !personajes) {
    return (
      <div className={styles.panel}>
        <p className={styles.filaAyuda}>No se pudo cargar el catálogo: {error}</p>
        <button type="button" className="btn btn-secundario" onClick={() => void cargar()}>
          Reintentar
        </button>
      </div>
    );
  }

  if (!personajes) {
    return (
      <div className={styles.panel}>
        <p className={styles.filaAyuda}>Cargando…</p>
      </div>
    );
  }

  return (
    <div className={styles.cfgWrap}>
      <p className={styles.apisIntro}>
        Crea y personaliza los personajes con los que chatea el niño. Al crear uno se
        prepara también su carpeta de documentos para el RAG (podrás subirlos en un
        próximo hito).
      </p>

      {error && <p className={styles.testNo}>❌ {error}</p>}
      {okMsg && <p className={styles.testOk}>✅ {okMsg}</p>}

      {editando === "__nuevo__" ? (
        <PersonajeForm
          inicial={FORM_VACIO}
          esNuevo
          voces={voces}
          vocesMsg={vocesMsg}
          onCancelar={() => setEditando(null)}
          onGuardar={(f) => onSubmit(f, true)}
        />
      ) : (
        <div className={styles.pjBarra}>
          <button
            type="button"
            className="btn btn-primario"
            onClick={() => {
              setOkMsg(null);
              setError(null);
              setEditando("__nuevo__");
            }}
          >
            ➕ Nuevo personaje
          </button>
          <button
            type="button"
            className="btn btn-secundario"
            onClick={() => void onReindexTodo()}
            title="Reconstruye el índice del RAG para TODOS los personajes"
          >
            ♻️ Reindexar todo
          </button>
        </div>
      )}

      <div className={styles.pjLista}>
        {personajes.map((p) =>
          editando === p.id ? (
            <PersonajeForm
              key={p.id}
              inicial={aForm(p)}
              esNuevo={false}
              voces={voces}
              vocesMsg={vocesMsg}
              onCancelar={() => setEditando(null)}
              onGuardar={(f) => onSubmit(f, false)}
            />
          ) : (
            <div key={p.id} className={styles.pjCard}>
              <span className={styles.pjEmoji} aria-hidden="true">
                {p.emoji ?? "🎭"}
              </span>
              <div className={styles.pjInfo}>
                <span className={styles.pjNombre}>
                  {p.nombre}
                  {!p.activo && <span className={styles.pjInactivo}> · oculto</span>}
                </span>
                <span className={styles.pjMeta}>
                  <code>{p.id}</code>
                  {p.categoria ? ` · ${p.categoria}` : ""}
                  {p.voz_id ? " · 🔊 con voz" : " · 🔇 solo texto"}
                </span>
              </div>
              <div className={styles.pjAcciones}>
                <button
                  type="button"
                  className={styles.testBtn}
                  onClick={() => {
                    setOkMsg(null);
                    setError(null);
                    setEditando(p.id);
                  }}
                >
                  ✏️ Editar
                </button>
                <button type="button" className={styles.pjBorrar} onClick={() => void onBorrar(p)}>
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
  voces: VozDTO[];
  vocesMsg: string;
  onCancelar: () => void;
  onGuardar: (form: FormState) => void | Promise<void>;
}

function PersonajeForm({ inicial, esNuevo, voces, vocesMsg, onCancelar, onGuardar }: FormProps) {
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

  const hayVoces = voces.length > 0;

  return (
    <div className={styles.pjForm}>
      <h3 className={styles.pjFormTitulo}>
        {esNuevo ? "Nuevo personaje" : `Editando: ${inicial.nombre}`}
      </h3>

      {esNuevo && (
        <label className={styles.pjLabel}>
          Id (no se puede cambiar luego)
          <input
            className={styles.input}
            value={form.id}
            placeholder="marie_curie"
            spellCheck={false}
            onChange={(e) => set("id", e.target.value)}
          />
          <span className={styles.filaAyuda}>Minúsculas, números, guion (-) o guion bajo (_).</span>
        </label>
      )}

      <label className={styles.pjLabel}>
        Nombre
        <input
          className={styles.input}
          value={form.nombre}
          placeholder="Marie Curie"
          onChange={(e) => set("nombre", e.target.value)}
        />
      </label>

      <div className={styles.pjFila2}>
        <label className={styles.pjLabel}>
          Categoría
          <select
            className={styles.select}
            value={form.categoria}
            onChange={(e) => set("categoria", e.target.value)}
          >
            <option value="">(sin categoría)</option>
            {CATEGORIAS.map((c) => (
              <option key={c.valor} value={c.valor}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.pjLabel}>
          Emoji
          <input
            className={styles.input}
            value={form.emoji}
            placeholder="🔬"
            onChange={(e) => set("emoji", e.target.value)}
          />
        </label>
      </div>

      <label className={styles.pjLabel}>
        Descripción para su imagen (en inglés)
        <textarea
          className={styles.textarea}
          value={form.prompt_imagen}
          rows={3}
          placeholder="Marie Curie as a kind scientist, big expressive eyes, holding a test tube"
          spellCheck={false}
          onChange={(e) => set("prompt_imagen", e.target.value)}
        />
        <span className={styles.filaAyuda}>
          Sin datos personales; describe su aspecto amable para un render 3D estilo Pixar.
        </span>
      </label>

      <label className={styles.pjLabel}>
        Voz (ElevenLabs)
        {hayVoces ? (
          <select
            className={styles.select}
            value={form.voz_id}
            onChange={(e) => set("voz_id", e.target.value)}
          >
            <option value="">Sin voz (solo texto)</option>
            {voces.map((v) => (
              <option key={v.voz_id} value={v.voz_id}>
                {v.nombre}
              </option>
            ))}
          </select>
        ) : (
          <input
            className={styles.input}
            value={form.voz_id}
            placeholder="ID de la voz (opcional)"
            spellCheck={false}
            onChange={(e) => set("voz_id", e.target.value)}
          />
        )}
        {!hayVoces && vocesMsg && <span className={styles.filaAyuda}>{vocesMsg}</span>}
      </label>

      <label className={styles.pjToggleFila}>
        <span className={styles.filaEtiqueta}>Activo (visible para el niño)</span>
        <button
          type="button"
          className={`${styles.toggle} ${form.activo ? styles.toggleOn : ""}`}
          onClick={() => set("activo", !form.activo)}
          role="switch"
          aria-checked={form.activo}
          aria-label="Activo"
        >
          <span className={styles.toggleKnob} />
        </button>
      </label>

      <div className={styles.footer}>
        <button type="button" className="btn btn-secundario" onClick={onCancelar} disabled={guardando}>
          Cancelar
        </button>
        <button type="button" className="btn btn-primario" onClick={() => void submit()} disabled={guardando}>
          {guardando ? "Guardando…" : esNuevo ? "Crear personaje" : "Guardar cambios"}
        </button>
      </div>

      {/* Los documentos del RAG solo existen para un personaje ya creado. */}
      {!esNuevo && <DocumentosPanel personajeId={inicial.id} />}
    </div>
  );
}
