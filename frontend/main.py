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

import threading

import flet as ft

import api_client
from personajes import GRUPOS, PERSONAJES, personajes_de_grupo
from ubicaciones import UBICACIONES

# Id especial (no es una ubicación real) para el modo "Usar mi foto".
FOTO_ID = "__foto__"


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
                "Prueba otra combinación."
            )
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
    )


if __name__ == "__main__":
    ft.app(target=main)
