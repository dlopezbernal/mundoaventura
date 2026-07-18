/**
 * DocumentosPanel — Visor y gestor de documentos del RAG de un personaje (Hito 5/8)
 * ===================================================================================
 *
 * Se muestra dentro de la edición de un personaje. Permite, sin terminal, saber en
 * todo momento qué "sabe" el personaje y gestionarlo por completo:
 *   - Ver los documentos ya indexados (fichero, origen, si se tradujo, fechas).
 *   - BUSCAR/filtrar la lista (en cliente, sin llamada nueva al backend).
 *   - SUBIR uno o varios .pdf/.txt/.md a la vez.
 *   - INGERIR un artículo de Wikipedia por URL.
 *   - Por documento: VER/EDITAR el texto indexado, DESCARGAR el original,
 *     COPIARLO a otro(s) personaje(s) (copia independiente) y BORRARLO.
 *   - REINDEXAR este personaje a mano.
 *
 * Si al subir/ingerir/copiar ya existe un documento con ese nombre, el backend
 * responde 409 (esConflictoDocumento) en vez de pisarlo en silencio: se ofrece
 * confirmar sobrescritura antes de reintentar.
 *
 * El idioma de cada documento se detecta automáticamente (DeepL) al guardar:
 * no hay ningún control manual — si no está en inglés, se traduce solo.
 */

import { useEffect, useState } from "react";
import {
  addDocumentoUrl,
  BackendError,
  copiarDocumento,
  deleteDocumento,
  descargarDocumento,
  esConflictoDocumento,
  getDocumentoContenido,
  getDocumentos,
  getPersonajes,
  reindexPersonaje,
  updateDocumentoContenido,
  uploadDocumentos,
} from "../../api/client";
import type { DocumentoDTO, PersonajeDTO } from "../../api/types";
import { MENSAJE_PROCESANDO } from "../../components/Modal/Modal";
import styles from "../Settings.module.css";

interface Props {
  personajeId: string;
  /** Notifica al contenedor (el Modal de edición) si hay una operación en curso,
   * para que pueda bloquear el resto del diálogo mientras dura. */
  onOcupadoChange?: (ocupado: boolean) => void;
}

export default function DocumentosPanel({ personajeId, onOcupadoChange }: Props) {
  const [docs, setDocs] = useState<DocumentoDTO[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [url, setUrl] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [expandidoId, setExpandidoId] = useState<number | null>(null);
  // Catálogo de personajes para el selector "copiar a…" (se carga una vez, perezoso).
  const [personajes, setPersonajes] = useState<PersonajeDTO[] | null>(null);

  useEffect(() => {
    onOcupadoChange?.(ocupado);
  }, [ocupado, onOcupadoChange]);

  async function cargar() {
    setError(null);
    try {
      setDocs(await getDocumentos(personajeId));
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  useEffect(() => {
    void cargar();
    setExpandidoId(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personajeId]);

  async function personajesParaCopiar(): Promise<PersonajeDTO[]> {
    if (personajes) return personajes;
    const lista = await getPersonajes();
    setPersonajes(lista);
    return lista;
  }

  /** Envuelve una acción con estado ocupado + refresco + mensajes. */
  async function correr(accion: () => Promise<string>) {
    setOcupado(true);
    setError(null);
    setOkMsg(null);
    try {
      const msg = await accion();
      await cargar();
      setOkMsg(msg);
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  /**
   * Como `correr`, pero SIN tragarse el error: si `accion` lanza, lo relanza tras
   * ponerlo en pantalla. Lo usan los flujos que necesitan reaccionar al 409 de
   * conflicto (subir 1 fichero, ingerir URL) para ofrecer sobrescribir.
   */
  async function correrOLanzar(accion: () => Promise<string>): Promise<void> {
    setOcupado(true);
    setError(null);
    setOkMsg(null);
    try {
      const msg = await accion();
      await cargar();
      setOkMsg(msg);
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
      throw exc;
    } finally {
      setOcupado(false);
    }
  }

  function onSubir(e: React.ChangeEvent<HTMLInputElement>) {
    const archivos = Array.from(e.target.files ?? []);
    e.target.value = ""; // permite volver a subir los mismos ficheros
    if (archivos.length === 0) return;

    function resumen(r: Awaited<ReturnType<typeof uploadDocumentos>>, sobrescrito: boolean): string {
      if (r.documentos) {
        const okCount = r.documentos.length;
        const erroresTxt = r.errores?.length
          ? ` · ${r.errores.length} fallo(s): ${r.errores.map((er) => `"${er.nombre}" (${er.detalle})`).join(", ")}`
          : "";
        return `${okCount} de ${archivos.length} documento(s) subido(s).${erroresTxt}`;
      }
      const doc = r.documento!;
      const accion = sobrescrito ? "sobrescrito" : "añadido";
      return `Documento "${doc.nombre_archivo}" ${accion}${doc.traducido ? " (traducido a inglés)" : ""}.`;
    }

    // Conflicto (409) solo puede darse cuando se sube UN fichero: con varios, el
    // backend reporta cada choque dentro de `errores` en vez de abortar todo.
    correrOLanzar(async () => resumen(await uploadDocumentos(personajeId, archivos, false), false)).catch((exc) => {
      if (
        archivos.length === 1 &&
        esConflictoDocumento(exc) &&
        window.confirm(`Ya existe un documento llamado "${archivos[0].name}" para este personaje. ¿Sobrescribirlo?`)
      ) {
        void correr(async () => resumen(await uploadDocumentos(personajeId, archivos, true), true));
      }
    });
  }

  function onAnadirUrl() {
    const limpia = url.trim();
    if (!limpia) return;
    correrOLanzar(async () => {
      const doc = await addDocumentoUrl(personajeId, limpia);
      setUrl("");
      return `Artículo añadido como "${doc.nombre_archivo}"${doc.traducido ? " (traducido)" : ""}.`;
    }).catch((exc) => {
      if (
        esConflictoDocumento(exc) &&
        window.confirm("Ya existe un documento con ese nombre para este personaje. ¿Sobrescribirlo?")
      ) {
        void correr(async () => {
          const doc = await addDocumentoUrl(personajeId, limpia, true);
          setUrl("");
          return `Artículo "${doc.nombre_archivo}" sobrescrito${doc.traducido ? " (traducido)" : ""}.`;
        });
      }
    });
  }

  function onBorrar(doc: DocumentoDTO) {
    if (!window.confirm(`¿Borrar el documento "${doc.nombre_archivo}"?`)) return;
    void correr(async () => {
      await deleteDocumento(personajeId, doc.id);
      if (expandidoId === doc.id) setExpandidoId(null);
      return `Documento "${doc.nombre_archivo}" borrado.`;
    });
  }

  function onReindexar() {
    void correr(async () => {
      const r = await reindexPersonaje(personajeId);
      return `Reindexado: ${r.archivos} archivo(s) → ${r.chunks} fragmento(s).`;
    });
  }

  const docsFiltrados = (docs ?? []).filter((d) =>
    d.nombre_archivo.toLowerCase().includes(busqueda.trim().toLowerCase()),
  );

  return (
    <div className={styles.docsPanel}>
      <h4 className={styles.docsTitulo}>📄 Documentos del RAG</h4>
      <p className={styles.filaAyuda}>
        Estos textos son de donde el personaje saca lo que sabe. Serán traducidos a
        inglés si no lo están, para mejor comprensión de la IA.
      </p>

      {/* Subir ficheros (uno o varios) */}
      <div className={styles.docsAcciones}>
        <label className={`${styles.testBtn} ${ocupado ? styles.docsDisabled : ""}`}>
          ⬆️ Subir .pdf / .txt / .md
          <input
            type="file"
            accept=".pdf,.txt,.md"
            multiple
            hidden
            disabled={ocupado}
            onChange={onSubir}
          />
        </label>
        <button type="button" className={styles.testBtn} onClick={onReindexar} disabled={ocupado}>
          ♻️ Reindexar este personaje
        </button>
      </div>

      {/* Ingesta por URL */}
      <div className={styles.docsUrlFila}>
        <input
          className={styles.input}
          value={url}
          placeholder="https://simple.wikipedia.org/wiki/…"
          spellCheck={false}
          disabled={ocupado}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button
          type="button"
          className={styles.testBtn}
          onClick={onAnadirUrl}
          disabled={ocupado || !url.trim()}
        >
          🌐 Añadir de Wikipedia
        </button>
      </div>

      {ocupado && <p className={styles.filaAyuda}>{MENSAJE_PROCESANDO}</p>}
      {error && <p className={styles.testNo}>❌ {error}</p>}
      {okMsg && <p className={styles.testOk}>✅ {okMsg}</p>}

      {/* Buscar / filtrar */}
      {docs && docs.length > 0 && (
        <input
          className={`${styles.input} ${styles.docsBuscar}`}
          value={busqueda}
          placeholder="🔎 Buscar por nombre de fichero…"
          spellCheck={false}
          onChange={(e) => setBusqueda(e.target.value)}
        />
      )}

      {/* Lista de documentos */}
      {docs && docsFiltrados.length > 0 ? (
        <ul className={styles.docsLista}>
          {docsFiltrados.map((d) => (
            <DocumentoFila
              key={d.id}
              doc={d}
              personajeId={personajeId}
              expandido={expandidoId === d.id}
              onToggle={() => setExpandidoId(expandidoId === d.id ? null : d.id)}
              onBorrar={() => onBorrar(d)}
              onCambiado={(msg) => {
                setOkMsg(msg);
                setError(null);
                void cargar();
              }}
              onError={(msg) => {
                setError(msg);
                setOkMsg(null);
              }}
              cargarPersonajes={personajesParaCopiar}
            />
          ))}
        </ul>
      ) : (
        docs &&
        (busqueda ? (
          <p className={styles.filaAyuda}>Ningún documento coincide con "{busqueda}".</p>
        ) : (
          <p className={styles.filaAyuda}>Aún no hay documentos para este personaje.</p>
        ))
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fila expandible de un documento: ver/editar contenido, descargar, copiar, borrar
// ---------------------------------------------------------------------------
interface FilaProps {
  doc: DocumentoDTO;
  personajeId: string;
  expandido: boolean;
  onToggle: () => void;
  onBorrar: () => void;
  onCambiado: (msg: string) => void;
  onError: (msg: string) => void;
  cargarPersonajes: () => Promise<PersonajeDTO[]>;
}

function DocumentoFila({
  doc,
  personajeId,
  expandido,
  onToggle,
  onBorrar,
  onCambiado,
  onError,
  cargarPersonajes,
}: FilaProps) {
  const [contenido, setContenido] = useState<string | null>(null);
  const [editable, setEditable] = useState(true);
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [mostrarCopiar, setMostrarCopiar] = useState(false);
  const [destinos, setDestinos] = useState<Set<string>>(new Set());
  const [opciones, setOpciones] = useState<PersonajeDTO[] | null>(null);
  const [copiando, setCopiando] = useState(false);

  useEffect(() => {
    if (!expandido || contenido !== null || cargando) return;
    setCargando(true);
    getDocumentoContenido(personajeId, doc.id)
      .then((r) => {
        setContenido(r.contenido);
        setEditable(r.editable);
      })
      .catch((exc) => onError(exc instanceof BackendError ? exc.message : String(exc)))
      .finally(() => setCargando(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expandido]);

  async function onGuardar() {
    if (contenido === null) return;
    setGuardando(true);
    try {
      await updateDocumentoContenido(personajeId, doc.id, contenido);
      onCambiado(`Documento "${doc.nombre_archivo}" actualizado.`);
    } catch (exc) {
      onError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setGuardando(false);
    }
  }

  async function onDescargar() {
    try {
      await descargarDocumento(personajeId, doc.id, doc.nombre_archivo);
    } catch (exc) {
      onError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  async function onAbrirCopiar() {
    setMostrarCopiar(true);
    if (!opciones) {
      const lista = await cargarPersonajes();
      setOpciones(lista.filter((p) => p.id !== personajeId));
    }
  }

  function toggleDestino(id: string) {
    setDestinos((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function onConfirmarCopiar(sobrescribir = false) {
    if (destinos.size === 0) return;
    setCopiando(true);
    try {
      const r = await copiarDocumento(personajeId, doc.id, Array.from(destinos), sobrescribir);
      const okCount = r.copiados.length;
      if (r.errores.length > 0) {
        const conflicto = r.errores.some((e) => e.detalle.includes("Ya existe un documento"));
        const detalle = r.errores.map((e) => `${e.personaje_id} (${e.detalle})`).join(", ");
        onError(
          `Copiado a ${okCount} personaje(s); ${r.errores.length} fallo(s): ${detalle}` +
            (conflicto ? " — marca sobrescribir e inténtalo de nuevo si quieres forzarlo." : ""),
        );
      } else {
        onCambiado(`Documento copiado a ${okCount} personaje(s).`);
      }
      setMostrarCopiar(false);
      setDestinos(new Set());
    } catch (exc) {
      onError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setCopiando(false);
    }
  }

  const editado = doc.actualizado_en !== doc.creado_en;

  return (
    <li className={styles.docsItem}>
      <div className={styles.docsItemHead}>
        <button
          type="button"
          className={styles.docsToggle}
          onClick={onToggle}
          aria-label={expandido ? "Contraer" : "Expandir"}
        >
          {expandido ? "▾" : "▸"}
        </button>
        <span className={styles.docsNombre}>
          {doc.origen === "url" ? "🌐" : "📄"} {doc.nombre_archivo}
        </span>
        {doc.copiado_de_id !== null && (
          <span className={styles.docsBadgeCopia}>copiado de #{doc.copiado_de_id}</span>
        )}
        <span className={styles.docsMeta}>
          {doc.traducido ? "traducido" : doc.idioma_original === "en" ? "inglés" : "—"}
          {editado ? ` · editado ${new Date(doc.actualizado_en).toLocaleDateString()}` : ""}
        </span>
        <button
          type="button"
          className={styles.pjBorrar}
          onClick={onBorrar}
          aria-label={`Borrar ${doc.nombre_archivo}`}
        >
          🗑
        </button>
      </div>

      {expandido && (
        <div className={styles.docsDetalle}>
          {cargando && <p className={styles.filaAyuda}>Cargando contenido…</p>}
          {contenido !== null && (
            <>
              <textarea
                className={`${styles.textarea} ${styles.docsTextarea}`}
                value={contenido}
                readOnly={!editable}
                onChange={(e) => setContenido(e.target.value)}
              />
              {!editable && (
                <p className={styles.filaAyuda}>
                  Los PDF no se pueden editar aquí (es un texto extraído de solo lectura); bórralo
                  y sube uno nuevo si necesitas cambiarlo.
                </p>
              )}
              <div className={styles.docsDetalleAcciones}>
                {editable && (
                  <button type="button" className={styles.testBtn} onClick={onGuardar} disabled={guardando}>
                    💾 Guardar cambios
                  </button>
                )}
                <button type="button" className={styles.testBtn} onClick={onDescargar}>
                  ⬇️ Descargar
                </button>
                <button type="button" className={styles.testBtn} onClick={onAbrirCopiar}>
                  📋 Copiar a…
                </button>
              </div>

              {mostrarCopiar && (
                <div className={styles.docsCopiarLista}>
                  {!opciones ? (
                    <p className={styles.filaAyuda}>Cargando personajes…</p>
                  ) : opciones.length === 0 ? (
                    <p className={styles.filaAyuda}>No hay otros personajes a los que copiar.</p>
                  ) : (
                    <>
                      {opciones.map((p) => (
                        <label key={p.id} className={styles.docsCheck}>
                          <input
                            type="checkbox"
                            checked={destinos.has(p.id)}
                            onChange={() => toggleDestino(p.id)}
                          />
                          {p.emoji ?? "👤"} {p.nombre}
                        </label>
                      ))}
                      <div className={styles.docsDetalleAcciones}>
                        <button
                          type="button"
                          className={styles.testBtn}
                          onClick={() => void onConfirmarCopiar(false)}
                          disabled={copiando || destinos.size === 0}
                        >
                          ✅ Copiar
                        </button>
                        <button
                          type="button"
                          className={styles.testBtn}
                          onClick={() => setMostrarCopiar(false)}
                          disabled={copiando}
                        >
                          Cancelar
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </li>
  );
}
