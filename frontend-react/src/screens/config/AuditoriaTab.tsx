/**
 * AuditoriaTab — Informe de auditoría de uso (Admin)
 * ===================================================
 *
 * Dos partes: (1) los AJUSTES de auditoría (activar, guardar contenido, retención)
 * con el ConfigForm genérico (categoría "auditoria"); (2) el INFORME: tabla de
 * eventos con filtro por tipo, exportación a CSV y purga manual por retención.
 *
 * Privacidad: es actividad de un menor. El texto de preguntas/respuestas solo
 * aparece si el adulto activó AUDITORIA_CONTENIDO; se purga por retención y con la
 * supresión de la cuenta de familia.
 */

import { useCallback, useEffect, useState } from "react";
import {
  BackendError,
  descargarAuditoriaCsv,
  getAuditoria,
  purgarAuditoria,
} from "../../api/client";
import type { AuditoriaEvento } from "../../api/types";
import styles from "../Settings.module.css";
import ConfigForm from "./ConfigForm";

const TIPOS: { valor: string; label: string }[] = [
  { valor: "", label: "Todos los eventos" },
  { valor: "login", label: "Accesos (login)" },
  { valor: "logout", label: "Cierres de sesión" },
  { valor: "signup", label: "Altas de familia" },
  { valor: "perfil", label: "Cambios de perfil/niños" },
  { valor: "escena", label: "Escenas generadas" },
  { valor: "pregunta", label: "Preguntas del chat" },
];

/** Formatea el detalle (JSON) a un texto corto legible. */
function resumenDetalle(ev: AuditoriaEvento): string {
  if (!ev.detalle) return "";
  try {
    const d = JSON.parse(ev.detalle) as Record<string, unknown>;
    return Object.entries(d)
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
      .join(" · ");
  } catch {
    return ev.detalle;
  }
}

export default function AuditoriaTab() {
  const [tipo, setTipo] = useState("");
  const [eventos, setEventos] = useState<AuditoriaEvento[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(async () => {
    setError(null);
    try {
      const res = await getAuditoria({ tipo: tipo || undefined, limite: 300 });
      setEventos(res.eventos);
      setTotal(res.total);
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }, [tipo]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function onExportar() {
    setError(null);
    setOkMsg(null);
    try {
      await descargarAuditoriaCsv({ tipo: tipo || undefined });
      setOkMsg("CSV exportado (revisa tus descargas).");
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  async function onPurgar() {
    if (!window.confirm("¿Aplicar la retención ahora y borrar los registros más antiguos?")) return;
    setError(null);
    setOkMsg(null);
    setOcupado(true);
    try {
      const { purgados } = await purgarAuditoria();
      setOkMsg(`${purgados} registro(s) purgado(s).`);
      await cargar();
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className={styles.cfgWrap}>
      <ConfigForm
        categorias={["auditoria"]}
        intro="Registro de la actividad de las familias para el informe de uso. Metadatos por defecto; el texto de preguntas y respuestas (dato sensible de un menor) solo se guarda si activas 'AUDITORIA_CONTENIDO'. Se borra por retención y con la cuenta."
      />

      <div className={styles.pjForm}>
        <h3 className={styles.pjFormTitulo}>🧾 Informe de actividad</h3>
        {error && <p className={styles.testNo}>❌ {error}</p>}
        {okMsg && <p className={styles.testOk}>✅ {okMsg}</p>}

        <div className={styles.docsUrlFila}>
          <select
            className={styles.select}
            value={tipo}
            aria-label="Filtrar por tipo de evento"
            onChange={(e) => setTipo(e.target.value)}
          >
            {TIPOS.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.label}
              </option>
            ))}
          </select>
          <button type="button" className={styles.testBtn} onClick={() => void cargar()}>
            🔄 Refrescar
          </button>
          <button type="button" className={styles.testBtn} onClick={() => void onExportar()}>
            ⬇️ Exportar CSV
          </button>
          <button
            type="button"
            className={styles.testBtn}
            onClick={() => void onPurgar()}
            disabled={ocupado}
          >
            🧹 Purgar antiguos
          </button>
        </div>

        <p className={styles.filaAyuda}>
          {eventos ? `${eventos.length} de ${total} evento(s)` : "Cargando…"}
        </p>

        {eventos && eventos.length > 0 ? (
          <div className={styles.auditWrap}>
            <table className={styles.auditTabla}>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Evento</th>
                  <th>Familia</th>
                  <th>Niño</th>
                  <th>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {eventos.map((ev) => (
                  <tr key={ev.id}>
                    <td className={styles.auditFecha}>
                      {new Date(ev.creado_en).toLocaleString("es-ES")}
                    </td>
                    <td>{ev.tipo}</td>
                    <td>{ev.familia_nombre ?? "—"}</td>
                    <td>{ev.nino ?? "—"}</td>
                    <td>
                      {resumenDetalle(ev)}
                      {ev.contenido && <div className={styles.auditContenido}>{ev.contenido}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : eventos ? (
          <p className={styles.filaAyuda}>No hay eventos registrados todavía.</p>
        ) : null}
      </div>
    </div>
  );
}
