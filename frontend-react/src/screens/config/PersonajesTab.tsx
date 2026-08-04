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

import { useEffect, useRef, useState } from "react";
import {
  assetUrl,
  BackendError,
  borrarAvatarPersonaje,
  createPersonaje,
  deletePersonaje,
  generarAvatarPersonaje,
  getPersonajesInfo,
  getReindexEstado,
  getVoices,
  probarVoz,
  reindexGlobal,
  updatePersonaje,
} from "../../api/client";
import type { PersonajeDTO, ReindexEstado, VozDTO } from "../../api/types";
import Modal from "../../components/Modal/Modal";
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
  const [limite, setLimite] = useState<number | null>(null);
  const [voces, setVoces] = useState<VozDTO[]>([]);
  const [vocesMsg, setVocesMsg] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  // "__nuevo__" = formulario de alta; un id = editando ese personaje; null = nada.
  const [editando, setEditando] = useState<string | null>(null);
  // Bloquea el modal (cierre + campos) mientras se procesa un documento o se guarda.
  const [bloqueado, setBloqueado] = useState(false);
  // Reindexado GLOBAL: null = inactivo; con valor = modal bloqueante abierto,
  // sondeando /api/reindex/estado para la barra de progreso.
  const [progresoReindex, setProgresoReindex] = useState<ReindexEstado | null>(null);

  async function cargar() {
    setError(null);
    try {
      const info = await getPersonajesInfo(true); // incluye inactivos (vista admin)
      setPersonajes(info.personajes);
      setLimite(info.limite);
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
    setProgresoReindex({ en_curso: true, total: 0, hecho: 0, personaje_actual: null, porcentaje: 0 });

    // Sondea el progreso mientras dura la petición de reindexado (que no se
    // resuelve hasta que TODO termina). `activo` evita una carrera real: un
    // sondeo ya en vuelo puede resolver DESPUÉS de que el `finally` de abajo
    // cierre el modal (clearInterval solo detiene sondeos FUTUROS), lo que
    // reabriría el modal atascado en el último progreso visto.
    let activo = true;
    const sondeo = window.setInterval(() => {
      void getReindexEstado()
        .then((estado) => {
          if (activo) setProgresoReindex(estado);
        })
        .catch(() => {});
    }, 400);

    try {
      const r = await reindexGlobal();
      setOkMsg(
        `Reindexado global: ${r.archivos} archivo(s) → ${r.chunks} fragmento(s) de ${r.personajes} personaje(s).`,
      );
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      activo = false;
      window.clearInterval(sondeo);
      setProgresoReindex(null);
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

  /** Abre el modal de edición/alta (id de personaje, o "__nuevo__"). */
  function abrirEdicion(id: string) {
    setOkMsg(null);
    setError(null);
    setBloqueado(false);
    setEditando(id);
  }

  /** Cierra el modal, salvo que haya una operación en curso (guardado/documentos). */
  function cerrarModal() {
    if (bloqueado) return;
    setEditando(null);
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

  const personajeEnEdicion = editando && editando !== "__nuevo__" ? personajes.find((p) => p.id === editando) : null;
  const alLimite = limite !== null && personajes.length >= limite;

  return (
    <div className={styles.cfgWrap}>
      <p className={styles.apisIntro}>
        Crea y personaliza los personajes. Al crear uno se prepara también su carpeta de
        documentos para el RAG
      </p>

      {error && <p className={styles.testNo}>❌ {error}</p>}
      {okMsg && <p className={styles.testOk}>✅ {okMsg}</p>}

      <div className={styles.pjBarra}>
        <button
          type="button"
          className="btn btn-primario"
          onClick={() => abrirEdicion("__nuevo__")}
          disabled={alLimite || !!progresoReindex}
          title={alLimite ? `Límite de ${limite} personajes alcanzado` : undefined}
        >
          ➕ Nuevo personaje
        </button>
        <button
          type="button"
          className="btn btn-secundario"
          onClick={() => void onReindexTodo()}
          disabled={!!progresoReindex}
          title="Reconstruye el índice del RAG para TODOS los personajes"
        >
          {progresoReindex ? "♻️ Reindexando…" : "♻️ Reindexar todo"}
        </button>
      </div>
      {alLimite && !progresoReindex && (
        <p className={styles.filaAyuda}>
          Límite de {limite} personajes alcanzado. Borra alguno para poder crear uno nuevo.
        </p>
      )}

      <div className={styles.pjLista}>
        {personajes.map((p) => (
          <div key={p.id} className={styles.pjCard}>
            {p.avatar_url ? (
              <img className={styles.pjMini} src={assetUrl(p.avatar_url)} alt="" aria-hidden="true" />
            ) : (
              <span className={styles.pjEmoji} aria-hidden="true">
                {p.emoji ?? "🎭"}
              </span>
            )}
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
              <button type="button" className={styles.testBtn} onClick={() => abrirEdicion(p.id)}>
                ✏️ Editar
              </button>
              <button type="button" className={styles.pjBorrar} onClick={() => void onBorrar(p)}>
                🗑
              </button>
            </div>
          </div>
        ))}
      </div>

      {editando && (
        <Modal
          titulo={editando === "__nuevo__" ? "Nuevo personaje" : `Editando: ${personajeEnEdicion?.nombre ?? editando}`}
          onCerrar={cerrarModal}
          bloqueado={bloqueado}
        >
          <PersonajeForm
            inicial={editando === "__nuevo__" ? FORM_VACIO : aForm(personajeEnEdicion!)}
            esNuevo={editando === "__nuevo__"}
            personaje={editando === "__nuevo__" ? null : (personajeEnEdicion ?? null)}
            voces={voces}
            vocesMsg={vocesMsg}
            onCancelar={cerrarModal}
            onGuardar={(f) => onSubmit(f, editando === "__nuevo__")}
            onAvatarCambiado={() => void cargar()}
            onBloqueadoChange={setBloqueado}
          />
        </Modal>
      )}

      {progresoReindex && (
        <Modal titulo="Reindexando el catálogo" onCerrar={() => {}} bloqueado mensajeBloqueo={mensajeReindex(progresoReindex)} progreso={progresoReindex.porcentaje}>
          {null}
        </Modal>
      )}
    </div>
  );
}

/** Texto del overlay de reindexado global, según lo que va reportando el sondeo. */
function mensajeReindex(p: ReindexEstado): string {
  if (p.total === 0) return "Preparando el reindexado…";
  const quien = p.personaje_actual ? ` (${p.personaje_actual})` : "";
  return `Reindexando… ${p.hecho} de ${p.total} personajes${quien} — ${Math.round(p.porcentaje)}%`;
}

// ---------------------------------------------------------------------------
// Formulario compartido de alta/edición.
// ---------------------------------------------------------------------------
interface FormProps {
  inicial: FormState;
  esNuevo: boolean;
  /** El personaje en edición (null al crear): aporta id + avatar_url para la imagen. */
  personaje: PersonajeDTO | null;
  voces: VozDTO[];
  vocesMsg: string;
  onCancelar: () => void;
  onGuardar: (form: FormState) => void | Promise<void>;
  /** Se llama tras generar/quitar el avatar, para refrescar el catálogo del carrusel. */
  onAvatarCambiado: () => void;
  /** Notifica al Modal contenedor si hay algo en curso (guardando, o el panel
   * de documentos procesando algo) para que bloquee el cierre y los campos. */
  onBloqueadoChange: (bloqueado: boolean) => void;
}

function PersonajeForm({
  inicial,
  esNuevo,
  personaje,
  voces,
  vocesMsg,
  onCancelar,
  onGuardar,
  onAvatarCambiado,
  onBloqueadoChange,
}: FormProps) {
  const [form, setForm] = useState<FormState>(inicial);
  const [guardando, setGuardando] = useState(false);
  const [probandoVoz, setProbandoVoz] = useState(false);
  const [errorVoz, setErrorVoz] = useState<string | null>(null);
  const [docsOcupado, setDocsOcupado] = useState(false);
  // Avatar del carrusel: URL vigente y estado de generación/borrado.
  const [avatarUrl, setAvatarUrl] = useState<string | null>(personaje?.avatar_url ?? null);
  const [avatarOcupado, setAvatarOcupado] = useState(false);
  const [errorAvatar, setErrorAvatar] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    onBloqueadoChange(guardando || docsOcupado || avatarOcupado);
  }, [guardando, docsOcupado, avatarOcupado, onBloqueadoChange]);

  async function onGenerarAvatar() {
    if (!personaje) return;
    setErrorAvatar(null);
    setAvatarOcupado(true);
    try {
      const actualizado = await generarAvatarPersonaje(personaje.id);
      setAvatarUrl(actualizado.avatar_url ?? null);
      onAvatarCambiado();
    } catch (exc) {
      setErrorAvatar(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setAvatarOcupado(false);
    }
  }

  async function onQuitarAvatar() {
    if (!personaje) return;
    setErrorAvatar(null);
    setAvatarOcupado(true);
    try {
      await borrarAvatarPersonaje(personaje.id);
      setAvatarUrl(null);
      onAvatarCambiado();
    } catch (exc) {
      setErrorAvatar(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setAvatarOcupado(false);
    }
  }

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

  async function onProbarVoz() {
    if (!form.voz_id.trim()) return;
    setErrorVoz(null);
    setProbandoVoz(true);
    try {
      const audioBase64 = await probarVoz(form.voz_id.trim());
      audioRef.current?.pause();
      const audio = new Audio(`data:audio/mpeg;base64,${audioBase64}`);
      audioRef.current = audio;
      await audio.play();
    } catch (exc) {
      setErrorVoz(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setProbandoVoz(false);
    }
  }

  const hayVoces = voces.length > 0;

  return (
    <div className={styles.pjForm}>
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
          Sin datos personales; describe su aspecto para un render 3D estilo Pixar (colorido y amable).
        </span>
      </label>

      {/* Avatar del carrusel: se genera desde la descripción de arriba (solo al editar,
          no al crear: el personaje aún no existe). Mientras no haya avatar, el carrusel
          usa el emoji. */}
      {!esNuevo && personaje && (
        <div className={styles.pjAvatar}>
          <div className={styles.pjAvatarPreview}>
            {avatarUrl ? (
              <img src={assetUrl(avatarUrl)} alt={`Avatar de ${personaje.nombre}`} />
            ) : (
              <span className={styles.pjAvatarEmoji}>{form.emoji.trim() || "🎭"}</span>
            )}
          </div>
          <div className={styles.pjAvatarCuerpo}>
            <strong>Imagen del carrusel</strong>
            <span className={styles.filaAyuda}>
              Genera una imagen con fondo transparente a partir de la descripción de arriba
              (cuesta una generación de Replicate). Mientras no la generes, se usa el emoji.
            </span>
            {errorAvatar && <p className={styles.testNo}>❌ {errorAvatar}</p>}
            <div className={styles.pjBarra}>
              <button
                type="button"
                className={styles.testBtn}
                onClick={() => void onGenerarAvatar()}
                disabled={avatarOcupado || !form.prompt_imagen.trim()}
              >
                {avatarOcupado ? "Generando…" : avatarUrl ? "🎨 Regenerar imagen" : "🎨 Generar imagen"}
              </button>
              {avatarUrl && (
                <button
                  type="button"
                  className={styles.testBtn}
                  onClick={() => void onQuitarAvatar()}
                  disabled={avatarOcupado}
                >
                  🗑 Quitar imagen
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <label className={styles.pjLabel}>
        Voz (ElevenLabs)
        <div className={styles.pjFilaControlBtn}>
          {hayVoces ? (
            <select
              className={styles.select}
              value={form.voz_id}
              onChange={(e) => {
                setErrorVoz(null);
                set("voz_id", e.target.value);
              }}
            >
              <option value="">Sin voz (solo texto)</option>
              {voces.map((v) => (
                <option key={v.voz_id} value={v.voz_id}>
                  {v.espanol ? "🇪🇸 " : ""}
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
              onChange={(e) => {
                setErrorVoz(null);
                set("voz_id", e.target.value);
              }}
            />
          )}
          <button
            type="button"
            className={styles.testBtn}
            onClick={() => void onProbarVoz()}
            disabled={!form.voz_id.trim() || probandoVoz}
            title="Reproduce una frase de prueba con esta voz"
          >
            {probandoVoz ? "🔊 Sonando…" : "🔊 Probar voz"}
          </button>
        </div>
        {hayVoces && (
          <span className={styles.filaAyuda}>
            🇪🇸 = ElevenLabs tiene el español verificado para esa voz. Las demás también
            pueden hablar español (el modelo es multilingüe), solo que ElevenLabs no lo
            ha verificado explícitamente.
          </span>
        )}
        {!hayVoces && vocesMsg && <span className={styles.filaAyuda}>{vocesMsg}</span>}
        {errorVoz && <span className={styles.testNo}>❌ {errorVoz}</span>}
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
        <button
          type="button"
          className="btn btn-secundario"
          onClick={onCancelar}
          disabled={guardando || docsOcupado}
        >
          Cancelar
        </button>
        <button
          type="button"
          className="btn btn-primario"
          onClick={() => void submit()}
          disabled={guardando || docsOcupado}
        >
          {guardando ? "Guardando…" : esNuevo ? "Crear personaje" : "Guardar cambios"}
        </button>
      </div>

      {/* Los documentos del RAG solo existen para un personaje ya creado. */}
      {!esNuevo && <DocumentosPanel personajeId={inicial.id} onOcupadoChange={setDocsOcupado} />}
    </div>
  );
}
