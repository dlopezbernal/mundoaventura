/**
 * Chat — Conversación con el personaje (RAG)
 * ===========================================
 *
 * Historial de burbujas (niño a la derecha, personaje a la izquierda), input
 * de texto con envío por botón o Enter, e indicador "está pensando..." mientras
 * el backend responde. Replica el chat de legacy/frontend-flet/main.py.
 *
 * Voz: si la respuesta trae audio_base64, se reproduce sola al llegar (y cada
 * burbuja con audio tiene un botón para volver a escucharla). Si es null, el
 * chat sigue funcionando solo con texto (degradación, igual que en Flet).
 *
 * El historial vive DENTRO de este componente: App lo remonta (via key) al
 * generar una escena nueva, con lo que la conversación empieza de cero.
 */

import { useEffect, useRef, useState } from "react";
import { ask, BackendError } from "../api/client";
import "./Chat.css";

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

export default function Chat({ personajeId, nombre, emoji }: Props) {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [pregunta, setPregunta] = useState("");
  const [pensando, setPensando] = useState(false);
  const historialRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Auto-scroll: al añadir una burbuja, el historial baja solo hasta el final.
  useEffect(() => {
    const el = historialRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [mensajes, pensando]);

  // Al desmontar el chat (nueva escena, empezar de nuevo) se corta el audio.
  useEffect(() => {
    return () => audioRef.current?.pause();
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

  async function enviar() {
    const texto = pregunta.trim();
    if (!texto || pensando) return;
    setMensajes((previos) => [...previos, { autor: "nino", texto }]);
    setPregunta("");
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
      setMensajes((previos) => [...previos, { autor: "error", texto: mensaje }]);
      setPregunta(texto); // la pregunta vuelve al input: no se pierde
    } finally {
      setPensando(false);
    }
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault(); // Enter en el input también envía
    void enviar();
  }

  return (
    <section className="chat">
      <h3 className="chat-titulo">💬 Habla con {nombre}</h3>

      <div className="chat-historial" ref={historialRef}>
        {mensajes.length === 0 && !pensando && (
          <p className="chat-vacio">
            ¡Pregúntale lo que quieras! (ej. ¿Qué comes?)
          </p>
        )}

        {mensajes.map((mensaje, i) => (
          <div key={i} className={`burbuja burbuja-${mensaje.autor}`}>
            <span className="burbuja-autor">
              {mensaje.autor === "nino" && "🧒 Tú"}
              {mensaje.autor === "personaje" && `${emoji} ${nombre}`}
              {mensaje.autor === "error" && "⚠️ Ups"}
            </span>
            <p className="burbuja-texto">{mensaje.texto}</p>

            {mensaje.audioBase64 && (
              <button
                type="button"
                className="burbuja-audio"
                aria-label="Volver a escuchar la respuesta"
                onClick={() => reproducir(mensaje.audioBase64 as string)}
              >
                🔊 Volver a escuchar
              </button>
            )}

            {mensaje.fuentes && mensaje.fuentes.length > 0 && (
              <details className="burbuja-fuentes">
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

        {pensando && (
          <div className="burbuja burbuja-personaje burbuja-pensando">
            <p className="burbuja-texto">🤔 {nombre} está pensando...</p>
          </div>
        )}
      </div>

      <form className="chat-form" onSubmit={onSubmit}>
        <input
          type="text"
          className="chat-input"
          placeholder="Escribe tu pregunta... (ej. ¿Qué comes?)"
          value={pregunta}
          onChange={(e) => setPregunta(e.target.value)}
          disabled={pensando}
          autoFocus
        />
        <button
          type="submit"
          className="chat-enviar"
          disabled={pensando || !pregunta.trim()}
        >
          Preguntar
        </button>
      </form>
    </section>
  );
}
