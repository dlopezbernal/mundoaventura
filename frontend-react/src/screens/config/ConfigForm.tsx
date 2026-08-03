/**
 * ConfigForm — Formulario genérico de ajustes del motor (Hito 3)
 * =============================================================
 *
 * Pinta, a partir de los METADATOS que envía el backend (settings_service),
 * un control adecuado para cada ajuste, SIN saber de antemano cuáles son:
 *
 *   - bool             → interruptor (toggle)
 *   - opciones (lista) → desplegable (select)
 *   - multilinea       → área de texto (prompts)
 *   - int / float      → campo numérico con min/max/paso
 *   - str              → campo de texto
 *
 * Recibe la lista de CATEGORÍAS que debe mostrar, así la misma pieza sirve para
 * la pestaña "IA" (rag/chunking/llm/prompts) y "General" (debug). Guarda solo los
 * ajustes MODIFICADOS y los aplica en caliente (PUT /api/config).
 *
 * Importante (decisión de diseño del proyecto): el umbral del Evaluator es una
 * DISTANCIA COSENO 0–2 y se edita como tal. NO se convierte a porcentaje en
 * ningún punto: el número que ve el adulto es el mismo que usa el backend.
 */

import { useEffect, useMemo, useState } from "react";
import { BackendError, getConfig, saveConfig } from "../../api/client";
import type { SettingMeta } from "../../api/types";
import styles from "../Settings.module.css";

type ValorAjuste = number | string | boolean;

interface Props {
  /** Categorías (settings_service) que se muestran en esta pestaña. */
  categorias: string[];
  /** Texto introductorio opcional de la pestaña. */
  intro?: string;
}

export default function ConfigForm({ categorias, intro }: Props) {
  const [ajustes, setAjustes] = useState<SettingMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Cambios sin guardar: clave → valor nuevo (solo lo que el adulto tocó).
  const [borrador, setBorrador] = useState<Record<string, ValorAjuste>>({});
  const [guardando, setGuardando] = useState(false);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  async function cargar() {
    setError(null);
    try {
      const todos = await getConfig();
      setAjustes(todos.filter((a) => categorias.includes(a.categoria)));
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  useEffect(() => {
    void cargar();
    // Recargamos si cambian las categorías (cambio de pestaña reusa el componente).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categorias.join(",")]);

  function setValor(clave: string, valor: ValorAjuste) {
    setBorrador((prev) => ({ ...prev, [clave]: valor }));
    setOkMsg(null);
  }

  /** Valor a mostrar en el control: el del borrador si se tocó, si no el vigente. */
  function valorActual(a: SettingMeta): ValorAjuste {
    return a.clave in borrador ? borrador[a.clave] : a.valor;
  }

  const hayCambios = Object.keys(borrador).length > 0;

  // ¿Algún ajuste modificado exige reindexar? (avisamos antes de guardar).
  const avisoReindex = useMemo(() => {
    if (!ajustes) return false;
    return ajustes.some((a) => a.clave in borrador && a.requiere_reindex);
  }, [ajustes, borrador]);

  async function guardar() {
    if (!hayCambios) return;
    setGuardando(true);
    setError(null);
    setOkMsg(null);
    try {
      const reindex = await saveConfig(borrador);
      setBorrador({});
      await cargar();
      setOkMsg(
        reindex.length > 0
          ? `Guardado. Para que surta efecto el cambio de troceado, reconstruye el índice: python -m backend.ingest (afecta a: ${reindex.join(", ")}).`
          : "Ajustes guardados y aplicados.",
      );
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setGuardando(false);
    }
  }

  function descartar() {
    setBorrador({});
    setOkMsg(null);
    setError(null);
  }

  if (error && !ajustes) {
    return (
      <div className={styles.panel}>
        <p className={styles.filaAyuda}>No se pudo cargar la configuración: {error}</p>
        <button type="button" className="btn btn-secundario" onClick={() => void cargar()}>
          Reintentar
        </button>
      </div>
    );
  }

  if (!ajustes) {
    return (
      <div className={styles.panel}>
        <p className={styles.filaAyuda}>Cargando…</p>
      </div>
    );
  }

  return (
    <div className={styles.cfgWrap}>
      {intro && <p className={styles.apisIntro}>{intro}</p>}

      {ajustes.map((a) => (
        <Campo
          key={a.clave}
          meta={a}
          valor={valorActual(a)}
          modificado={a.clave in borrador}
          onChange={(v) => setValor(a.clave, v)}
        />
      ))}

      {avisoReindex && (
        <p className={styles.reindexAviso}>
          ⚠️ Has cambiado un ajuste de troceado. Tras guardar, hará falta reconstruir
          el índice con <code>python -m backend.ingest</code> para que tenga efecto.
        </p>
      )}
      {error && <p className={styles.testNo}>❌ {error}</p>}
      {okMsg && <p className={styles.testOk}>✅ {okMsg}</p>}

      <div className={styles.footer}>
        <button
          type="button"
          className="btn btn-secundario"
          onClick={descartar}
          disabled={!hayCambios || guardando}
        >
          Descartar cambios
        </button>
        <button
          type="button"
          className="btn btn-primario"
          onClick={() => void guardar()}
          disabled={!hayCambios || guardando}
        >
          {guardando ? "Guardando…" : "💾 Guardar ajustes"}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Un ajuste: etiqueta + ayuda + el control adecuado a su tipo.
// ---------------------------------------------------------------------------
interface CampoProps {
  meta: SettingMeta;
  valor: number | string | boolean;
  modificado: boolean;
  onChange: (valor: number | string | boolean) => void;
}

function Campo({ meta, valor, modificado, onChange }: CampoProps) {
  const esMultilinea = meta.multilinea === true;

  return (
    <div className={`${styles.cfgCampo} ${esMultilinea ? styles.cfgCampoAncho : ""}`}>
      <div className={styles.cfgCabecera}>
        <span className={styles.filaEtiqueta}>
          {meta.clave}
          {modificado && <span className={styles.cfgPunto} title="Sin guardar">●</span>}
        </span>
        <Control meta={meta} valor={valor} onChange={onChange} />
      </div>
      {meta.ayuda && <p className={styles.filaAyuda}>{meta.ayuda}</p>}
    </div>
  );
}

function Control({ meta, valor, onChange }: Omit<CampoProps, "modificado">) {
  // 1) Booleano → interruptor.
  if (meta.tipo === "bool") {
    const on = valor === true;
    return (
      <button
        type="button"
        className={`${styles.toggle} ${on ? styles.toggleOn : ""}`}
        onClick={() => onChange(!on)}
        role="switch"
        aria-checked={on}
        aria-label={meta.clave}
      >
        <span className={styles.toggleKnob} />
      </button>
    );
  }

  // 2) Opciones cerradas → desplegable.
  if (meta.opciones && meta.opciones.length > 0) {
    return (
      <select
        className={styles.select}
        value={String(valor)}
        onChange={(e) => onChange(e.target.value)}
      >
        {meta.opciones.map((op) => (
          <option key={op} value={op}>
            {op}
          </option>
        ))}
      </select>
    );
  }

  // 3) Texto largo (prompts) → área de texto.
  if (meta.multilinea) {
    return (
      <textarea
        className={styles.textarea}
        value={String(valor)}
        rows={6}
        spellCheck={false}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  // 4) Numérico (int/float) → campo con min/max/paso.
  if (meta.tipo === "int" || meta.tipo === "float") {
    const paso = meta.paso ?? (meta.tipo === "int" ? 1 : 0.01);
    return (
      <input
        type="number"
        className={styles.input}
        value={String(valor)}
        min={meta.min ?? undefined}
        max={meta.max ?? undefined}
        step={paso}
        onChange={(e) => {
          const n = meta.tipo === "int" ? parseInt(e.target.value, 10) : parseFloat(e.target.value);
          onChange(Number.isNaN(n) ? valor : n);
        }}
      />
    );
  }

  // 5) Texto corto → campo de texto.
  return (
    <input
      type="text"
      className={styles.input}
      value={String(valor)}
      spellCheck={false}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
