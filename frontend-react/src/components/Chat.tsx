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
import { ask, BackendError, transcribe } from "../api/client";
import QuickChips from "./QuickChips/QuickChips";
import styles from "./Chat.module.css";

interface Mensaje {
  autor: "nino" | "personaje" | "error";
  texto: string;
  /** Voz de la respuesta (mp3 en base64), solo en burbujas del personaje. */
  audioBase64?: string | null;
  /** Fragmentos de la enciclopedia en los que se apoyó la respuesta. */
  fuentes?: string[];
}

interface Props {
  personajeId: string;
  /** Nombre visible del personaje (ej. "T-Rex"). */
  nombre: string;
  emoji: string;
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

export default function Chat({ personajeId, nombre, emoji }: Props) {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [pregunta, setPregunta] = useState("");
  const [pensando, setPensando] = useState(false);
  const [micEstado, setMicEstado] = useState<MicEstado>(() =>
    micSoportado() ? "reposo" : "no-disponible",
  );
  const historialRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const grabacionRef = useRef<Grabacion | null>(null);

  // Mientras se responde, se graba o se transcribe, no se puede escribir/enviar
  // (evita solapar una pregunta escrita con una hablada, como en Flet).
  const ocupado =
    pensando || micEstado === "grabando" || micEstado === "transcribiendo";

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
      audioRef.current?.pause();
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

  function reproducir(audioBase64: string) {
    // Corta la respuesta anterior si aún sonaba y arranca la nueva. Un fallo
    // NUNCA rompe la UI: el texto ya está visible, solo se pierde el audio.
    try {
      audioRef.current?.pause();
      const audio = new Audio(`data:audio/mpeg;base64,${audioBase64}`);
      audioRef.current = audio;
      void audio.play().catch((exc: unknown) => {
        console.warn("No se pudo reproducir la voz de la respuesta:", exc);
      });
    } catch (exc) {
      console.warn("No se pudo reproducir la voz de la respuesta:", exc);
    }
  }

  function burbujaError(texto: string) {
    setMensajes((previos) => [...previos, { autor: "error", texto }]);
  }

  // -- Envío de una pregunta (escrita, transcrita o por chip: MISMO flujo) ----

  async function enviarPregunta(texto: string) {
    setMensajes((previos) => [...previos, { autor: "nino", texto }]);
    setPensando(true);
    try {
      const respuesta = await ask(personajeId, texto);
      setMensajes((previos) => [
        ...previos,
        {
          autor: "personaje",
          texto: respuesta.respuesta,
          audioBase64: respuesta.audio_base64,
          fuentes: respuesta.fuentes,
        },
      ]);
      if (respuesta.audio_base64) reproducir(respuesta.audio_base64);
    } catch (exc) {
      const mensaje =
        exc instanceof BackendError
          ? exc.message
          : "No he podido responder. Inténtalo otra vez.";
      burbujaError(mensaje);
      setPregunta(texto); // la pregunta vuelve al input: no se pierde
    } finally {
      setPensando(false);
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
      // La pregunta hablada entra al MISMO flujo que una escrita.
      await enviarPregunta(texto);
    } catch {
      // El backend (Scribe) rechazó o no pudo transcribir el audio.
      burbujaError("No pude escucharte bien. Inténtalo otra vez. 🎤");
    } finally {
      setMicEstado("reposo");
    }
  }

  function onMicClick() {
    if (micEstado === "reposo") void empezarGrabacion();
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

            {mensaje.audioBase64 && (
              <button
                type="button"
                className={styles.audio}
                aria-label="Volver a escuchar la respuesta"
                onClick={() => reproducir(mensaje.audioBase64 as string)}
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
            pensando
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

        <button
          type="submit"
          className={styles.enviar}
          disabled={ocupado || !pregunta.trim()}
        >
          Preguntar
        </button>
      </form>
    </section>
  );
}
