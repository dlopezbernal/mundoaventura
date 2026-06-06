"""
frontend/main.py — Interfaz de usuario (asistente por pasos)
============================================================

Aplicación Flet con un flujo guiado, pensado para niños de 8-12 años:

  Paso 1 → Elegir un PERSONAJE.
  Paso 2 → Elegir un LUGAR (o subir "Mi foto").
  Paso 3 → Generar la escena y conversar con el personaje (chat RAG).

Estilo "infantil y vivo": cabecera con degradado, barra de progreso de pasos,
tarjetas grandes y redondeadas con emoji, y selección resaltada con animación.

Arráncala con:
    flet run frontend/main.py
"""

import os
import threading
import time

import flet as ft

import api_client  # al importarse, carga el .env (incluida la variable DEBUG)
from personajes import GRUPOS, PERSONAJES, personajes_de_grupo
from ubicaciones import UBICACIONES

# Id especial (no es una ubicación real) para el modo "Usar mi foto".
FOTO_ID = "__foto__"

# Modo desarrollo: si DEBUG está activo, se muestra el botón "Probar conexión".
# El origen de cada respuesta del chat (RAG/GENERAL) lo traza el BACKEND en su
# propia consola (ver backend/services/rag_service.py), no el frontend.
DEBUG = os.getenv("DEBUG", "false").strip().lower() in ("1", "true", "yes", "on")


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
    BTN_PRIMARY = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=28),
        padding=ft.padding.symmetric(horizontal=26, vertical=18),
        text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
    )
    BTN_ROUND = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=24),
        padding=ft.padding.symmetric(horizontal=18, vertical=14),
    )

    # -----------------------------------------------------------------------
    # Estado de la app
    # -----------------------------------------------------------------------
    state = {
        "ubicacion_id": None,    # ubicación elegida (o FOTO_ID)
        "personaje_id": None,    # personaje elegido
        "foto_path": None,       # ruta de la foto subida (modo FOTO_ID)
        "chat_personaje": None,  # personaje en pantalla (al que se pregunta)
        "paso": 0,               # paso actual del asistente (0, 1, 2)
        "generando": False,      # True mientras se está generando la escena
        "generado_para": None,   # (personaje, ubicacion, foto) de la última escena hecha
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
    loading_panel = ft.Container(
        visible=False,
        width=460,
        height=260,
        border_radius=18,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[ft.Colors.PURPLE_300, ft.Colors.PINK_200],
        ),
        alignment=ft.alignment.center,
        content=ft.Column(
            [
                loading_emoji,
                loading_text,
                ft.ProgressBar(
                    width=240,
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=16,
        ),
    )
    result_image = ft.Image(width=460, fit=ft.ImageFit.CONTAIN, visible=False)

    # Chat (RAG)
    chat_titulo = ft.Text("💬 Habla con el personaje", size=16, weight=ft.FontWeight.BOLD)
    # auto_scroll=True: al añadir una burbuja (pregunta o respuesta) el chat baja solo
    # hasta el final, para no tener que arrastrar a mano y ver siempre lo último.
    chat_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=240, auto_scroll=True)
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
    chat_panel = ft.Container(
        visible=False,
        padding=14,
        bgcolor=ft.Colors.WHITE,
        border=ft.border.all(1, ft.Colors.GREY_200),
        border_radius=18,
        content=ft.Column(
            [chat_titulo, chat_column, ft.Row([pregunta_field, preguntar_button])],
            spacing=10,
        ),
    )

    # Contenedor donde se dibuja el paso actual.
    content = ft.Container(padding=24, width=880)

    # -----------------------------------------------------------------------
    # Helpers de presentación
    # -----------------------------------------------------------------------
    def nombre_lugar() -> str:
        if state["ubicacion_id"] == FOTO_ID:
            return "tu foto"
        if state["ubicacion_id"]:
            return UBICACIONES[state["ubicacion_id"]]["label"]
        return ""

    def tarjeta(emoji: str, label: str, seleccionada: bool, on_click) -> ft.Container:
        """Tarjeta grande y redondeada (lugar o personaje), con resalte al elegir."""
        return ft.Container(
            width=140,
            height=140,
            padding=8,
            bgcolor=ft.Colors.AMBER_50 if seleccionada else ft.Colors.WHITE,
            border=ft.border.all(4, ft.Colors.AMBER_400 if seleccionada else ft.Colors.GREY_200),
            border_radius=24,
            ink=True,
            on_click=on_click,
            alignment=ft.alignment.center,
            scale=1.06 if seleccionada else 1.0,
            animate_scale=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=ft.Colors.with_opacity(0.15, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            content=ft.Column(
                [
                    ft.Text(emoji, size=50),
                    ft.Text(label, size=13, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
        )

    def build_header() -> ft.Control:
        fila_cabecera = [
            ft.Column(
                [
                    ft.Text("🕰️ Máquina del Tiempo", size=26,
                            weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ft.Text("¡Viaja sin salir de tu cuarto!", size=14, color=ft.Colors.WHITE),
                ],
                expand=True,
                spacing=2,
            ),
        ]
        # "Probar conexión" es una herramienta de diagnóstico: solo en modo DEBUG.
        # En la versión final para el niño no aparece.
        if DEBUG:
            fila_cabecera.append(
                ft.OutlinedButton(
                    "🔌 Probar conexión",
                    on_click=on_check_backend,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        side=ft.BorderSide(1, ft.Colors.WHITE),
                        shape=ft.RoundedRectangleBorder(radius=20),
                    ),
                )
            )
        hero = ft.Container(
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=[ft.Colors.PURPLE_400, ft.Colors.PINK_300],
            ),
            border_radius=24,
            padding=24,
            content=ft.Row(
                fila_cabecera,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        return ft.Column([hero, build_stepper()], spacing=16)

    def build_stepper() -> ft.Control:
        items = []
        nombres = [("1", "Personaje"), ("2", "Lugar"), ("3", "¡Listo!")]
        for i, (num, nom) in enumerate(nombres):
            activo = i == state["paso"]
            hecho = i < state["paso"]
            color = ft.Colors.PURPLE_400 if (activo or hecho) else ft.Colors.GREY_300
            circulo = ft.Container(
                width=34, height=34, border_radius=17, bgcolor=color,
                alignment=ft.alignment.center,
                content=ft.Text("✓" if hecho else num, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            )
            items.append(
                ft.Row(
                    [circulo, ft.Text(nom, weight=ft.FontWeight.BOLD if activo else ft.FontWeight.NORMAL,
                                      color=ft.Colors.GREY_900 if activo else ft.Colors.GREY_500)],
                    spacing=6,
                )
            )
            if i < 2:
                items.append(ft.Container(width=28, height=3, bgcolor=ft.Colors.GREY_300, border_radius=2))
        return ft.Row(items, alignment=ft.MainAxisAlignment.CENTER,
                      vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)

    # -----------------------------------------------------------------------
    # Paso 1 — Lugar
    # -----------------------------------------------------------------------
    def build_step_lugar() -> ft.Control:
        tarjetas = []
        for uid, datos in UBICACIONES.items():
            tarjetas.append(
                tarjeta(datos["emoji"], datos["label"], state["ubicacion_id"] == uid,
                        lambda e, i=uid: seleccionar_ubicacion(i))
            )
        # Tarjeta especial "Mi foto".
        foto_sel = state["ubicacion_id"] == FOTO_ID
        foto_label = "✓ ¡Foto lista!" if (foto_sel and state["foto_path"]) else "Mi foto"
        tarjetas.append(tarjeta("📷", foto_label, foto_sel, lambda e: abrir_selector_foto()))

        nav = ft.Row(
            [
                ft.OutlinedButton("←  Atrás", on_click=lambda e: ir_paso(0), style=BTN_ROUND),
                ft.ElevatedButton("Siguiente  →", on_click=lambda e: ir_paso(2),
                                  disabled=not state["ubicacion_id"],
                                  bgcolor=ft.Colors.PURPLE_400, color=ft.Colors.WHITE, style=BTN_PRIMARY),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        return ft.Column(
            [
                ft.Text("¿A dónde quieres viajar? 📍", size=22, weight=ft.FontWeight.BOLD),
                ft.Row(tarjetas, wrap=True, spacing=14, run_spacing=14),
                ft.Text("📷 Si usas tu foto, ¡saca tu cuarto vacío! 😊", size=12,
                        italic=True, color=ft.Colors.GREY_600),
                status_text,
                nav,
            ],
            spacing=16,
        )

    # -----------------------------------------------------------------------
    # Paso 2 — Personaje
    # -----------------------------------------------------------------------
    def build_step_personaje() -> ft.Control:
        secciones = [ft.Text("¿A quién quieres conocer? 🎭", size=22, weight=ft.FontWeight.BOLD)]
        for titulo, categorias in GRUPOS.items():
            fila = [
                tarjeta(datos["emoji"], datos["label"], state["personaje_id"] == pid,
                        lambda e, i=pid: seleccionar_personaje(i))
                for pid, datos in personajes_de_grupo(categorias)
            ]
            if fila:
                secciones.append(ft.Text(titulo, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_700))
                secciones.append(ft.Row(fila, wrap=True, spacing=14, run_spacing=14))

        nav = ft.Row(
            [
                ft.ElevatedButton("Siguiente  →", on_click=lambda e: ir_paso(1),
                                  disabled=not state["personaje_id"],
                                  bgcolor=ft.Colors.PURPLE_400, color=ft.Colors.WHITE, style=BTN_PRIMARY),
            ],
            alignment=ft.MainAxisAlignment.END,
        )
        secciones.append(nav)
        return ft.Column(secciones, spacing=12)

    # -----------------------------------------------------------------------
    # Paso 3 — Generar + resultado + chat
    # -----------------------------------------------------------------------
    def build_step_generar() -> ft.Control:
        pid = state["personaje_id"]
        pj = PERSONAJES[pid]["label"] if pid else ""
        emoji = PERSONAJES[pid]["emoji"] if pid else ""
        summary_text.value = f"{emoji} {pj}  en  {nombre_lugar()}"
        if state["chat_personaje"]:
            chat_titulo.value = f"💬 Habla con {PERSONAJES[state['chat_personaje']]['label']}"

        nav = ft.Row(
            [
                ft.OutlinedButton("←  Atrás", on_click=lambda e: ir_paso(1), style=BTN_ROUND),
                ft.OutlinedButton("🔄 Empezar de nuevo", on_click=empezar_de_nuevo, style=BTN_ROUND),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        # La escena se genera AUTOMÁTICAMENTE al llegar a este paso (ver _auto_generar):
        # ya no hay botón "¡Generar!". Mientras genera se ve loading_panel animado;
        # al terminar, la imagen y el chat.
        return ft.Column(
            [
                ft.Text("¡Tu escena! 🎉", size=22, weight=ft.FontWeight.BOLD),
                ft.Container(summary_text, padding=14, bgcolor=ft.Colors.PURPLE_50, border_radius=14),
                ft.Container(loading_panel, alignment=ft.alignment.center),
                ft.Container(result_image, alignment=ft.alignment.center),
                status_text,
                chat_panel,
                nav,
            ],
            spacing=16,
        )

    # -----------------------------------------------------------------------
    # Render: dibuja el paso actual
    # -----------------------------------------------------------------------
    def render():
        if state["paso"] == 0:
            cuerpo = build_step_personaje()
        elif state["paso"] == 1:
            cuerpo = build_step_lugar()
        else:
            cuerpo = build_step_generar()
        content.content = ft.Column([build_header(), cuerpo], spacing=20)
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
    def seleccionar_ubicacion(uid: str):
        state["ubicacion_id"] = uid
        state["foto_path"] = None  # salimos del modo foto
        render()

    def seleccionar_personaje(pid: str):
        state["personaje_id"] = pid
        render()

    def on_foto_selected(e: ft.FilePickerResultEvent):
        if not e.files:
            return  # el usuario canceló
        state["foto_path"] = e.files[0].path
        state["ubicacion_id"] = FOTO_ID
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
            status_text.value = "🎉 ¡Listo! Ahora puedes hacerle preguntas abajo. 💬"
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
        pregunta_field.disabled = True
        preguntar_button.disabled = True
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
        except api_client.BackendError as exc:
            pensando.value = f"❌ {exc}"
        finally:
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

    page.add(ft.Row([content], alignment=ft.MainAxisAlignment.CENTER))
    render()


if __name__ == "__main__":
    ft.app(target=main)
