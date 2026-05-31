"""
frontend/main.py — Interfaz de usuario
=======================================

Aplicación Flet que guía al niño:
  1. Elegir un LUGAR: una ubicación predefinida (laboratorio, bosque...) o
     "📷 Mi foto" para subir una foto suya (se estiliza a Pixar 3D y se le añade
     el personaje encima, todo coherente).
  2. Elegir un PERSONAJE (t-rex, Leonardo da Vinci, Sherlock Holmes...).
  3. Pulsar «Generar»: se envía al backend, que pide la imagen a Replicate.

Arráncala con:
    flet run frontend/main.py
"""

import os
import threading

import flet as ft

import api_client  # al importarse, carga el .env (incluida la variable DEBUG)
from personajes import GRUPOS, PERSONAJES, personajes_de_grupo
from ubicaciones import UBICACIONES

# Id especial (no es una ubicación real) para el modo "Usar mi foto".
FOTO_ID = "__foto__"

# Modo desarrollo: si DEBUG está activo, el chat muestra una etiqueta de origen
# ([RAG]/[LLM]) en cada respuesta. En la versión final para el usuario, no.
DEBUG = os.getenv("DEBUG", "false").strip().lower() in ("1", "true", "yes", "on")

# Icono según el origen de la respuesta (solo se muestra si DEBUG).
ICONO_ORIGEN = {
    "RAG": "🟢",       # fundamentada en la enciclopedia
    "GENERAL": "🟡",   # conocimiento propio del modelo (no RAG)
}


def construir_tag_debug(result: dict) -> str:
    """Crea la etiqueta de depuración con origen + método + distancia.

    Ej.: "🟢 [RAG · umbral · d=0.42] "  ó  "🟡 [GENERAL · llm] "
    Solo se usa cuando DEBUG está activo.
    """
    origen = result.get("origen", "?")
    icono = ICONO_ORIGEN.get(origen, "⚪")
    partes = [origen]
    if result.get("metodo"):
        partes.append(result["metodo"])
    if result.get("distancia") is not None:
        partes.append(f"d={result['distancia']:.2f}")
    if result.get("pregunta_traducida"):
        partes.append(f'"{result["pregunta_traducida"]}"')
    return f"{icono} [{' · '.join(partes)}] "


def main(page: ft.Page):
    # -----------------------------------------------------------------------
    # Configuración general de la ventana
    # -----------------------------------------------------------------------
    page.title = "Máquina del Tiempo — Elige lugar y personaje"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    # -----------------------------------------------------------------------
    # "Estado" de la app.
    # -----------------------------------------------------------------------
    state = {
        "ubicacion_id": None,   # ubicación elegida ("laboratorio"..., o FOTO_ID)
        "personaje_id": None,   # personaje elegido
        "foto_path": None,      # ruta de la foto subida (solo en modo FOTO_ID)
        "chat_personaje": None,  # personaje que está EN PANTALLA (al que se pregunta)
    }

    status_text = ft.Text("Elige un lugar y un personaje para empezar.", size=14)
    progress = ft.ProgressRing(visible=False)

    result_image = ft.Image(width=512, fit=ft.ImageFit.CONTAIN, visible=False)

    tarjetas_ubicacion: dict[str, ft.Container] = {}
    tarjetas_personaje: dict[str, ft.Container] = {}

    # -----------------------------------------------------------------------
    # Tarjetas (mismo patrón visual para ubicaciones y personajes)
    # -----------------------------------------------------------------------
    def crear_tarjeta(item_id: str, emoji: str, label: str, on_click) -> ft.Container:
        return ft.Container(
            width=130,
            height=120,
            padding=8,
            border=ft.border.all(3, ft.Colors.GREY_300),
            border_radius=12,
            bgcolor=ft.Colors.WHITE,
            alignment=ft.alignment.center,
            ink=True,
            content=ft.Column(
                [
                    ft.Text(emoji, size=44),
                    ft.Text(label, size=12, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            on_click=lambda _e, i=item_id: on_click(i),
        )

    def resaltar(tarjetas: dict[str, ft.Container], elegido_id: str):
        """Marca con borde azul la tarjeta elegida y apaga las demás."""
        for cid, card in tarjetas.items():
            elegido = cid == elegido_id
            card.border = ft.border.all(
                3, ft.Colors.BLUE_400 if elegido else ft.Colors.GREY_300
            )
            card.bgcolor = ft.Colors.BLUE_50 if elegido else ft.Colors.WHITE

    def nombre_lugar() -> str:
        """Texto del lugar elegido (ubicación predefinida o 'tu foto')."""
        if state["ubicacion_id"] == FOTO_ID:
            return "tu foto"
        return UBICACIONES[state["ubicacion_id"]]["label"]

    def actualizar_estado_boton():
        """Habilita «Generar» solo cuando hay lugar y personaje elegidos."""
        listo = bool(state["ubicacion_id"] and state["personaje_id"])
        generate_button.disabled = not listo
        if listo:
            pj = PERSONAJES[state["personaje_id"]]["label"]
            status_text.value = (
                f"¡Listo! Vas a crear: {pj} en {nombre_lugar()}. Pulsa «Generar». 🎨"
            )

    def seleccionar_ubicacion(uid: str):
        state["ubicacion_id"] = uid
        state["foto_path"] = None          # salimos del modo foto
        foto_card_label.value = "Mi foto"
        resaltar(tarjetas_ubicacion, uid)
        if not state["personaje_id"]:
            status_text.value = "Ahora elige un personaje. 🦖"
        actualizar_estado_boton()
        page.update()

    def seleccionar_personaje(pid: str):
        state["personaje_id"] = pid
        resaltar(tarjetas_personaje, pid)
        if not state["ubicacion_id"]:
            status_text.value = "Ahora elige un lugar (o sube tu foto). 🧪"
        actualizar_estado_boton()
        page.update()

    # -----------------------------------------------------------------------
    # Modo "Usar mi foto": tarjeta especial que abre el selector de archivos
    # -----------------------------------------------------------------------
    def on_foto_selected(e: ft.FilePickerResultEvent):
        if not e.files:
            return  # el usuario canceló
        state["foto_path"] = e.files[0].path
        state["ubicacion_id"] = FOTO_ID
        foto_card_label.value = "✓ ¡Foto lista!"
        resaltar(tarjetas_ubicacion, FOTO_ID)
        if not state["personaje_id"]:
            status_text.value = "Ahora elige un personaje. 🦖"
        actualizar_estado_boton()
        page.update()

    file_picker = ft.FilePicker(on_result=on_foto_selected)
    page.overlay.append(file_picker)

    def abrir_selector_foto(_i):
        file_picker.pick_files(
            allowed_extensions=["png", "jpg", "jpeg", "bmp", "webp"],
            allow_multiple=False,
        )

    foto_card_label = ft.Text("Mi foto", size=12, text_align=ft.TextAlign.CENTER)

    # -----------------------------------------------------------------------
    # Catálogo de LUGARES (ubicaciones predefinidas + tarjeta "Mi foto")
    # -----------------------------------------------------------------------
    fila_ubicaciones = ft.Row(wrap=True, spacing=10, run_spacing=10)
    for uid, datos in UBICACIONES.items():
        card = crear_tarjeta(uid, datos["emoji"], datos["label"], seleccionar_ubicacion)
        tarjetas_ubicacion[uid] = card
        fila_ubicaciones.controls.append(card)

    # Tarjeta especial "Mi foto" (usa un label mutable para mostrar "¡Foto lista!").
    foto_card = ft.Container(
        width=130, height=120, padding=8,
        border=ft.border.all(3, ft.Colors.GREY_300), border_radius=12,
        bgcolor=ft.Colors.WHITE, alignment=ft.alignment.center, ink=True,
        content=ft.Column(
            [ft.Text("📷", size=44), foto_card_label],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER, spacing=6,
        ),
        on_click=abrir_selector_foto,
    )
    tarjetas_ubicacion[FOTO_ID] = foto_card
    fila_ubicaciones.controls.append(foto_card)

    # -----------------------------------------------------------------------
    # Catálogo de PERSONAJES (agrupado por categoría)
    # -----------------------------------------------------------------------
    personaje_controls: list[ft.Control] = []
    for titulo, categorias in GRUPOS.items():
        personaje_controls.append(ft.Text(titulo, size=14, weight=ft.FontWeight.BOLD))
        fila = ft.Row(wrap=True, spacing=10, run_spacing=10)
        for pid, datos in personajes_de_grupo(categorias):
            card = crear_tarjeta(pid, datos["emoji"], datos["label"], seleccionar_personaje)
            tarjetas_personaje[pid] = card
            fila.controls.append(card)
        personaje_controls.append(fila)
    catalogo_personajes = ft.Column(personaje_controls, spacing=8)

    # -----------------------------------------------------------------------
    # Generar la escena (llamada al backend en un hilo aparte)
    # -----------------------------------------------------------------------
    def generar(_):
        if not state["ubicacion_id"] or not state["personaje_id"]:
            status_text.value = "Elige un lugar y un personaje primero. 🙂"
            page.update()
            return
        progress.visible = True
        generate_button.disabled = True
        status_text.value = "Generando tu escena con Replicate... 🎨 (unos segundos)"
        page.update()
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
            status_text.value = (
                f"🎉 ¡Aquí tienes a {PERSONAJES[pid]['label']} en {nombre_lugar()}! "
                "Ahora puedes hacerle preguntas abajo. 💬"
            )
            # Activamos el chat para ESTE personaje (al que se ve en pantalla).
            state["chat_personaje"] = pid
            chat_titulo.value = f"💬 Habla con {PERSONAJES[pid]['label']}"
            chat_column.controls.clear()  # nueva escena = conversación nueva
            chat_panel.visible = True
            pregunta_field.disabled = False
            preguntar_button.disabled = False
        except api_client.BackendError as exc:
            status_text.value = f"❌ {exc}"
        finally:
            progress.visible = False
            generate_button.disabled = False
            page.update()

    generate_button = ft.ElevatedButton("🎨 Generar", disabled=True, on_click=generar)

    # -----------------------------------------------------------------------
    # Botón opcional para comprobar la conexión con el backend
    # -----------------------------------------------------------------------
    def on_check_backend(_):
        try:
            info = api_client.check_health()
            token = "sí" if info.get("token_configurado") else "NO"
            status_text.value = (
                f"✅ Backend OK · modelo={info.get('replicate_model')} · "
                f"token configurado: {token}"
            )
        except api_client.BackendError as exc:
            status_text.value = f"❌ {exc}"
        page.update()

    check_button = ft.OutlinedButton("🔌 Probar backend", on_click=on_check_backend)

    # -----------------------------------------------------------------------
    # Conversación con el personaje (RAG) — aparece tras generar la escena
    # -----------------------------------------------------------------------
    chat_titulo = ft.Text("💬 Habla con el personaje", size=16, weight=ft.FontWeight.BOLD)

    # Columna donde se van apilando las preguntas (niño) y respuestas (personaje).
    chat_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=240)

    # Caja de texto para escribir la pregunta. (La voz/micro llegará en el siguiente paso.)
    pregunta_field = ft.TextField(
        hint_text="Escribe tu pregunta... (ej. ¿Qué comes?)",
        expand=True,
        disabled=True,
        on_submit=lambda _e: preguntar(_e),  # permite enviar con la tecla Enter
    )
    preguntar_button = ft.ElevatedButton("Preguntar", disabled=True)

    def _add_burbuja(texto: str, es_nino: bool):
        """Añade una 'burbuja' de conversación a la columna del chat."""
        chat_column.controls.append(
            ft.Container(
                content=ft.Text(texto, size=13, selectable=True),
                bgcolor=ft.Colors.BLUE_50 if es_nino else ft.Colors.GREEN_50,
                padding=10,
                border_radius=10,
                alignment=ft.alignment.center_right if es_nino else ft.alignment.center_left,
            )
        )

    def preguntar(_):
        pid = state["chat_personaje"]
        texto = (pregunta_field.value or "").strip()
        if not pid or not texto:
            return  # no hay personaje en pantalla o la caja está vacía

        # Mostramos la pregunta del niño y limpiamos la caja.
        _add_burbuja(f"🧒 {texto}", es_nino=True)
        pregunta_field.value = ""
        pregunta_field.disabled = True
        preguntar_button.disabled = True
        # "Pensando..." como burbuja temporal del personaje.
        pensando = ft.Text("🤔 Pensando...", size=13, italic=True)
        chat_column.controls.append(pensando)
        page.update()

        threading.Thread(
            target=_run_ask, args=(pid, texto, pensando), daemon=True
        ).start()

    def _run_ask(pid: str, texto: str, pensando: ft.Text):
        try:
            result = api_client.ask(pid, texto)
            respuesta = result.get("respuesta", "(sin respuesta)")
            chat_column.controls.remove(pensando)  # quitamos el "Pensando..."
            # En modo DEBUG anteponemos el origen + método + distancia.
            prefijo = construir_tag_debug(result) if DEBUG else ""
            _add_burbuja(
                f"{prefijo}{PERSONAJES[pid]['emoji']} {respuesta}", es_nino=False
            )
        except api_client.BackendError as exc:
            pensando.value = f"❌ {exc}"
        finally:
            pregunta_field.disabled = False
            preguntar_button.disabled = False
            page.update()

    preguntar_button.on_click = preguntar

    # Panel completo del chat (oculto hasta que se genera una escena).
    chat_panel = ft.Container(
        visible=False,
        padding=12,
        margin=ft.margin.only(top=10),
        border=ft.border.all(1, ft.Colors.GREY_300),
        border_radius=12,
        content=ft.Column(
            [
                chat_titulo,
                chat_column,
                ft.Row([pregunta_field, preguntar_button]),
            ],
            spacing=10,
        ),
    )

    # -----------------------------------------------------------------------
    # Montaje final de la pantalla
    # -----------------------------------------------------------------------
    page.add(
        ft.Text("🕰️ Elige un lugar y un personaje", size=22, weight=ft.FontWeight.BOLD),
        ft.Text(
            "Combina cualquier lugar con cualquier personaje (¡un t-rex en un "
            "laboratorio!) o sube tu propia foto y conviértela en una escena Pixar.",
            size=13,
            color=ft.Colors.GREY_700,
        ),
        ft.Row([check_button]),
        ft.Text("📍 Lugar", size=16, weight=ft.FontWeight.BOLD),
        fila_ubicaciones,
        ft.Text(
            "📷 Si usas tu foto, ¡saca tu cuarto vacío! Si sale gente, puede quedar "
            "un poco rara. 😊",
            size=12,
            italic=True,
            color=ft.Colors.GREY_700,
        ),
        ft.Text("🎭 Personaje", size=16, weight=ft.FontWeight.BOLD),
        catalogo_personajes,
        ft.Row([generate_button]),
        ft.Row([progress, status_text], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Container(content=result_image, border=ft.border.all(1, ft.Colors.GREY_300)),
        chat_panel,
    )


if __name__ == "__main__":
    ft.app(target=main)
