/**
 * DocumentosPanel — Documentos del RAG de un personaje (Hito 5)
 * =============================================================
 *
 * Se muestra dentro de la edición de un personaje. Permite, sin terminal:
 *   - Ver los documentos ya indexados (fichero, origen, si se tradujo).
 *   - SUBIR un .pdf/.txt/.md.
 *   - INGERIR un artículo de Wikipedia por URL.
 *   - BORRAR un documento (reindexa solo a este personaje).
 *   - REINDEXAR este personaje a mano.
 *
 * Aviso importante (que pide el proyecto): siempre es mejor adjuntar el material
 * EN INGLÉS para que la IA lo entienda mejor. Si el contenido está en español, el
 * backend lo traduce con DeepL al guardar (marca la casilla si YA está en inglés
 * para no gastar cuota de DeepL, sobre todo en documentos largos).
 */

import { useEffect, useState } from "react";
import {
  addDocumentoUrl,
  BackendError,
  deleteDocumento,
  getDocumentos,
  reindexPersonaje,
  uploadDocumento,
} from "../../api/client";
import type { DocumentoDTO } from "../../api/types";
import styles from "../Settings.module.css";

interface Props {
  personajeId: string;
}

export default function DocumentosPanel({ personajeId }: Props) {
  const [docs, setDocs] = useState<DocumentoDTO[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  // "Ya está en inglés" (no traducir con DeepL). Compartido por subida y URL.
  const [yaEnIngles, setYaEnIngles] = useState(true);
  const [url, setUrl] = useState("");

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personajeId]);

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

  function onSubir(e: React.ChangeEvent<HTMLInputElement>) {
    const archivo = e.target.files?.[0];
    e.target.value = ""; // permite volver a subir el mismo fichero
    if (!archivo) return;
    void correr(async () => {
      const doc = await uploadDocumento(personajeId, archivo, yaEnIngles);
      return `Documento "${doc.nombre_archivo}" añadido${doc.traducido ? " (traducido a inglés)" : ""}.`;
    });
  }

  function onAnadirUrl() {
    const limpia = url.trim();
    if (!limpia) return;
    void correr(async () => {
      const doc = await addDocumentoUrl(personajeId, limpia, yaEnIngles);
      setUrl("");
      return `Artículo añadido como "${doc.nombre_archivo}"${doc.traducido ? " (traducido)" : ""}.`;
    });
  }

  function onBorrar(doc: DocumentoDTO) {
    if (!window.confirm(`¿Borrar el documento "${doc.nombre_archivo}"?`)) return;
    void correr(async () => {
      await deleteDocumento(personajeId, doc.id);
      return `Documento "${doc.nombre_archivo}" borrado.`;
    });
  }

  function onReindexar() {
    void correr(async () => {
      const r = await reindexPersonaje(personajeId);
      return `Reindexado: ${r.archivos} archivo(s) → ${r.chunks} fragmento(s).`;
    });
  }

  return (
    <div className={styles.docsPanel}>
      <h4 className={styles.docsTitulo}>📄 Documentos del RAG</h4>
      <p className={styles.filaAyuda}>
        Estos textos son de donde el personaje saca lo que sabe. Es mejor subirlos{" "}
        <b>en inglés</b> (la IA los entiende mejor); si están en español, se traducen
        solos con DeepL al guardar.
      </p>

      <label className={styles.docsCheck}>
        <input
          type="checkbox"
          checked={yaEnIngles}
          onChange={(e) => setYaEnIngles(e.target.checked)}
        />
        El material ya está en inglés (no traducir · ahorra cuota de DeepL)
      </label>

      {/* Subir fichero */}
      <div className={styles.docsAcciones}>
        <label className={`${styles.testBtn} ${ocupado ? styles.docsDisabled : ""}`}>
          ⬆️ Subir .pdf / .txt / .md
          <input
            type="file"
            accept=".pdf,.txt,.md"
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

      {ocupado && <p className={styles.filaAyuda}>Procesando… (traducir/indexar puede tardar)</p>}
      {error && <p className={styles.testNo}>❌ {error}</p>}
      {okMsg && <p className={styles.testOk}>✅ {okMsg}</p>}

      {/* Lista de documentos */}
      {docs && docs.length > 0 ? (
        <ul className={styles.docsLista}>
          {docs.map((d) => (
            <li key={d.id} className={styles.docsItem}>
              <span className={styles.docsNombre}>
                {d.origen === "url" ? "🌐" : "📄"} {d.nombre_archivo}
              </span>
              <span className={styles.docsMeta}>
                {d.traducido ? "traducido" : d.idioma_original === "en" ? "inglés" : "—"}
              </span>
              <button
                type="button"
                className={styles.pjBorrar}
                onClick={() => onBorrar(d)}
                disabled={ocupado}
                aria-label={`Borrar ${d.nombre_archivo}`}
              >
                🗑
              </button>
            </li>
          ))}
        </ul>
      ) : (
        docs && <p className={styles.filaAyuda}>Aún no hay documentos para este personaje.</p>
      )}
    </div>
  );
}
