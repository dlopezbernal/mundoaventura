/**
 * ApisTab — Pestaña "APIs" del menú de configuración (Hito 2)
 * ===========================================================
 *
 * Permite a cualquier persona configurar las claves de los 3 proveedores
 * (Replicate, DeepL, ElevenLabs) SIN abrir el .env:
 *
 *   - Muestra el estado de cada proveedor (configurado / falta) y la clave
 *     ENMASCARADA (nunca la completa).
 *   - Campo para pegar una clave nueva, con icono de ojo 👁 para revelar/ocultar
 *     (revelar la clave actual es una petición aparte y autorizada al backend).
 *   - Botón "Probar conexión" por proveedor (✅ / ❌ + mensaje).
 *   - Guardar → escribe en el .env de forma segura y aplica en caliente.
 *
 * Toda la lógica sensible (escribir el .env, no filtrar secretos) vive en el
 * backend (secrets_service); aquí solo se orquesta la UI.
 */

import { useEffect, useState } from "react";
import { BackendError, getApis, revealApi, saveApis, testApi } from "../../api/client";
import type { ApiProviderStatus, ApiTestResult } from "../../api/types";
import styles from "../Settings.module.css";

type EstadoTest = { cargando: boolean; res?: ApiTestResult };

export default function ApisTab() {
  const [proveedores, setProveedores] = useState<ApiProviderStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Valor tecleado por proveedor (vacío = no cambiar esa clave).
  const [valores, setValores] = useState<Record<string, string>>({});
  // ¿Se muestra en claro el campo de cada proveedor?
  const [revelado, setRevelado] = useState<Record<string, boolean>>({});
  const [tests, setTests] = useState<Record<string, EstadoTest>>({});
  const [guardando, setGuardando] = useState(false);
  const [guardadoOk, setGuardadoOk] = useState(false);

  async function cargar() {
    setError(null);
    try {
      setProveedores(await getApis());
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    }
  }

  useEffect(() => {
    void cargar();
  }, []);

  function setValor(proveedor: string, valor: string) {
    setValores((prev) => ({ ...prev, [proveedor]: valor }));
    setGuardadoOk(false);
  }

  /** Ojo 👁: revela u oculta el campo. Al revelar por 1ª vez, trae la clave actual. */
  async function alternarOjo(p: ApiProviderStatus) {
    const yaVisible = revelado[p.proveedor];
    if (!yaVisible && !valores[p.proveedor] && p.configurado) {
      try {
        const clave = await revealApi(p.proveedor);
        if (clave) setValores((prev) => ({ ...prev, [p.proveedor]: clave }));
      } catch {
        /* si falla revelar, simplemente mostramos el campo (vacío) */
      }
    }
    setRevelado((prev) => ({ ...prev, [p.proveedor]: !yaVisible }));
  }

  async function probar(proveedor: string) {
    setTests((prev) => ({ ...prev, [proveedor]: { cargando: true } }));
    try {
      const res = await testApi(proveedor);
      setTests((prev) => ({ ...prev, [proveedor]: { cargando: false, res } }));
    } catch (exc) {
      setTests((prev) => ({
        ...prev,
        [proveedor]: {
          cargando: false,
          res: { ok: false, mensaje: exc instanceof BackendError ? exc.message : String(exc) },
        },
      }));
    }
  }

  async function guardar() {
    // Solo se envían los proveedores con una clave nueva escrita.
    const cambios: Record<string, string> = {};
    for (const [proveedor, valor] of Object.entries(valores)) {
      if (valor.trim()) cambios[proveedor] = valor.trim();
    }
    if (Object.keys(cambios).length === 0) return;

    setGuardando(true);
    setError(null);
    setGuardadoOk(false);
    try {
      const actualizados = await saveApis(cambios);
      setProveedores(actualizados);
      setValores({});
      setRevelado({});
      setTests({});
      setGuardadoOk(true);
    } catch (exc) {
      setError(exc instanceof BackendError ? exc.message : String(exc));
    } finally {
      setGuardando(false);
    }
  }

  if (error && !proveedores) {
    return (
      <div className={styles.panel}>
        <p className={styles.filaAyuda}>No se pudo cargar el estado de las APIs: {error}</p>
        <button type="button" className="btn btn-secundario" onClick={() => void cargar()}>
          Reintentar
        </button>
      </div>
    );
  }

  if (!proveedores) {
    return <div className={styles.panel}><p className={styles.filaAyuda}>Cargando…</p></div>;
  }

  const hayCambios = Object.values(valores).some((v) => v.trim());

  return (
    <div className={styles.apisWrap}>
      <p className={styles.apisIntro}>
        Pega aquí las claves de las plataformas de IA. Se guardan solo en este
        equipo (en el archivo <code>.env</code>) y nunca se muestran completas.
      </p>

      {proveedores.map((p) => {
        const test = tests[p.proveedor];
        return (
          <div key={p.proveedor} className={styles.apiCard}>
            <div className={styles.apiHead}>
              <span className={styles.apiName}>{p.nombre}</span>
              <span
                className={`${styles.badge} ${p.configurado ? styles.badgeOk : styles.badgeNo}`}
              >
                {p.configurado ? "✓ Configurada" : "✗ Falta"}
              </span>
            </div>

            <div className={styles.keyRow}>
              <input
                className={styles.keyInput}
                type={revelado[p.proveedor] ? "text" : "password"}
                value={valores[p.proveedor] ?? ""}
                placeholder={p.enmascarado ?? "Pega tu clave…"}
                onChange={(e) => setValor(p.proveedor, e.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                className={styles.eyeBtn}
                onClick={() => void alternarOjo(p)}
                aria-label={revelado[p.proveedor] ? "Ocultar" : "Revelar"}
                title={revelado[p.proveedor] ? "Ocultar" : "Revelar clave actual"}
              >
                {revelado[p.proveedor] ? "🙈" : "👁"}
              </button>
            </div>

            <div className={styles.apiActions}>
              <button
                type="button"
                className={styles.testBtn}
                onClick={() => void probar(p.proveedor)}
                disabled={test?.cargando}
              >
                {test?.cargando ? "Probando…" : "🔌 Probar conexión"}
              </button>
              {test?.res && (
                <span className={test.res.ok ? styles.testOk : styles.testNo}>
                  {test.res.ok ? "✅" : "❌"} {test.res.mensaje}
                </span>
              )}
              <a
                className={styles.helpLink}
                href={p.ayuda_url}
                target="_blank"
                rel="noreferrer"
              >
                ¿Cómo consigo la clave? ↗
              </a>
            </div>
          </div>
        );
      })}

      {error && <p className={styles.testNo}>❌ {error}</p>}
      {guardadoOk && <p className={styles.testOk}>✅ Claves guardadas y aplicadas.</p>}

      <div className={styles.footer}>
        <button
          type="button"
          className="btn btn-primario"
          onClick={() => void guardar()}
          disabled={guardando || !hayCambios}
        >
          {guardando ? "Guardando…" : "💾 Guardar claves"}
        </button>
      </div>
    </div>
  );
}
