"""
frontend/main.py — Interfaz de usuario (asistente por pasos)
============================================================

Aplicación Flet con un flujo guiado, pensado para niños de 8-12 años:

  Paso 1 → Elegir CON QUIÉN hablar (personaje).
  Paso 2 → Elegir un LUGAR (o subir "Mi foto").
  Paso 3 → Generar la escena y conversar con el personaje (chat RAG).

Estilo "infantil y vivo": cabecera con degradado, barra de progreso de pasos,
y la elección de personaje/lugar mediante un carrusel "coverflow" (carta central
grande con las vecinas asomando, flechas ‹ › y puntitos de posición).

Arráncala con:
    flet run frontend/main.py
"""

import base64
import io
import os
import tempfile
import threading
import time

import flet as ft
import numpy as np
import sounddevice as sd
import soundfile as sf

import api_client  # al importarse, carga el .env (incluida la variable DEBUG)
from personajes import GRUPOS, PERSONAJES
from ubicaciones import UBICACIONES

# Id especial (no es una ubicación real) para el modo "Usar mi foto".
FOTO_ID = "__foto__"

# Mapa inverso categoría -> título de grupo legible (p. ej. "prehistorico" ->
# "Prehistóricos"), para mostrar la categoría en la carta central del carrusel.
CATEGORIA_LABEL = {cat: titulo for titulo, cats in GRUPOS.items() for cat in cats}

# Modo desarrollo: si DEBUG está activo, se muestra el botón "Probar conexión".
# El origen de cada respuesta del chat (RAG/GENERAL) lo traza el BACKEND en su
# propia consola (ver backend/services/rag_service.py), no el frontend.
DEBUG = os.getenv("DEBUG", "false").strip().lower() in ("1", "true", "yes", "on")

# Ancho (px) por debajo del cual tratamos la pantalla como "móvil": el contenido pasa
# a ocupar todo el ancho, el carrusel oculta las cartas vecinas, el paso final apila
# imagen y chat, etc. Por encima de este valor se mantiene el diseño de escritorio.
MOVIL_MAX = 760


def main(page: ft.Page):
    # -----------------------------------------------------------------------
    # Configuración general y tema
    # -----------------------------------------------------------------------
    page.title = "Máquina del Tiempo"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.PURPLE)
    page.bgcolor = "#FBF7FF"
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO

    # Estilos de botón reutilizables (grandes y redondeados).
    BTN_ROUND = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=24),
        padding=ft.padding.symmetric(horizontal=18, vertical=14),
    )
    # Estilo para botones que van DENTRO de la cabecera morada: borde y texto
    # blancos para que resalten sobre el degradado (igual que "Probar conexión").
    BTN_HEADER = ft.ButtonStyle(
        color=ft.Colors.WHITE,
        side=ft.BorderSide(1, ft.Colors.WHITE),
        shape=ft.RoundedRectangleBorder(radius=20),
    )

    def es_movil() -> bool:
        """True si la pantalla es estrecha (móvil). Único punto de decisión del
        layout responsive: lo consultan render() y los helpers de presentación."""
        return (page.width or 1200) < MOVIL_MAX

    # -----------------------------------------------------------------------
    # Estado de la app
    # -----------------------------------------------------------------------
    state = {
        "ubicacion_id": None,    # ubicación elegida (o FOTO_ID)
        "personaje_id": None,    # personaje elegido
        "foto_path": None,       # ruta de la foto subida (modo FOTO_ID)
        "chat_personaje": None,  # personaje en pantalla (al que se pregunta)
        "paso": 0,               # paso actual del asistente (0, 1, 2)
        "personaje_idx": 0,      # carta centrada en el carrusel de personajes
        "ubicacion_idx": 0,      # carta centrada en el carrusel de lugares
        "generando": False,      # True mientras se está generando la escena
        "generado_para": None,   # (personaje, ubicacion, foto) de la última escena hecha
        "_ancho": None,          # último ancho de página visto (para re-render en resize)
    }

    # -----------------------------------------------------------------------
    # Controles PERSISTENTES (se crean una vez y se reutilizan entre pasos,
    # para que su contenido —imagen, chat— no se pierda al cambiar de paso).
    # -----------------------------------------------------------------------
    status_text = ft.Text("", size=14, color=ft.Colors.GREY_800)
    summary_text = ft.Text("", size=15, weight=ft.FontWeight.BOLD)

    # --- Panel de carga animado ("Creando...") ---------------------------------
    # Mientras se genera la escena, ocupamos el hueco de la imagen con un panel
    # vivo (emoji que late y cambia + texto con puntos en movimiento + barra), para
    # que el niño tenga algo bonito que mirar y no vea un espacio vacío. La animación
    # la mueve un hilo aparte (_animar_carga) mientras dura la generación.
    loading_emoji = ft.Text(
        "🎨", size=72, text_align=ft.TextAlign.CENTER,
        animate_scale=ft.Animation(420, ft.AnimationCurve.EASE_IN_OUT),
        animate_rotation=ft.Animation(420, ft.AnimationCurve.EASE_IN_OUT),
    )
    loading_text = ft.Text(
        "Creando tu escena", size=18, weight=ft.FontWeight.BOLD,
        color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER,
    )
    # Barra de progreso del panel de carga (su ancho se ajusta en render() según pantalla).
    loading_bar = ft.ProgressBar(
        width=240,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
    )
    # width/height se reasignan en render() para adaptarse al ancho disponible (móvil).
    loading_panel = ft.Container(
        visible=False,
        width=560,
        height=320,
        border_radius=18,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[ft.Colors.PURPLE_300, ft.Colors.PINK_200],
        ),
        alignment=ft.alignment.center,
        content=ft.Column(
            [loading_emoji, loading_text, loading_bar],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=16,
        ),
    )
    # width se reasigna en render() (fluido en móvil); fit=CONTAIN evita recortes.
    result_image = ft.Image(width=560, fit=ft.ImageFit.CONTAIN, visible=False)

    # Chat (RAG)
    chat_titulo = ft.Text("💬 Habla con el personaje", size=16, weight=ft.FontWeight.BOLD)
    # auto_scroll=True: al añadir una burbuja (pregunta o respuesta) el chat baja solo
    # hasta el final, para no tener que arrastrar a mano y ver siempre lo último.
    chat_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=320, auto_scroll=True)

    def _reproducir_respuesta(audio_b64: str) -> None:
        """Decodifica el mp3 (base64) y lo reproduce COMPLETO sin bloquear.

        Usa soundfile (decodifica el mp3 entero en memoria) + sounddevice
        (`sd.play`, no bloquea y reproduce TODO el array). Antes se usaba
        just_playback, que cortaba la reproducción a mitad aunque el mp3 estuviera
        completo. `sd.stop()` corta la respuesta anterior si aún sonaba. No deja
        ficheros temporales. Un fallo NUNCA rompe la UI: el texto ya está visible.
        """
        try:
            mp3 = base64.b64decode(audio_b64)
            data, sr = sf.read(io.BytesIO(mp3), dtype="float32")
            sd.stop()
            sd.play(data, sr)
        except Exception as exc:
            print(f"[Frontend] No se pudo reproducir la voz: {exc}")

    # Grabación del micrófono con sounddevice → wav. El dispositivo de entrada por
    # defecto puede ser -1 (ninguno) y Windows enumera muchos micros "fantasma"
    # (auriculares Bluetooth desconectados) que dan 'Invalid device' al abrir: por
    # eso probamos varios candidatos hasta que uno abre de verdad.
    FS_GRAB = 16000
    grabacion = {"stream": None, "frames": [], "fs": FS_GRAB}

    def _dispositivos_entrada():
        """Índices de micrófonos candidatos, ordenados por fiabilidad de apertura.

        En Windows los endpoints directos de hardware (WASAPI/WDM-KS) a menudo dan
        'Unanticipated host error' (-9999); en cambio los MAPEADORES por defecto de
        cada host API (MME 'Asignador de sonido', DirectSound 'Controlador
        primario') abren de forma fiable y siguen al micro predeterminado de
        Windows. Orden: (1) el default de sounddevice si es válido; (2) el input
        por defecto de cada host API (los mapeadores fiables); (3) micros con
        nombre "micrófono/mic" no-BT; (4) otras entradas no-BT (mezcla estéreo,
        línea... se evitan salvo que no haya micro); (5) Bluetooth 'Hands-Free'.
        """
        candidatos = []

        def _añadir(idx):
            if isinstance(idx, int) and idx >= 0 and idx not in candidatos:
                try:
                    if sd.query_devices(idx)["max_input_channels"] > 0:
                        candidatos.append(idx)
                except Exception:
                    pass

        try:
            _añadir(sd.default.device[0])
        except Exception:
            pass
        for host in sd.query_hostapis():
            _añadir(host.get("default_input_device", -1))

        mics, otros, bt = [], [], []
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] <= 0 or i in candidatos:
                continue
            nombre = dev["name"].lower()
            if "hands-free" in nombre or "bthhfenum" in nombre:
                bt.append(i)
            elif "mic" in nombre:  # "micrófono", "mic input", "microphone"...
                mics.append(i)
            else:
                otros.append(i)
        return candidatos + mics + otros + bt

    def _iniciar_grabacion():
        """Abre el micrófono y empieza a acumular frames PCM.

        Prueba los dispositivos de entrada candidatos en orden y se queda con el
        PRIMERO que abre de verdad (saltando los micros fantasma/BT que dan
        'Invalid device'). Para cada uno prueba 16 kHz y, si no lo admite, su
        frecuencia por defecto. Solo asigna grabacion["stream"] tras un start()
        con éxito; si ninguno abre, lanza una excepción con el último error.
        """
        grabacion["frames"] = []

        def _cb(indata, frames, time_info, status):
            grabacion["frames"].append(indata.copy())

        ultimo_error = None
        for dev in _dispositivos_entrada():
            info = sd.query_devices(dev)
            for fs in dict.fromkeys((FS_GRAB, int(info.get("default_samplerate") or 44100))):
                stream = None
                try:
                    stream = sd.InputStream(
                        samplerate=fs, channels=1, device=dev, callback=_cb
                    )
                    stream.start()
                except Exception as exc:
                    ultimo_error = exc
                    if stream is not None:
                        try:
                            stream.close()
                        except Exception:
                            pass
                    continue
                grabacion["stream"] = stream
                grabacion["fs"] = fs
                if DEBUG:
                    print(f"[Frontend] 🎙️ Grabando device {dev} ({info['name']}) @ {fs} Hz")
                return
        raise RuntimeError(f"ningún micrófono disponible se pudo abrir ({ultimo_error})")

    def _detener_grabacion():
        """Cierra el stream, escribe los frames a un .wav y devuelve su ruta (o None)."""
        st = grabacion["stream"]
        grabacion["stream"] = None
        if st is not None:
            st.stop()
            st.close()
        if not grabacion["frames"]:
            return None
        audio = np.concatenate(grabacion["frames"], axis=0)
        ruta = os.path.join(tempfile.gettempdir(), f"pregunta_{int(time.time())}.wav")
        sf.write(ruta, audio, grabacion["fs"])
        return ruta

    pregunta_field = ft.TextField(
        hint_text="Escribe tu pregunta... (ej. ¿Qué comes?)",
        expand=True,
        disabled=True,
        border_radius=16,
    )
    preguntar_button = ft.ElevatedButton(
        "Preguntar", disabled=True, bgcolor=ft.Colors.PURPLE_400, color=ft.Colors.WHITE,
        style=BTN_ROUND,
    )
    mic_button = ft.IconButton(
        icon=ft.Icons.MIC,
        tooltip="Toca para hablar; toca otra vez para enviar",
        disabled=True,
        icon_color=ft.Colors.PURPLE_400,
    )
    chat_panel = ft.Container(
        visible=False,
        expand=True,  # en el paso 3 ocupa el ancho que sobra a la derecha de la imagen
        padding=14,
        bgcolor=ft.Colors.WHITE,
        border=ft.border.all(1, ft.Colors.GREY_200),
        border_radius=18,
        content=ft.Column(
            [chat_titulo, chat_column, ft.Row([pregunta_field, mic_button, preguntar_button])],
            spacing=10,
        ),
    )

    # Contenedor donde se dibuja el paso actual. Su ancho/padding se fijan en render():
    # ~1100 centrado en escritorio (para que quepan las dos columnas del paso final) y
    # el ancho completo de la pantalla en móvil.
    content = ft.Container(padding=24)

    # -----------------------------------------------------------------------
    # Helpers de presentación
    # -----------------------------------------------------------------------
    def nombre_lugar() -> str:
        if state["ubicacion_id"] == FOTO_ID:
            return "tu foto"
        if state["ubicacion_id"]:
            return UBICACIONES[state["ubicacion_id"]]["label"]
        return ""

    def carta_carrusel(emoji: str, label: str, *, foco: bool, seleccionada: bool,
                       on_click, sub: str | None = None) -> ft.Container:
        """Una carta del carrusel.

        `foco=True` es la carta central (grande y protagonista); las vecinas van
        más pequeñas y semitransparentes para dar el efecto "coverflow". La central
        se resalta en ámbar cuando está seleccionada.
        """
        if foco:
            if es_movil():
                w, h, e_size, l_size, opacity, border_w = 150, 150, 56, 16, 1.0, 5
            else:
                w, h, e_size, l_size, opacity, border_w = 190, 186, 66, 17, 1.0, 5
            border_col = ft.Colors.AMBER_400 if seleccionada else ft.Colors.PURPLE_200
        else:
            w, h, e_size, l_size, opacity, border_w = 112, 128, 40, 11, 0.5, 3
            border_col = ft.Colors.GREY_200

        col = [ft.Text(emoji, size=e_size)]
        if foco and sub:
            col.append(
                ft.Container(
                    ft.Text(sub, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_700),
                    bgcolor=ft.Colors.PURPLE_50,
                    border_radius=10,
                    padding=ft.padding.symmetric(horizontal=10, vertical=2),
                )
            )
        col.append(
            ft.Text(label, size=l_size, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
        )

        return ft.Container(
            width=w,
            height=h,
            padding=8,
            bgcolor=ft.Colors.AMBER_50 if (foco and seleccionada) else ft.Colors.WHITE,
            border=ft.border.all(border_w, border_col),
            border_radius=24,
            ink=True,
            on_click=on_click,
            alignment=ft.alignment.center,
            opacity=opacity,
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            shadow=ft.BoxShadow(
                blur_radius=16 if foco else 6,
                color=ft.Colors.with_opacity(0.18 if foco else 0.10, ft.Colors.BLACK),
                offset=ft.Offset(0, 5),
            ),
            content=ft.Column(
                col,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
        )

    def flecha_carrusel(icono: str, on_click, color=ft.Colors.PURPLE_400) -> ft.Container:
        """Botón circular (‹ / ›) para mover el carrusel; grande para dedos pequeños."""
        lado = 48 if es_movil() else 58
        return ft.Container(
            width=lado,
            height=lado,
            border_radius=lado / 2,
            bgcolor=color,
            ink=True,
            on_click=on_click,
            alignment=ft.alignment.center,
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Text(icono, size=26 if es_movil() else 30,
                            color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
        )

    def carrusel(items: list[dict], idx: int, on_prev, on_next, on_center,
                 accent=ft.Colors.PURPLE_400, accent_suave=ft.Colors.PURPLE_100) -> ft.Control:
        """Carrusel tipo coverflow.

        `items` es una lista de dicts {emoji, label, sub, seleccionada}. Muestra la
        carta `idx` en el centro con sus vecinas (con vuelta circular) asomando a los
        lados; flechas ‹ › y puntitos de posición debajo. Tocar una vecina la trae al
        centro; tocar la central dispara `on_center` (p. ej. abrir el selector de foto).
        `accent`/`accent_suave` colorean flechas y puntitos para distinguir cada paso.
        """
        n = len(items)
        idx %= n
        prev_it, cur_it, next_it = items[(idx - 1) % n], items[idx], items[(idx + 1) % n]

        carta_central = carta_carrusel(
            cur_it["emoji"], cur_it["label"], foco=True,
            seleccionada=cur_it["seleccionada"], on_click=on_center, sub=cur_it.get("sub"),
        )
        if es_movil():
            # En móvil no caben las cartas vecinas: solo flecha + carta central + flecha.
            cartas = [
                flecha_carrusel("‹", on_prev, color=accent),
                carta_central,
                flecha_carrusel("›", on_next, color=accent),
            ]
        else:
            cartas = [
                flecha_carrusel("‹", on_prev, color=accent),
                carta_carrusel(prev_it["emoji"], prev_it["label"],
                               foco=False, seleccionada=False, on_click=on_prev),
                carta_central,
                carta_carrusel(next_it["emoji"], next_it["label"],
                               foco=False, seleccionada=False, on_click=on_next),
                flecha_carrusel("›", on_next, color=accent),
            ]

        fila = ft.Row(
            cartas,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10 if es_movil() else 14,
            height=170 if es_movil() else 200,
        )
        puntos = ft.Row(
            [
                ft.Container(
                    width=11, height=11, border_radius=6,
                    bgcolor=accent if i == idx else accent_suave,
                )
                for i in range(n)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=7,
        )
        return ft.Column([fila, puntos],
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)

    def build_header(acciones: list | None = None) -> ft.Control:
        """Cabecera común a TODAS las pantallas: título + botones de navegación.

        `acciones` son los botones del paso (Atrás / Siguiente / Empezar de nuevo),
        que van DENTRO de la cabecera —no debajo del contenido— para no robar espacio
        vertical y quedar siempre visibles. Todas las pantallas siguen este mismo
        patrón (cabecera con botones + contenido), sin barra de pasos.
        """
        movil = es_movil()
        fila_cabecera = [
            ft.Column(
                [
                    ft.Text("🕰️ Máquina del Tiempo", size=20 if movil else 26,
                            weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ft.Text("¡Viaja sin salir de tu cuarto!", size=12 if movil else 14,
                            color=ft.Colors.WHITE),
                ],
                # En móvil no usamos expand para que los botones puedan envolver debajo.
                expand=not movil,
                spacing=2,
            ),
        ]
        if acciones:
            fila_cabecera.extend(acciones)
        # "Probar conexión" es una herramienta de diagnóstico: solo en modo DEBUG.
        # En la versión final para el niño no aparece.
        if DEBUG:
            fila_cabecera.append(
                ft.OutlinedButton(
                    "🔌 Probar conexión",
                    on_click=on_check_backend,
                    style=BTN_HEADER,
                )
            )
        return ft.Container(
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=[ft.Colors.PURPLE_400, ft.Colors.PINK_300],
            ),
            border_radius=24,
            padding=16 if movil else 24,
            # wrap=True: en móvil los botones de acción bajan a otra línea en vez de salirse.
            content=ft.Row(
                fila_cabecera,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=movil,
                spacing=10,
                run_spacing=8,
            ),
        )

    def panel_paso(titulo: str, contenido: ft.Control, *, fondo, borde, color_titulo) -> ft.Control:
        """Envuelve un paso en un 'mundo' de color propio (fondo + borde + título),
        para que al cambiar de pantalla se note claramente que es otra sección.

        Tamaño FIJO (mismo ancho y alto en los dos pasos) para que la pantalla no
        "salte" al cambiar, aunque un paso tenga más texto que el otro (p. ej. el
        aviso de la foto). El contenido se ancla arriba y el hueco sobrante queda abajo.
        """
        movil = es_movil()
        return ft.Container(
            # Sin ancho fijo: el Column contenedor lo estira al MISMO ancho que la
            # cabecera (ver render → horizontal_alignment=STRETCH). En escritorio, altura
            # fija para que los dos pasos midan igual; en móvil crece con el contenido
            # (el scroll de página lo absorbe) para que nada se corte.
            height=None if movil else 360,
            bgcolor=fondo,
            border=ft.border.all(3, borde),
            border_radius=28,
            padding=ft.padding.symmetric(horizontal=12 if movil else 20, vertical=16),
            alignment=ft.alignment.top_center,
            content=ft.Column(
                [
                    ft.Text(titulo, size=19 if movil else 23,
                            weight=ft.FontWeight.BOLD, color=color_titulo,
                            text_align=ft.TextAlign.CENTER),
                    contenido,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
        )

    # -----------------------------------------------------------------------
    # Paso 1 — Lugar
    # -----------------------------------------------------------------------
    def build_step_lugar() -> ft.Control:
        # Catálogo del carrusel: "Mi foto" SIEMPRE primero, luego las ubicaciones reales.
        keys = [FOTO_ID] + list(UBICACIONES.keys())
        idx = state["ubicacion_idx"] % len(keys)
        centrada = keys[idx]

        # La carta central queda AUTOSELECCIONADA: para una ubicación real basta con
        # tenerla en el centro; la foto necesita además un archivo (si no, se queda sin
        # seleccionar y el niño pulsa la carta central para abrir el selector).
        if centrada == FOTO_ID:
            state["ubicacion_id"] = FOTO_ID if state["foto_path"] else None
        else:
            state["ubicacion_id"] = centrada
            state["foto_path"] = None  # salimos del modo foto

        def item(key: str) -> dict:
            if key == FOTO_ID:
                sel = state["ubicacion_id"] == FOTO_ID
                label = "✓ ¡Foto lista!" if (sel and state["foto_path"]) else "Mi foto"
                return {"emoji": "📷", "label": label, "sub": "Tu cuarto", "seleccionada": sel}
            d = UBICACIONES[key]
            return {"emoji": d["emoji"], "label": d["label"], "sub": None,
                    "seleccionada": state["ubicacion_id"] == key}

        items = [item(k) for k in keys]

        def on_center(_):
            # "Mi foto" sin archivo: abre el selector. En cualquier otro caso (lugar
            # real, o foto ya elegida) tocar la central avanza de paso, igual que
            # "Siguiente". Si la foto aún no está, no se puede avanzar.
            if centrada == FOTO_ID and not state["foto_path"]:
                abrir_selector_foto()
            elif state["ubicacion_id"]:
                ir_paso(2)

        contenido = ft.Column(
            [
                carrusel(items, idx,
                         on_prev=lambda e: mover_lugar(-1),
                         on_next=lambda e: mover_lugar(1),
                         on_center=on_center,
                         accent=ft.Colors.TEAL_600, accent_suave=ft.Colors.TEAL_200),
                ft.Text("📷 Si usas tu foto, ¡saca tu cuarto vacío! 😊", size=12,
                        italic=True, color=ft.Colors.TEAL_900),
                status_text,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
        )
        # Paso "Lugar": mundo TURQUESA (viaje) — distinto del morado de "Personaje".
        return panel_paso("🗺️ Selecciona un lugar", contenido,
                          fondo="#B8F2E6", borde=ft.Colors.TEAL_400,
                          color_titulo=ft.Colors.TEAL_900)

    # -----------------------------------------------------------------------
    # Paso 2 — Personaje
    # -----------------------------------------------------------------------
    def build_step_personaje() -> ft.Control:
        # Un único carrusel con todos los personajes; la categoría (Prehistóricos,
        # Históricos, Ficticios) se muestra como etiqueta en la carta central.
        keys = list(PERSONAJES.keys())
        idx = state["personaje_idx"] % len(keys)
        # La carta central queda autoseleccionada (siempre hay un personaje elegido).
        state["personaje_id"] = keys[idx]

        items = [
            {
                "emoji": PERSONAJES[pid]["emoji"],
                "label": PERSONAJES[pid]["label"],
                "sub": CATEGORIA_LABEL.get(PERSONAJES[pid]["categoria"]),
                "seleccionada": state["personaje_id"] == pid,
            }
            for pid in keys
        ]

        contenido = carrusel(items, idx,
                             on_prev=lambda e: mover_personaje(-1),
                             on_next=lambda e: mover_personaje(1),
                             # Tocar la carta central avanza de paso (igual que "Siguiente").
                             on_center=lambda e: ir_paso(1),
                             accent=ft.Colors.PURPLE_500, accent_suave=ft.Colors.PURPLE_200)
        # Paso "Personaje": mundo MORADO — distinto del turquesa de "Lugar".
        return panel_paso("🎭 ¿Con quién quieres hablar?", contenido,
                          fondo="#E6D2FF", borde=ft.Colors.PURPLE_400,
                          color_titulo=ft.Colors.PURPLE_900)

    # -----------------------------------------------------------------------
    # Paso 3 — Generar + resultado + chat
    # -----------------------------------------------------------------------
    def build_step_generar() -> ft.Control:
        pid = state["personaje_id"]
        pj = PERSONAJES[pid]["label"] if pid else ""
        emoji = PERSONAJES[pid]["emoji"] if pid else ""
        summary_text.value = f"{emoji}  {pj} · {nombre_lugar()}"
        if state["chat_personaje"]:
            chat_titulo.value = f"💬 Habla con {PERSONAJES[state['chat_personaje']]['label']}"

        # COLUMNA IZQUIERDA — la imagen es la protagonista (o el panel de carga
        # mientras se genera). Debajo, una etiqueta compacta con personaje · lugar
        # (sustituye al antiguo título "¡Tu escena!" + caja grande de resumen).
        caption = ft.Container(
            summary_text,
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            bgcolor=ft.Colors.PURPLE_50,
            border_radius=12,
        )
        movil = es_movil()
        columna_imagen = ft.Container(
            # Escritorio: ancho fijo (la imagen es la protagonista a la izquierda).
            # Móvil: ocupa el ancho del contenedor padre.
            width=None if movil else 580,
            content=ft.Column(
                [
                    ft.Container(loading_panel, alignment=ft.alignment.center),
                    ft.Container(result_image, alignment=ft.alignment.center),
                    caption,
                    status_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
        )

        # Escritorio: imagen (izquierda) + chat a toda la altura (derecha), en DOS
        # COLUMNAS. Móvil: se APILAN (imagen arriba, chat debajo). La escena se genera
        # AUTOMÁTICAMENTE al llegar al paso (ver _auto_generar): no hay botón "¡Generar!".
        if movil:
            return ft.Column(
                [columna_imagen, chat_panel],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                spacing=14,
            )
        return ft.Row(
            [columna_imagen, chat_panel],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=18,
        )

    # -----------------------------------------------------------------------
    # Render: dibuja el paso actual
    # -----------------------------------------------------------------------
    def render():
        # -- Tamaños adaptativos (responsive) -------------------------------------
        # Se calculan aquí, en el único punto que se re-ejecuta en cada navegación y
        # cambio de tamaño (ver on_resized), porque los controles persistentes
        # (content, loading_panel, result_image, chat_column) se crean una sola vez.
        movil = es_movil()
        if movil:
            content.width = page.width          # ocupa todo el ancho de la pantalla
            content.padding = 12
            ancho_img = min(560, (page.width or 560) - 2 * content.padding)
            loading_panel.width = ancho_img
            loading_panel.height = 240
            loading_bar.width = min(240, ancho_img - 40)
            result_image.width = ancho_img
            chat_column.height = 260
        else:
            content.width = min(1100, (page.width or 1100))  # centrado, máx. 1100
            content.padding = 24
            loading_panel.width = 560
            loading_panel.height = 320
            loading_bar.width = 240
            result_image.width = 560
            chat_column.height = 320

        # Los botones de navegación de cada paso viven EN la cabecera (mismo patrón en
        # las tres pantallas). "Siguiente" se desactiva hasta que hay selección; como
        # render() se vuelve a llamar al elegir, su estado se actualiza solo.
        if state["paso"] == 0:
            cuerpo = build_step_personaje()
            acciones = [
                ft.OutlinedButton("Siguiente  →", on_click=lambda e: ir_paso(1),
                                  disabled=not state["personaje_id"], style=BTN_HEADER),
            ]
        elif state["paso"] == 1:
            cuerpo = build_step_lugar()
            acciones = [
                ft.OutlinedButton("←  Atrás", on_click=lambda e: ir_paso(0), style=BTN_HEADER),
                ft.OutlinedButton("Siguiente  →", on_click=lambda e: ir_paso(2),
                                  disabled=not state["ubicacion_id"], style=BTN_HEADER),
            ]
        else:
            cuerpo = build_step_generar()
            acciones = [
                ft.OutlinedButton("←  Atrás", on_click=lambda e: ir_paso(1), style=BTN_HEADER),
                ft.OutlinedButton("🔄 Empezar de nuevo", on_click=empezar_de_nuevo, style=BTN_HEADER),
            ]
        # STRETCH: cabecera y panel del paso ocupan el MISMO ancho (el del contenedor),
        # para que el panel de colores no quede más estrecho que la cabecera.
        content.content = ft.Column(
            [build_header(acciones=acciones), cuerpo],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        page.update()

    def ir_paso(n: int):
        state["paso"] = n
        status_text.value = ""
        render()
        # Al entrar en el paso final, generamos la escena automáticamente.
        if n == 2:
            _auto_generar()

    # -----------------------------------------------------------------------
    # Selección de lugar / personaje / foto
    # -----------------------------------------------------------------------
    def mover_personaje(delta: int):
        """Gira el carrusel de personajes; la carta central se autoselecciona al renderizar."""
        state["personaje_idx"] = (state["personaje_idx"] + delta) % len(PERSONAJES)
        render()

    def mover_lugar(delta: int):
        """Gira el carrusel de lugares (ubicaciones + 'Mi foto') con vuelta circular."""
        total = len(UBICACIONES) + 1  # +1 por la carta "Mi foto"
        state["ubicacion_idx"] = (state["ubicacion_idx"] + delta) % total
        render()

    def on_foto_selected(e: ft.FilePickerResultEvent):
        if not e.files:
            return  # el usuario canceló
        state["foto_path"] = e.files[0].path
        state["ubicacion_id"] = FOTO_ID
        state["ubicacion_idx"] = 0  # "Mi foto" es la primera carta del carrusel
        render()

    file_picker = ft.FilePicker(on_result=on_foto_selected)
    page.overlay.append(file_picker)

    def abrir_selector_foto():
        file_picker.pick_files(
            allowed_extensions=["png", "jpg", "jpeg", "bmp", "webp"],
            allow_multiple=False,
        )

    # -----------------------------------------------------------------------
    # Generar la escena (en un hilo aparte para no congelar la interfaz)
    # -----------------------------------------------------------------------
    def _auto_generar():
        """Genera la escena al entrar en el paso final, solo si hace falta.

        Evita regenerar si ya hay una escena para esta misma selección (p. ej. al
        ir "Atrás" y volver sin cambiar nada) o si ya se está generando.
        """
        if state["generando"]:
            return
        if not state["ubicacion_id"] or not state["personaje_id"]:
            return
        seleccion = (state["personaje_id"], state["ubicacion_id"], state["foto_path"])
        if seleccion == state["generado_para"]:
            return  # ya tenemos esta escena hecha: conservamos imagen y chat
        _iniciar_generacion()

    def _animar_carga():
        """Anima el panel de carga (emoji + puntos) mientras dura la generación.

        Corre en su propio hilo y se detiene solo cuando state['generando'] pasa a
        False. Cicla emojis "creativos", hace latir/girar el emoji y mueve los puntos
        de "Creando..." para que la espera resulte entretenida.
        """
        frames = ["🎨", "🖌️", "✨", "🪄", "🌈", "🖼️"]
        i = 0
        while state["generando"]:
            loading_emoji.value = frames[i % len(frames)]
            loading_emoji.scale = 1.25 if i % 2 == 0 else 1.0
            loading_emoji.rotate = 0.12 if i % 2 == 0 else -0.12
            loading_text.value = "Creando tu escena" + "." * (1 + i % 3)
            i += 1
            try:
                page.update()
            except Exception:
                break  # la página se cerró: salimos sin ruido
            time.sleep(0.45)

    def _iniciar_generacion():
        state["generando"] = True
        loading_panel.visible = True
        # Mientras (re)generamos, ocultamos la escena y el chat anteriores.
        result_image.visible = False
        chat_panel.visible = False
        pregunta_field.disabled = True
        preguntar_button.disabled = True
        status_text.value = ""  # el propio panel ya dice "Creando..."
        page.update()
        # Un hilo anima el panel y otro hace la llamada (la red) sin congelar la UI.
        threading.Thread(target=_animar_carga, daemon=True).start()
        threading.Thread(target=_run_generate, daemon=True).start()

    def _run_generate():
        pid = state["personaje_id"]
        try:
            if state["ubicacion_id"] == FOTO_ID:
                result = api_client.generate_on_photo(state["foto_path"], pid)
            else:
                result = api_client.generate(state["ubicacion_id"], pid)
            result_image.src_base64 = result["result_png_base64"]
            result_image.visible = True
            # Recordamos para qué selección se hizo, para no regenerarla sin motivo.
            state["generado_para"] = (pid, state["ubicacion_id"], state["foto_path"])
            # Activamos el chat para ESTE personaje.
            state["chat_personaje"] = pid
            chat_titulo.value = f"💬 Habla con {PERSONAJES[pid]['label']}"
            chat_column.controls.clear()
            chat_panel.visible = True
            pregunta_field.disabled = False
            preguntar_button.disabled = False
            mic_button.disabled = False
            status_text.value = ""  # el chat ya invita a hablar; no hace falta avisar
        except api_client.BackendError as exc:
            status_text.value = f"❌ {exc}"
        finally:
            state["generando"] = False  # detiene el hilo de animación
            loading_panel.visible = False
            page.update()

    # -----------------------------------------------------------------------
    # Chat (RAG)
    # -----------------------------------------------------------------------
    def _add_burbuja(texto: str, es_nino: bool):
        chat_column.controls.append(
            ft.Container(
                content=ft.Text(texto, size=13, selectable=True),
                bgcolor=ft.Colors.BLUE_50 if es_nino else ft.Colors.GREEN_50,
                padding=10,
                border_radius=12,
                alignment=ft.alignment.center_right if es_nino else ft.alignment.center_left,
            )
        )

    def preguntar(_):
        pid = state["chat_personaje"]
        texto = (pregunta_field.value or "").strip()
        if not pid or not texto:
            return
        _add_burbuja(f"🧒 {texto}", es_nino=True)
        pregunta_field.value = ""
        # Mientras se responde, bloqueamos también el micro para no solapar una
        # pregunta escrita con una hablada.
        pregunta_field.disabled = True
        preguntar_button.disabled = True
        mic_button.disabled = True
        pensando = ft.Text("🤔 Pensando...", size=13, italic=True)
        chat_column.controls.append(pensando)
        page.update()
        threading.Thread(target=_run_ask, args=(pid, texto, pensando), daemon=True).start()

    def _run_ask(pid: str, texto: str, pensando: ft.Text):
        try:
            result = api_client.ask(pid, texto)
            respuesta = result.get("respuesta", "(sin respuesta)")
            chat_column.controls.remove(pensando)
            # El origen (RAG/GENERAL) lo traza el backend en su consola, no el cliente.
            _add_burbuja(f"{PERSONAJES[pid]['emoji']} {respuesta}", es_nino=False)
            # Auto-reproducción de la respuesta (si vino audio), a la vez que
            # aparece la burbuja. Si audio_base64 es None (voz off o TTS falló),
            # simplemente no suena: el texto sigue visible.
            audio_b64 = result.get("audio_base64")
            if audio_b64:
                _reproducir_respuesta(audio_b64)
        except api_client.BackendError as exc:
            pensando.value = f"❌ {exc}"
        finally:
            pregunta_field.disabled = False
            preguntar_button.disabled = False
            mic_button.disabled = False
            page.update()

    def _toggle_micro(_):
        pid = state["chat_personaje"]
        if not pid:
            return
        if grabacion["stream"] is None:
            # Empezar a grabar.
            try:
                _iniciar_grabacion()
            except Exception as exc:
                _add_burbuja(f"❌ No se pudo abrir el micrófono: {exc}", es_nino=False)
                page.update()
                return
            mic_button.icon = ft.Icons.STOP_CIRCLE
            mic_button.icon_color = ft.Colors.RED_400
            mic_button.tooltip = "Grabando... toca para enviar"
            # Mientras se graba, no se puede escribir/enviar (evita solapar).
            pregunta_field.disabled = True
            preguntar_button.disabled = True
            page.update()
        else:
            # Parar, escribir el wav y transcribir.
            ruta = _detener_grabacion()
            mic_button.icon = ft.Icons.MIC
            mic_button.icon_color = ft.Colors.PURPLE_400
            mic_button.tooltip = "Toca para hablar; toca otra vez para enviar"
            mic_button.disabled = True
            pregunta_field.disabled = True
            preguntar_button.disabled = True
            page.update()
            if not ruta:
                # No se capturó nada: reactivar y salir.
                mic_button.disabled = False
                pregunta_field.disabled = False
                preguntar_button.disabled = False
                page.update()
                return
            threading.Thread(target=_run_transcribe, args=(pid, ruta), daemon=True).start()

    def _run_transcribe(pid: str, audio_path: str):
        try:
            texto = api_client.transcribe(audio_path).strip()
            if not texto:
                _add_burbuja("🤔 No te oí bien. Prueba otra vez. 🎤", es_nino=False)
                return
            # La pregunta hablada entra al MISMO flujo que una escrita.
            _add_burbuja(f"🧒 {texto}", es_nino=True)
            pensando = ft.Text("🤔 Pensando...", size=13, italic=True)
            chat_column.controls.append(pensando)
            page.update()
            _run_ask(pid, texto, pensando)  # reutiliza el flujo de respuesta+voz
        except api_client.BackendError as exc:
            print(f"[Frontend] Error al transcribir la voz: {exc}")
            _add_burbuja("❌ No pude escucharte bien. Inténtalo otra vez. 🎤", es_nino=False)
        finally:
            # El wav ya se transcribió: lo borramos para no acumular temporales.
            try:
                os.remove(audio_path)
            except OSError:
                pass
            mic_button.disabled = False
            pregunta_field.disabled = False
            preguntar_button.disabled = False
            page.update()

    # -----------------------------------------------------------------------
    # Empezar de nuevo / comprobar backend
    # -----------------------------------------------------------------------
    def empezar_de_nuevo(_):
        state.update(
            {"ubicacion_id": None, "personaje_id": None, "foto_path": None,
             "chat_personaje": None, "paso": 0,
             "personaje_idx": 0, "ubicacion_idx": 0,
             "generando": False, "generado_para": None}
        )
        loading_panel.visible = False
        result_image.visible = False
        result_image.src_base64 = None
        chat_panel.visible = False
        chat_column.controls.clear()
        pregunta_field.value = ""
        pregunta_field.disabled = True
        preguntar_button.disabled = True
        mic_button.disabled = True
        status_text.value = ""
        render()

    def on_check_backend(_):
        try:
            info = api_client.check_health()
            token = "sí" if info.get("token_configurado") else "NO"
            deepl = "ok" if info.get("deepl_ok") else "NO"
            msg = (
                f"✅ Backend OK · modelo={info.get('replicate_model')} · "
                f"token={token} · DeepL={deepl}"
            )
        except api_client.BackendError as exc:
            msg = f"❌ {exc}"
        page.open(ft.SnackBar(ft.Text(msg)))

    # -----------------------------------------------------------------------
    # Conectar handlers a los controles persistentes y montar la página
    # -----------------------------------------------------------------------
    preguntar_button.on_click = preguntar
    pregunta_field.on_submit = preguntar
    mic_button.on_click = _toggle_micro

    def on_resized(e):
        # Re-dibuja al cambiar el ancho (cruce de breakpoint móvil/escritorio o cambio
        # notable, p. ej. al rotar) para recalcular los anchos fluidos. El umbral de
        # 20 px evita reconstruir el árbol en cada píxel del arrastre.
        if state["_ancho"] is None or abs((page.width or 0) - state["_ancho"]) > 20:
            state["_ancho"] = page.width
            render()

    page.on_resized = on_resized

    page.add(ft.Row([content], alignment=ft.MainAxisAlignment.CENTER))
    render()


if __name__ == "__main__":
    ft.app(target=main)
