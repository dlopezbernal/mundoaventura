/**
 * pwa/instalar.ts — Instalar la app desde la propia página
 * =========================================================
 *
 * Chrome no deja abrir el diálogo de instalación cuando a uno le apetece: avisa
 * con el evento `beforeinstallprompt` de que AHORA se puede, y hay que guardarse
 * ese evento para dispararlo después desde un gesto del usuario.
 *
 * Ese aviso llega poco después de cargar la página, y puede adelantarse a que
 * React haya pintado la pantalla de login. Por eso el listener se registra en el
 * propio módulo (al importarlo, es decir al arrancar la app) y no dentro de un
 * `useEffect`: si esperásemos al montaje del componente, en algunos arranques el
 * evento ya habría pasado y el botón no aparecería nunca.
 *
 * Los componentes leen el estado con `useSyncExternalStore(suscribir, sePuedeInstalar)`.
 *
 * Requisitos para que el evento llegue: manifest válido, service worker activo,
 * HTTPS (o localhost) y que la app NO esté ya instalada. Safari y Firefox no lo
 * implementan; ahí sencillamente no hay botón, que es el comportamiento correcto
 * (en iOS se instala desde Compartir → Añadir a pantalla de inicio).
 */

/** El evento de Chrome, que no está en las definiciones estándar del DOM. */
interface EventoInstalacion extends Event {
  prompt(): Promise<void>;
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

let pendiente: EventoInstalacion | null = null;
const suscriptores = new Set<() => void>();

function avisar() {
  suscriptores.forEach((f) => f());
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (evento) => {
    // Sin esto, Chrome muestra su propio aviso por debajo y perdemos el control
    // de dónde y cuándo ofrecer la instalación.
    evento.preventDefault();
    pendiente = evento as EventoInstalacion;
    avisar();
  });
  // Ya instalada: el botón sobra.
  window.addEventListener("appinstalled", () => {
    pendiente = null;
    avisar();
  });
}

/** ¿Se puede ofrecer la instalación ahora mismo? */
export function sePuedeInstalar(): boolean {
  return pendiente !== null;
}

/** Suscribe un aviso de cambio (para `useSyncExternalStore`). */
export function suscribirInstalacion(alCambiar: () => void): () => void {
  suscriptores.add(alCambiar);
  return () => suscriptores.delete(alCambiar);
}

/** ¿Está la app corriendo YA como app instalada (y no en una pestaña)? */
export function estaInstalada(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(display-mode: standalone)").matches === true
  );
}

/**
 * Abre el diálogo de instalación. Devuelve `true` si el usuario aceptó.
 *
 * El evento es de UN SOLO USO: `prompt()` no se puede llamar dos veces sobre el
 * mismo, así que se descarta al usarlo y el botón desaparece. Si el usuario
 * cancela, Chrome vuelve a emitir `beforeinstallprompt` más adelante (otra
 * visita o recarga) y el botón reaparece solo.
 */
export async function instalar(): Promise<boolean> {
  const evento = pendiente;
  if (!evento) return false;
  pendiente = null;
  avisar();
  await evento.prompt();
  const { outcome } = await evento.userChoice;
  return outcome === "accepted";
}
