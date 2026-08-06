/**
 * Chat — Conversación con el personaje (RAG), por texto y por voz
 * ================================================================
 *
 * Historial de burbujas (niño a la derecha, personaje a la izquierda), input
 * de texto con envío por botón o Enter, chips de preguntas rápidas e indicador
 * "está pensando..." mientras el backend responde.
 *
 * Voz de RESPUESTA: si la respuesta trae audio_base64, se reproduce sola al
 * llegar (y cada burbuja con audio tiene un botón para volver a escucharla).
 * Si es null, el chat sigue funcionando solo con texto (degradación).
 *
 * Voz de PREGUNTA: el botón de micrófono graba con MediaRecorder, sube el blob
 * a /api/transcribe y el texto entra por el MISMO flujo que una pregunta
 * escrita. Si no hay getUserMedia (contexto no seguro), ni permiso, ni
 * micrófono, el chat de texto no se ve afectado.
 *
 * El historial vive DENTRO de este componente: App lo remonta (via key) al
 * generar una escena nueva, con lo que la conversación empieza de cero.
 */

import { useEffect, useRef, useState } from "react";
import { askStream, BackendError, transcribe } from "../api/client";
import { sfx } from "../audio/sfx";
import QuickChips from "./QuickChips/QuickChips";
import styles from "./Chat.module.css";

interface Mensaje {
  autor: "nino" | "personaje" | "error";
  texto: string;
  /** Voz de la respuesta: una lista de mp3 (base64), UNO POR FRASE (streaming, H8). */
  audios?: string[];
  /** Fragmentos de la enciclopedia en los que se apoyó la respuesta. */
  fuentes?: string[];
}

interface Props {
  personajeId: string;
  /** Nombre visible del personaje (ej. "T-Rex"). */
  nombre: string;
  emoji: string;
  /** Nombre del niño que juega (multi-perfil, H9.2c): personaliza la respuesta. */
  nombreNino?: string | null;
  /** Sexo del niño ('chico'/'chica'/''): género gramatical de la respuesta. */
  sexoNino?: string | null;
}

/**
 * Formatos a intentar con MediaRecorder, de más a menos preferido. Scribe
 * deduce el formato de los propios bytes, así que cualquiera de ellos vale
 * (webm/ogg opus verificados en el spike; mp4 es el de Safari).
 */
const MIME_PREFERIDOS = [
  "audio/webm;codecs=opus",
  "audio/ogg;codecs=opus",
  "audio/webm",
  "audio/mp4",
];

/** ¿Se puede grabar aquí? getUserMedia solo existe en https o localhost. */
function micSoportado(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined"
  );
}

type MicEstado = "no-disponible" | "reposo" | "grabando" | "transcribiendo";

/** Lo que hay vivo mientras se graba (fuera del estado de React: no se pinta). */
interface Grabacion {
  recorder: MediaRecorder;
  stream: MediaStream;
  chunks: Blob[];
  cancelada: boolean;
}

export default function Chat({ personajeId, nombre, emoji, nombreNino, sexoNino }: Props) {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [pregunta, setPregunta] = useState("");
  const [pensando, setPensando] = useState(false);
  // `generando`: desde que se envía la pregunta hasta que TERMINA el stream (cubre
  // todo, no solo hasta el primer token como `pensando`). `hablando`: el personaje
  // está reproduciendo su voz. Ambos bloquean nuevas preguntas y el micrófono.
  const [generando, setGenerando] = useState(false);
  const [hablando, setHablando] = useState(false);
  const [micEstado, setMicEstado] = useState<MicEstado>(() =>
    micSoportado() ? "reposo" : "no-disponible",
  );
  const historialRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const grabacionRef = useRef<Grabacion | null>(null);
  // Cola de reproducción de audio (H8): las frases llegan por streaming de una en una
  // y se reproducen EN ORDEN, sin pisarse, aunque lleguen mientras suena la anterior.
  const colaAudioRef = useRef<string[]>([]);
  const reproduciendoRef = useRef(false);

  // Mientras se genera la respuesta, el personaje habla, se graba o se transcribe, no
  // se puede escribir/enviar ni lanzar otra pregunta: evita solapar preguntas y activar
  // el micrófono mientras el personaje aún está hablando.
  const ocupado =
    generando || hablando || micEstado === "grabando" || micEstado === "transcribiendo";

  // Foco correcto: al quedar libre el input (respuesta recibida, grabación
  // cancelada...), el cursor vuelve solo para seguir preguntando.
  useEffect(() => {
    if (!ocupado) inputRef.current?.focus();
  }, [ocupado]);

  // Auto-scroll: al añadir una burbuja, el historial baja solo hasta el final.
  useEffect(() => {
    const el = historialRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [mensajes, pensando, micEstado]);

  // Al desmontar el chat (nueva escena, empezar de nuevo): cortar el audio
  // que sonara y soltar el micrófono si estaba grabando.
  useEffect(() => {
    return () => {
      if (audioRef.current) audioRef.current.onended = null; // corta el encadenado de la cola
      audioRef.current?.pause();
      colaAudioRef.current = [];
      const grabacion = grabacionRef.current;
      if (grabacion) {
        grabacion.cancelada = true;
        try {
          grabacion.recorder.stop();
        } catch {
          // ya estaba parado
        }
        grabacion.stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  /** Reproduce el siguiente audio de la cola; al acabar, encadena el siguiente. */
  function bombearCola() {
    if (reproduciendoRef.current) return;
    const siguiente = colaAudioRef.current.shift();
    if (!siguiente) {
      setHablando(false); // cola vacía: el personaje deja de hablar
      return;
    }
    reproduciendoRef.current = true;
    setHablando(true); // suena una frase → el personaje está hablando
    const seguir = () => {
      reproduciendoRef.current = false;
      bombearCola();
    };
    try {
      const audio = new Audio(`data:audio/mpeg;base64,${siguiente}`);
      audioRef.current = audio;
      audio.onended = seguir;
      void audio.play().catch(() => seguir()); // si no puede sonar, sigue con el resto
    } catch {
      seguir();
    }
  }

  /** Encola una frase de audio (llega por streaming) y arranca la cola si hace falta. */
  function encolarAudio(audioBase64: string) {
    colaAudioRef.current.push(audioBase64);
    bombearCola();
  }

  /** Reproduce una respuesta completa (todas sus frases) desde cero: botón "escuchar". */
  function reproducirMensaje(audios: string[]) {
    if (audioRef.current) audioRef.current.onended = null; // corta el encadenado anterior
    audioRef.current?.pause();
    reproduciendoRef.current = false;
    colaAudioRef.current = [...audios];
    bombearCola();
  }

  function burbujaError(texto: string) {
    sfx("error"); // cubre todos los fallos suaves del chat, micro incluido
    setMensajes((previos) => [...previos, { autor: "error", texto }]);
  }

  /** Actualiza (fusiona) la ÚLTIMA burbuja del historial (la del personaje en curso). */
  function actualizarUltima(cambios: Partial<Mensaje>) {
    setMensajes((previos) => {
      if (previos.length === 0) return previos;
      const copia = [...previos];
      copia[copia.length - 1] = { ...copia[copia.length - 1], ...cambios };
      return copia;
    });
  }

  // -- Envío de una pregunta (escrita, transcrita o por chip: MISMO flujo) ----
  // Streaming (H8): el texto se pinta token a token y cada FRASE se oye en cuanto
  // llega, en vez de esperar en blanco a toda la respuesta.

  async function enviarPregunta(texto: string) {
    sfx("send"); // escrita, por chip o transcrita: todas entran por aquí
    setMensajes((previos) => [...previos, { autor: "nino", texto }]);
    setGenerando(true);
    setPensando(true);
    let creada = false; // ¿ya existe la burbuja del personaje que vamos rellenando?
    let acumulado = "";
    let fuentes: string[] = [];
    const audios: string[] = [];
    try {
      await askStream(personajeId, texto, {
        onFuentes: (f) => {
          fuentes = f; // llega ANTES que los tokens (evento meta); se usa al crear la burbuja
        },
        onToken: (trozo) => {
          acumulado += trozo;
          if (!creada) {
            // Primer token: quita el "pensando" y crea la burbuja del personaje.
            sfx("receive"); // SFX ligero, aparte de la voz mp3 del personaje
            setPensando(false);
            setMensajes((previos) => [
              ...previos,
              { autor: "personaje", texto: acumulado, audios: [], fuentes },
            ]);
            creada = true;
          } else {
            actualizarUltima({ texto: acumulado });
          }
        },
        onAudio: (audioBase64) => {
          audios.push(audioBase64);
          encolarAudio(audioBase64);
          actualizarUltima({ audios: [...audios] }); // para el botón "volver a escuchar"
        },
        onFin: (respuesta) => {
          if (respuesta) {
            acumulado = respuesta;
            actualizarUltima({ texto: acumulado });
          }
        },
        onError: (mensaje) => burbujaError(mensaje),
      }, undefined, nombreNino, sexoNino);
    } catch (exc) {
      const mensaje =
        exc instanceof BackendError
          ? exc.message
          : "No he podido responder. Inténtalo otra vez.";
      burbujaError(mensaje);
      setPregunta(texto); // la pregunta vuelve al input: no se pierde
    } finally {
      setPensando(false);
      setGenerando(false); // stream terminado; si aún queda voz sonando, `hablando` sigue bloqueando
    }
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault(); // Enter en el input también envía
    const texto = pregunta.trim();
    if (!texto || ocupado) return;
    setPregunta("");
    void enviarPregunta(texto);
  }

  /** Chip de pregunta rápida: entra por el mismo flujo que una escrita. */
  function onChip(texto: string) {
    if (ocupado) return;
    setPregunta("");
    void enviarPregunta(texto);
  }

  // -- Micrófono (pregunta por voz) --------------------------------------------

  async function empezarGrabacion() {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      // Permiso denegado o sin micrófono: el chat de texto sigue intacto.
      burbujaError(
        "No pude usar el micrófono. Revisa el permiso del navegador o escribe tu pregunta. 🎤",
      );
      return;
    }
    const mime = MIME_PREFERIDOS.find((m) => MediaRecorder.isTypeSupported(m));
    const recorder = mime
      ? new MediaRecorder(stream, { mimeType: mime })
      : new MediaRecorder(stream);
    const grabacion: Grabacion = { recorder, stream, chunks: [], cancelada: false };
    grabacionRef.current = grabacion;

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) grabacion.chunks.push(event.data);
    };
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop()); // suelta el micro
      grabacionRef.current = null;
      if (grabacion.cancelada) return;
      const tipo = recorder.mimeType || "audio/webm";
      void transcribirYEnviar(new Blob(grabacion.chunks, { type: tipo }), tipo);
    };

    recorder.start();
    setMicEstado("grabando");
  }

  /** Para la grabación; si `cancelar`, descarta la toma sin transcribir. */
  function pararGrabacion(cancelar: boolean) {
    const grabacion = grabacionRef.current;
    if (!grabacion) return;
    grabacion.cancelada = cancelar;
    setMicEstado(cancelar ? "reposo" : "transcribiendo");
    try {
      grabacion.recorder.stop();
    } catch {
      grabacionRef.current = null;
      setMicEstado("reposo");
    }
  }

  async function transcribirYEnviar(blob: Blob, tipo: string) {
    try {
      const ext = tipo.includes("ogg") ? "ogg" : tipo.includes("mp4") ? "m4a" : "webm";
      const texto = (await transcribe(blob, `grabacion.${ext}`)).trim();
      if (!texto) {
        burbujaError("No te oí bien. Prueba otra vez. 🎤");
        return;
      }
      // Se envía DIRECTAMENTE, como una pregunta escrita: más inmediato para el niño
      // (sin paso de "¿has dicho esto?"). Si el ASR se equivoca, el niño repregunta.
      void enviarPregunta(texto);
    } catch {
      // El backend rechazó o no pudo transcribir el audio.
      burbujaError("No pude escucharte bien. Inténtalo otra vez. 🎤");
    } finally {
      setMicEstado("reposo");
    }
  }

  function onMicClick() {
    // No arrancar el micro mientras el personaje genera o habla (defensa extra al
    // `disabled` del botón). Estando grabando, siempre se puede parar/enviar.
    if (micEstado === "reposo" && !generando && !hablando) void empezarGrabacion();
    else if (micEstado === "grabando") pararGrabacion(false);
  }

  const micTitulo = {
    "no-disponible":
      "El micrófono necesita una página segura (https o localhost) y un navegador compatible",
    reposo: "Toca para hablar; toca otra vez para enviar",
    grabando: "Grabando... toca para enviar",
    transcribiendo: "Escuchando lo que dijiste...",
  }[micEstado];

  return (
    <section className={styles.chat}>
      <h3 className={styles.titulo}>💬 Habla con {nombre}</h3>

      <div className={styles.historial} ref={historialRef}>
        {mensajes.length === 0 && !pensando && (
          <p className={styles.vacio}>
            ¡Pregúntale lo que quieras! (usa los botones de abajo o escribe)
          </p>
        )}

        {mensajes.map((mensaje, i) => (
          <div key={i} className={`${styles.burbuja} ${styles[mensaje.autor]}`}>
            <span className={styles.autor}>
              {mensaje.autor === "nino" && "🧒 TÚ"}
              {mensaje.autor === "personaje" && `${emoji} ${nombre.toUpperCase()}`}
              {mensaje.autor === "error" && "⚠️ UPS"}
            </span>
            <p className={styles.texto}>{mensaje.texto}</p>

            {mensaje.audios && mensaje.audios.length > 0 && (
              <button
                type="button"
                className={styles.audio}
                aria-label="Volver a escuchar la respuesta"
                onClick={() => reproducirMensaje(mensaje.audios as string[])}
              >
                🔊 Volver a escuchar
              </button>
            )}

            {mensaje.fuentes && mensaje.fuentes.length > 0 && (
              <details className={styles.fuentes}>
                <summary>📚 ¿De dónde lo he sacado?</summary>
                <ul>
                  {mensaje.fuentes.map((fuente, j) => (
                    <li key={j}>{fuente}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        ))}

        {micEstado === "transcribiendo" && (
          <div className={`${styles.burbuja} ${styles.nino} ${styles.pensando}`}>
            <p className={styles.texto}>👂 Escuchando lo que dijiste...</p>
          </div>
        )}

        {pensando && (
          <div className={`${styles.burbuja} ${styles.personaje} ${styles.pensando}`}>
            <p className={styles.texto}>🤔 {nombre} está pensando...</p>
          </div>
        )}
      </div>

      <QuickChips disabled={ocupado} onElegir={onChip} />

      <form className={styles.form} onSubmit={onSubmit}>
        <input
          ref={inputRef}
          type="text"
          className={styles.input}
          placeholder={
            micEstado === "grabando"
              ? "Grabando tu pregunta... 🔴"
              : "Escribe tu pregunta... (ej. ¿Qué comes?)"
          }
          value={pregunta}
          onChange={(e) => setPregunta(e.target.value)}
          disabled={ocupado}
          autoFocus
        />

        <button
          type="button"
          className={`${styles.mic}${micEstado === "grabando" ? ` ${styles.grabando}` : ""}`}
          aria-label={micTitulo}
          title={micTitulo}
          disabled={
            micEstado === "no-disponible" ||
            micEstado === "transcribiendo" ||
            generando ||
            hablando
          }
          onClick={onMicClick}
        >
          {micEstado === "grabando" ? "⏹" : "🎙️"}
        </button>

        {micEstado === "grabando" && (
          <button
            type="button"
            className={styles.cancelar}
            aria-label="Cancelar la grabación"
            title="Cancelar la grabación"
            onClick={() => pararGrabacion(true)}
          >
            ✖
          </button>
        )}

        {/* Icono en móvil, palabra a partir de tablet: lo decide el CSS, y el
            aria-label mantiene el nombre de la acción en los dos casos.
            data-no-sfx: enviar ya suena con "send" desde `enviarPregunta`. */}
        <button
          type="submit"
          data-no-sfx
          className={styles.enviar}
          aria-label="Preguntar"
          disabled={ocupado || !pregunta.trim()}
        >
          <span className={styles.enviarIco} aria-hidden="true">
            ➤
          </span>
          <span className={styles.enviarTexto}>Preguntar</span>
        </button>
      </form>
    </section>
  );
}
