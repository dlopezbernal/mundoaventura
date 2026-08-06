/**
 * audio/sfx.ts — Efectos de sonido de la interfaz (Arcade Holo)
 * ==============================================================
 *
 * Los SFX se SINTETIZAN con la Web Audio API: no hay mp3/wav que empaquetar ni
 * dependencias nuevas. Un único `AudioContext` con una ganancia maestra baja
 * (0.14) y un helper `nota()` que toca un oscilador con envolvente exponencial
 * (ataque de 12 ms, caída hasta el final) y glisando opcional.
 *
 * Ojo con dos cosas:
 *   · Autoplay — el navegador crea el contexto SUSPENDIDO hasta el primer gesto
 *     del usuario. Por eso `asegurar()` llama a `resume()` en cada sonido: como
 *     todos salen de un evento de interacción, el primer clic lo despierta (es
 *     también lo que hace que funcione en iOS).
 *   · La voz del personaje NO se sintetiza aquí: es el mp3 de ElevenLabs y lo
 *     reproduce `Chat.tsx` con un `Audio()` normal. Pero SÍ obedece al mismo
 *     interruptor: para el niño hay un único botón de sonido, y si lo apaga
 *     espera silencio, no "silencio a medias". `Chat` consulta `sonidoActivo()`
 *     antes de reproducir y se suscribe con `suscribirSonido` para callar en el
 *     acto si se silencia a mitad de una frase.
 *
 * El interruptor global se persiste en `localStorage` (`mdt_sonido`) y lo maneja
 * el botón 🔊/🔇 del HUD. Es un store mínimo (`sonidoActivo`/`suscribirSonido`)
 * para `useSyncExternalStore`: la preferencia vive en el módulo, no en el estado
 * de un componente, porque la leen dos sitios independientes (el HUD y el chat).
 */

export type SfxNombre =
  | "click" // pulsar cualquier botón (listener delegado en App)
  | "select" // confirmar y avanzar (¡GENERAR!, SIGUIENTE, elegir perfil…)
  | "back" // retroceder o cerrar
  | "move" // girar el carrusel
  | "open" // abrir un panel de adulto
  | "send" // enviar una pregunta en el chat
  | "receive" // llega la respuesta del personaje
  | "done" // la escena ha terminado de generarse
  | "error"; // acción no permitida o fallo suave

const CLAVE_PREFERENCIA = "mdt_sonido";
const VOLUMEN_MAESTRO = 0.14;

let contexto: AudioContext | null = null;
let maestro: GainNode | null = null;
/** Se marca si el navegador no tiene Web Audio: no se reintenta en cada sonido. */
let sinAudio = false;

function leerPreferencia(): boolean {
  try {
    // Por defecto ENCENDIDO: solo se guarda marca cuando el usuario silencia.
    return localStorage.getItem(CLAVE_PREFERENCIA) !== "0";
  } catch {
    return true; // localStorage puede no estar disponible
  }
}

let activo = leerPreferencia();

/** Suscritos al interruptor (HUD y chat), para `useSyncExternalStore`. */
const oyentes = new Set<() => void>();

/**
 * ¿Está encendido el sonido? Cubre TODO lo que suena: los efectos de esta
 * fábrica y la voz del personaje que reproduce `Chat`.
 */
export function sonidoActivo(): boolean {
  return activo;
}

/** Avisa de los cambios del interruptor. Devuelve la función para darse de baja. */
export function suscribirSonido(oyente: () => void): () => void {
  oyentes.add(oyente);
  return () => {
    oyentes.delete(oyente);
  };
}

/** Enciende/apaga el sonido (efectos + voz) y lo recuerda en el dispositivo. */
export function activarSonido(encendido: boolean): void {
  activo = encendido;
  try {
    if (encendido) localStorage.removeItem(CLAVE_PREFERENCIA);
    else localStorage.setItem(CLAVE_PREFERENCIA, "0");
  } catch {
    /* localStorage puede no estar disponible */
  }
  // Al reactivar, un "select" de confirmación: se oye que ha vuelto el sonido.
  if (encendido) sfx("select");
  oyentes.forEach((oyente) => oyente());
}

function asegurar(): AudioContext | null {
  if (!contexto && !sinAudio) {
    const Constructor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;
    if (!Constructor) {
      sinAudio = true;
      return null;
    }
    try {
      contexto = new Constructor();
      maestro = contexto.createGain();
      maestro.gain.value = VOLUMEN_MAESTRO;
      maestro.connect(contexto.destination);
    } catch {
      sinAudio = true;
      return null;
    }
  }
  if (contexto?.state === "suspended") {
    // Si aún no ha habido gesto, `resume()` rechaza: no es un error que reportar.
    void contexto.resume().catch(() => {});
  }
  return contexto;
}

/**
 * Una nota: oscilador + envolvente.
 * @param frecuencia Hz de salida
 * @param duracion segundos
 * @param tipo forma de onda
 * @param pico ganancia máxima de la envolvente
 * @param retraso segundos de espera antes de sonar (para encadenar notas)
 * @param glisando Hz de destino (barrido de frecuencia durante la nota)
 */
function nota(
  frecuencia: number,
  duracion: number,
  tipo: OscillatorType = "triangle",
  pico = 0.5,
  retraso = 0,
  glisando?: number,
): void {
  const ac = asegurar();
  if (!ac || !maestro) return;
  const t = ac.currentTime + retraso;
  const osc = ac.createOscillator();
  const ganancia = ac.createGain();
  osc.type = tipo;
  osc.frequency.setValueAtTime(frecuencia, t);
  if (glisando) osc.frequency.exponentialRampToValueAtTime(glisando, t + duracion);
  // Las rampas exponenciales no pueden pasar por 0: se arranca en 0.0001.
  ganancia.gain.setValueAtTime(0.0001, t);
  ganancia.gain.exponentialRampToValueAtTime(pico, t + 0.012);
  ganancia.gain.exponentialRampToValueAtTime(0.0001, t + duracion);
  osc.connect(ganancia);
  ganancia.connect(maestro);
  osc.start(t);
  osc.stop(t + duracion + 0.03);
}

/** Reproduce un efecto del catálogo (no hace nada si el sonido está apagado). */
export function sfx(nombre: SfxNombre): void {
  if (!activo) return;
  switch (nombre) {
    case "click":
      nota(660, 0.05, "square", 0.4);
      break;
    case "select": // dos notas ascendentes: "adelante"
      nota(523, 0.08, "triangle", 0.55);
      nota(784, 0.12, "triangle", 0.45, 0.07);
      break;
    case "back": // las mismas dos notas, descendentes: "atrás"
      nota(523, 0.08, "triangle", 0.5);
      nota(392, 0.12, "triangle", 0.5, 0.07);
      break;
    case "move":
      nota(440, 0.06, "triangle", 0.45, 0, 560);
      break;
    case "open":
      nota(220, 0.18, "sawtooth", 0.35, 0, 620);
      break;
    case "send":
      nota(880, 0.06, "square", 0.4);
      break;
    case "receive":
      nota(600, 0.12, "sine", 0.45, 0, 960);
      break;
    case "done": // arpegio Do-Mi-Sol-Do: la escena está lista
      [523, 659, 784, 1047].forEach((f, i) => nota(f, 0.2, "triangle", 0.5, i * 0.09));
      break;
    case "error":
      nota(200, 0.22, "sawtooth", 0.45, 0, 120);
      break;
  }
}

/**
 * Fanfarria de bienvenida: la escala Do-Mi-Sol-Do-Mi subiendo, y encima un
 * acorde final sostenido (Sol agudo + Do de cuerpo + Do brillante). Es el único
 * sonido "largo" (~1,1 s) del catálogo, y por eso no está en `sfx()`: solo suena
 * al activar la cuenta, una vez por familia.
 *
 * Reutiliza el motor de arriba a propósito — un `AudioContext` propio sería un
 * segundo canal fuera del interruptor 🔊/🔇 y del volumen maestro.
 */
export function sfxBienvenida(): void {
  if (!activo) return;
  [523, 659, 784, 1047, 1319].forEach((f, i) => nota(f, 0.22, "triangle", 0.5, i * 0.1));
  nota(1568, 0.6, "triangle", 0.4, 0.52);
  nota(1047, 0.6, "sine", 0.3, 0.52);
  nota(2093, 0.5, "triangle", 0.22, 0.62);
}

/**
 * Bucle de "generando": un arpegio ascendente cada 210 ms mientras se crea la
 * escena. Devuelve la función para pararlo — llámala SIEMPRE (también al fallar
 * la generación), o el bucle se queda sonando.
 *
 * El interruptor se consulta en cada tic, no al arrancar: así, silenciar a mitad
 * de una generación calla el bucle en el acto.
 */
export function bucleGenerando(): () => void {
  let i = 0;
  const id = window.setInterval(() => {
    if (!activo) return;
    const f = 420 + (i % 6) * 90;
    nota(f, 0.12, "sine", 0.24, 0, f + 140);
    i++;
  }, 210);
  return () => window.clearInterval(id);
}
