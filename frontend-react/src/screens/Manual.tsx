/**
 * Manual — Guía de uso de MundoAventura (manual de usuario en pantalla)
 * =====================================================================
 *
 * Una sola pantalla, de solo lectura, con dos secciones separadas: una para el
 * NIÑO (cómo jugar: los 3 pasos + el chat) y otra para el ADULTO (crear la cuenta
 * de familia y qué se hace desde ⚙️ Configuración). La zona 🛡️ Admin queda fuera
 * a propósito: es la configuración global de la instalación, no la de una familia.
 *
 * Se abre desde el botón 📖 del HUD y también desde la pantalla de login, para que
 * el adulto pueda leer qué hace la app ANTES de dar su correo y crear la cuenta.
 *
 * No llama a la API ni guarda estado: es contenido estático. El fondo (rejilla +
 * scanlines) lo pone App, no esta pantalla.
 */

import { useEffect } from "react";
import { sfx } from "../audio/sfx";
import Marca from "../components/Marca/Marca";
import Steps from "../components/Steps/Steps";
import styles from "./Manual.module.css";

interface Props {
  /** Cierra el manual y vuelve a donde se estaba (flujo o login). */
  onCerrar: () => void;
}

/** Preguntas de muestra: las mismas que ve el niño como chips en el chat. */
const EJEMPLOS = ["¿Dónde vives?", "¿Tienes amigos?", "Cuéntame algo", "¿Qué comes?"];

export default function Manual({ onCerrar }: Props) {
  // El manual se abre desde cualquier punto de la página: empezar por el principio.
  // "auto" (no smooth) para que el salto sea inmediato al montar.
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, []);

  return (
    <article className={styles.pagina} aria-label="Manual de usuario">
      {/* Barra pegajosa: solo rótulo y salida. Los saltos a cada sección viven en las
          dos "puertas" de la portada, unas líneas más abajo; repetirlos aquí era ruido. */}
      <div className={styles.nav}>
        <span className={styles.navRotulo}>
          <span aria-hidden="true">📖</span> MANUAL DE USUARIO
        </span>
        <button
          type="button"
          data-no-sfx
          className={styles.cerrar}
          onClick={() => {
            sfx("back");
            onCerrar();
          }}
        >
          ✕ Cerrar
        </button>
      </div>

      <header className={styles.portada}>
        <p className={styles.kicker}>◇ MANUAL DE USUARIO · MUNDOAVENTURA ◇</p>
        <div className={styles.marca}>
          <Marca size={92} className={styles.marcaMark} title="MundoAventura" />
          <h1 className={styles.marcaTitulo}>MundoAventura</h1>
          <p className={styles.marcaEslogan}>¡Descubre tu próxima aventura!</p>
        </div>
        <p className={styles.lead}>
          Esta guía te enseña a usar <strong>MundoAventura</strong>, la app donde los niños
          charlan con personajes de la historia y la ficción. Está dividida en dos partes: una
          para el <strong className={styles.acentoNino}>niño</strong> y otra para el{" "}
          <strong className={styles.acentoAdulto}>adulto</strong>.
        </p>

        <div className={styles.puertas}>
          <a className={`${styles.puerta} ${styles.puertaNino}`} href="#manual-nino">
            <span className={styles.puertaEmoji} aria-hidden="true">
              🧒
            </span>
            <span className={styles.puertaTitulo}>PARA EL NIÑO</span>
            <span className={styles.puertaSub}>Elige, entra y habla. Tu aventura en 3 pasos.</span>
          </a>
          <a className={`${styles.puerta} ${styles.puertaAdulto}`} href="#manual-adulto">
            <span className={styles.puertaEmoji} aria-hidden="true">
              ⚙️
            </span>
            <span className={styles.puertaTitulo}>PARA EL ADULTO</span>
            <span className={styles.puertaSub}>Cuenta de familia, perfiles y configuración.</span>
          </a>
        </div>

        <div className={styles.requisitos}>
          <span className={styles.requisito}>📶 Un dispositivo con internet</span>
          <span className={styles.requisito}>👤 Un adulto que cree la cuenta</span>
          <span className={styles.requisito}>🎙️ Micrófono (opcional) para hablar</span>
        </div>
      </header>

      {/* ================= NIÑO ================= */}
      <section id="manual-nino" className={styles.seccion}>
        <div className={`${styles.banda} ${styles.bandaNino}`}>
          <span className={styles.bandaEmoji} aria-hidden="true">
            🧒
          </span>
          <h2 className={styles.bandaTitulo}>PARA EL NIÑO</h2>
        </div>

        <p className={styles.tira}>
          <span className={styles.tiraOk}>◉ SISTEMA LISTO</span>
          <span className={styles.tiraTexto}>◇ ESCANEANDO LÍNEA TEMPORAL... ¡A JUGAR! ◇</span>
        </p>

        <p className={styles.parrafo}>
          ¡Hola, aventurero! 👋 Aquí eliges un <strong>personaje</strong>, un{" "}
          <strong>mundo</strong> y empiezas a <strong>charlar</strong>. Pide a un adulto que te
          ayude la primera vez.
        </p>

        {/* Misma línea de pasos que ve en el juego, sin ninguno encendido. */}
        <Steps pasoActivo={0} />

        <div className={styles.pasos}>
          <div className={`${styles.paso} ${styles.pasoAmber}`}>
            <span className={styles.pasoTag}>PASO 1</span>
            <div className={styles.pasoEmoji} aria-hidden="true">
              🦖
            </div>
            <h3 className={styles.pasoTitulo}>ELIGE TU PERSONAJE</h3>
            <p className={styles.pasoTexto}>
              Mueve los hologramas con las flechas ◀ ▶ y para en quien quieras: un T-Rex,
              Leonardo da Vinci, Sherlock Holmes… El del <strong className={styles.destacado}>centro</strong>{" "}
              es el elegido. Luego pulsa <strong className={styles.destacado}>SIGUIENTE ▶</strong>.
            </p>
          </div>
          <div className={`${styles.paso} ${styles.pasoHolo}`}>
            <span className={styles.pasoTag}>PASO 2</span>
            <div className={styles.pasoEmoji} aria-hidden="true">
              🌋
            </div>
            <h3 className={styles.pasoTitulo}>ELIGE TU MUNDO</h3>
            <p className={styles.pasoTexto}>
              Ahora un lugar: un volcán, un cuadro, una isla… O usa la carta{" "}
              <strong className={styles.destacado}>«MI FOTO» 📸</strong> para meterte tú en la
              escena (para esa hace falta que un adulto dé permiso).
            </p>
          </div>
          <div className={`${styles.paso} ${styles.pasoLime}`}>
            <span className={styles.pasoTag}>PASO 3</span>
            <div className={styles.pasoEmoji} aria-hidden="true">
              💬
            </div>
            <h3 className={styles.pasoTitulo}>¡A JUGAR!</h3>
            <p className={styles.pasoTexto}>
              Pulsa <strong className={styles.destacado}>¡GENERAR! ▶</strong> y la máquina abre un
              portal 🌀 y crea tu escena. Cuando aparezca la imagen, ¡ya puedes hablar!
            </p>
          </div>
        </div>

        <div className={styles.panel}>
          <h3 className={styles.panelTitulo}>💬 Habla con tu personaje</h3>
          <div className={styles.usos}>
            <div className={styles.uso}>
              <span className={styles.usoEmoji} aria-hidden="true">
                ⌨️
              </span>
              <p className={styles.usoTexto}>
                <strong className={styles.destacado}>Escribe</strong> tu pregunta abajo y pulsa{" "}
                <em>Preguntar</em> (o la tecla Enter).
              </p>
            </div>
            <div className={styles.uso}>
              <span className={styles.usoEmoji} aria-hidden="true">
                🎙️
              </span>
              <p className={styles.usoTexto}>
                O toca el <strong className={styles.destacado}>micro</strong> y habla; toca otra
                vez ⏹ para enviar. Con ✖ cancelas sin mandar nada.
              </p>
            </div>
            <div className={styles.uso}>
              <span className={styles.usoEmoji} aria-hidden="true">
                🔊
              </span>
              <p className={styles.usoTexto}>
                El personaje te responde con su voz. Pulsa{" "}
                <strong className={styles.destacado}>🔊 Volver a escuchar</strong> para oírlo otra
                vez.
              </p>
            </div>
          </div>
          <p className={styles.nota}>Prueba con botones de preguntas rápidas como estos:</p>
          <div className={styles.chips}>
            {EJEMPLOS.map((ejemplo) => (
              <span key={ejemplo} className={styles.chip}>
                {ejemplo}
              </span>
            ))}
          </div>
        </div>

        <div className={styles.badges}>
          <span className={`${styles.badge} ${styles.badgeHolo}`}>HABLA CLARO Y DESPACIO</span>
          <span className={`${styles.badge} ${styles.badgeAmber}`}>PRUEBA PREGUNTAS DISTINTAS</span>
          <span className={`${styles.badge} ${styles.badgePink}`}>
            SI ALGO FALLA, LLAMA A UN ADULTO
          </span>
        </div>
      </section>

      {/* ================= ADULTO ================= */}
      <section id="manual-adulto" className={`${styles.seccion} ${styles.seccionAdulto}`}>
        <div className={`${styles.banda} ${styles.bandaAdulto}`}>
          <span className={styles.bandaEmoji} aria-hidden="true">
            ⚙️
          </span>
          <h2 className={styles.bandaTitulo}>PARA EL ADULTO · CONFIGURACIÓN</h2>
        </div>

        <p className={`${styles.parrafo} ${styles.parrafoAdulto}`}>
          Tú creas y cuidas la <strong>cuenta de familia</strong>. Aquí tienes el arranque y todo
          lo que puedes hacer desde <strong className={styles.acentoAdulto}>⚙️ Configuración</strong>.{" "}
          <span className={styles.aparte}>(La zona 🛡️ Admin queda fuera de este manual.)</span>
        </p>

        <div className={styles.paneles}>
          <div className={styles.panel}>
            <h3 className={styles.panelTitulo}>🚀 Primeros pasos</h3>
            <ol className={styles.lista}>
              <li>
                <strong className={styles.destacado}>Crea la cuenta de familia</strong> con el
                nombre de la familia, el correo de un adulto y una contraseña (mínimo 8
                caracteres). Si la instalación pide verificar el correo, recibirás un código de 6
                dígitos.
              </li>
              <li>
                <strong className={styles.destacado}>Añade un perfil por cada niño</strong>: su
                nombre y, si quieres, el sexo, para que el personaje le hable bien. Con varios
                perfiles, la app pregunta «¿quién juega?» al empezar.
              </li>
              <li>
                <strong className={styles.destacado}>Pon un PIN de 4 dígitos</strong> 🔐 para
                proteger los ajustes de la familia y la subida de fotos.
              </li>
            </ol>
          </div>

          <div className={styles.panel}>
            <h3 className={styles.panelTitulo}>⚙️ Configuración de la familia</h3>
            <p className={styles.introPanel}>
              Se abre con el icono ⚙️ del HUD (dentro del menú ☰). Si hay PIN, lo pide antes de
              entrar (🔐).
            </p>
            <ul className={styles.lista}>
              <li>
                ✏️ Editar el <strong className={styles.destacado}>nombre de la familia</strong>.
              </li>
              <li>
                👥 <strong className={styles.destacado}>Gestionar los niños</strong>: añadir,
                editar o quitar perfiles.
              </li>
              <li>
                🔐 <strong className={styles.destacado}>Poner o cambiar</strong> el PIN de familia
                (para cambiarlo hace falta el actual).
              </li>
              <li>
                🗑️ <strong className={styles.peligro}>Eliminar la cuenta</strong> (acción
                destructiva; pide confirmación).
              </li>
            </ul>
            <p className={styles.cierrePanel}>
              Configuración es solo de tu familia; no toca los ajustes globales de la app.
            </p>
          </div>
        </div>

        <div className={styles.panel}>
          <h3 className={styles.panelTitulo}>🛡️ Seguridad y privacidad</h3>
          <ul className={styles.lista}>
            <li>
              El <strong className={styles.destacado}>PIN</strong> protege la edición del perfil y
              el permiso para subir una foto.
            </li>
            <li>
              La foto que subas <strong className={styles.destacado}>no se guarda</strong>: se usa
              para crear la escena y se descarta.
            </li>
            <li>
              La app está pensada para que un adulto acompañe; el niño ve una interfaz simple, sin
              ajustes sensibles.
            </li>
            <li>
              Revisa la{" "}
              <a
                className={styles.enlace}
                href="/privacidad.html"
                target="_blank"
                rel="noopener noreferrer"
              >
                política de privacidad
              </a>{" "}
              antes de empezar a jugar.
            </li>
          </ul>
        </div>

        <h3 className={styles.faqTitulo}>❓ ¿PROBLEMAS?</h3>
        <div className={styles.faq}>
          <div className={styles.faqCard}>
            <p className={styles.faqPregunta}>😢 «No pude cargar el catálogo»</p>
            <p className={styles.faqTexto}>
              Revisa la conexión a internet y pulsa «Reintentar».
            </p>
          </div>
          <div className={styles.faqCard}>
            <p className={styles.faqPregunta}>🎙️ El micrófono no funciona</p>
            <p className={styles.faqTexto}>
              Necesita una página segura (https o localhost) y permiso del navegador. Siempre
              puedes escribir la pregunta.
            </p>
          </div>
          <div className={styles.faqCard}>
            <p className={styles.faqPregunta}>⏳ La escena tarda</p>
            <p className={styles.faqTexto}>
              Crear una escena lleva unos segundos; verás el portal girando. Espera a que aparezca
              la imagen.
            </p>
          </div>
          <div className={styles.faqCard}>
            <p className={styles.faqPregunta}>🔐 Olvidé el PIN de familia</p>
            <p className={styles.faqTexto}>
              No hay recuperación automática: para cambiarlo hay que escribir el actual. Podéis
              seguir jugando (solo bloquea ⚙️ Configuración y subir una foto); si lo necesitas,
              crea una cuenta de familia nueva.
            </p>
          </div>
        </div>
      </section>

      <footer className={styles.pie}>
        <span className={styles.pieMarca}>
          <Marca size={22} />
          MundoAventura
        </span>
        <span className={styles.pieTexto}>
          MANUAL DE USUARIO · V1 · ¡DESCUBRE TU PRÓXIMA AVENTURA!
        </span>
      </footer>

      <p className={styles.volver}>
        <button
          type="button"
          data-no-sfx
          className="btn btn-secundario"
          onClick={() => {
            sfx("back");
            onCerrar();
          }}
        >
          Volver
        </button>
      </p>
    </article>
  );
}
