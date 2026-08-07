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
 *   - Botón "Consultar saldo": cuánta cuota queda, con barra por dimensión
 *     (caracteres, tokens, peticiones). Solo se pinta donde el saldo se puede
 *     consultar de verdad — lo decide el backend con `saldo_consultable`, no una
 *     lista de proveedores repetida aquí. Donde no se puede se ofrece el panel
 *     del proveedor, y donde no aplica (SMTP) no se ofrece nada.
 *     Ver backend/services/saldo_service.py.
 *   - Guardar → escribe en el .env de forma segura y aplica en caliente.
 *
 * Toda la lógica sensible (escribir el .env, no filtrar secretos) vive en el
 * backend (secrets_service); aquí solo se orquesta la UI.
 */

import { useEffect, useState } from "react";
import { BackendError, getApis, revealApi, saldoApi, saveApis, testApi } from "../../api/client";
import type { ApiProviderStatus, ApiSaldoResult, ApiTestResult } from "../../api/types";
import styles from "../Settings.module.css";

type EstadoTest = { cargando: boolean; res?: ApiTestResult };
type EstadoSaldo = { cargando: boolean; res?: ApiSaldoResult };

/** Color de la barra según lo consumido: tranquilo, aviso, alarma. */
function claseRelleno(porcentaje: number): string {
  if (porcentaje >= 90) return styles.saldoRellenoAlto;
  if (porcentaje >= 75) return styles.saldoRellenoMedio;
  return "";
}

export default function ApisTab() {
  const [proveedores, setProveedores] = useState<ApiProviderStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Valor tecleado por proveedor (vacío = no cambiar esa clave).
  const [valores, setValores] = useState<Record<string, string>>({});
  // ¿Se muestra en claro el campo de cada proveedor?
  const [revelado, setRevelado] = useState<Record<string, boolean>>({});
  const [tests, setTests] = useState<Record<string, EstadoTest>>({});
  const [saldos, setSaldos] = useState<Record<string, EstadoSaldo>>({});
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

  /** Consulta la cuota que queda. Para el LLM esto GASTA una petición mínima
   *  (es la única que devuelve las cabeceras de cuota), así que solo se dispara
   *  con el clic: nunca al montar ni al cambiar de pestaña. */
  async function consultarSaldo(proveedor: string) {
    setSaldos((prev) => ({ ...prev, [proveedor]: { cargando: true } }));
    try {
      const res = await saldoApi(proveedor);
      setSaldos((prev) => ({ ...prev, [proveedor]: { cargando: false, res } }));
    } catch (exc) {
      setSaldos((prev) => ({
        ...prev,
        [proveedor]: {
          cargando: false,
          res: {
            proveedor,
            disponible: true,
            ok: false,
            mensaje: exc instanceof BackendError ? exc.message : String(exc),
            medidas: [],
            panel_url: null,
          },
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
      // El saldo mostrado era el de la clave ANTERIOR: con otra clave (u otra
      // cuenta) ya no dice nada. Se limpia igual que el resultado del test.
      setSaldos({});
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
        Introduce aquí las claves de las plataformas de IA. Son necesarias para que la
        aplicación funcione.
      </p>

      {proveedores.map((p) => {
        const test = tests[p.proveedor];
        const saldo = saldos[p.proveedor];
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
              {/* El botón solo aparece donde el saldo se puede consultar de verdad
                  (lo dice el backend con `saldo_consultable`). Donde no —Replicate—
                  se ofrece directamente su panel, y donde no aplica —SMTP— nada. */}
              {p.saldo_consultable ? (
                <button
                  type="button"
                  className={styles.testBtn}
                  onClick={() => void consultarSaldo(p.proveedor)}
                  disabled={saldo?.cargando || !p.configurado}
                  title={
                    p.configurado
                      ? "Consulta cuánta cuota queda en este proveedor"
                      : "Configura primero la clave"
                  }
                >
                  {saldo?.cargando ? "Consultando…" : "📊 Consultar saldo"}
                </button>
              ) : (
                p.panel_url && (
                  <a
                    className={styles.saldoPanel}
                    href={p.panel_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    📊 Ver el saldo en el panel del proveedor ↗
                  </a>
                )
              )}
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

              {saldo?.res && (
                <div className={styles.saldoBox}>
                  {/* Tres desenlaces distintos, y se distinguen a propósito:
                      ✅ hay cifras · ❌ el proveedor lo expone pero falló (hay algo
                      que arreglar) · ℹ️ no lo expone por API (no es un error). */}
                  <span
                    className={
                      saldo.res.ok
                        ? styles.saldoMensaje
                        : saldo.res.disponible
                          ? styles.testNo
                          : styles.saldoMensaje
                    }
                  >
                    {saldo.res.ok ? "📊" : saldo.res.disponible ? "❌" : "ℹ️"}{" "}
                    {saldo.res.mensaje}
                  </span>

                  {(saldo.res.medidas ?? []).map((m) => (
                    <div key={m.etiqueta} className={styles.saldoMedida}>
                      <div className={styles.saldoFila}>
                        <span className={styles.saldoEtiqueta}>{m.etiqueta}</span>
                        <span>
                          {m.porcentaje != null
                            ? `${String(m.porcentaje).replace(".", ",")} % usado`
                            : "sin límite declarado"}
                          {m.renueva ? ` · ${m.renueva}` : ""}
                        </span>
                      </div>
                      {m.porcentaje != null && (
                        <div className={styles.saldoBarra}>
                          <div
                            className={`${styles.saldoRelleno} ${claseRelleno(m.porcentaje)}`}
                            style={{ width: `${Math.min(100, Math.max(0, m.porcentaje))}%` }}
                          />
                        </div>
                      )}
                    </div>
                  ))}

                  {saldo.res.panel_url && (
                    <a
                      className={styles.saldoPanel}
                      href={saldo.res.panel_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Ver el saldo en el panel del proveedor ↗
                    </a>
                  )}
                </div>
              )}
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
