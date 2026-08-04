"""
services/secrets_service.py — Claves API (leer/escribir el .env con cuidado)
============================================================================

Gestiona los TRES secretos del proyecto (Replicate, DeepL, ElevenLabs) para la
pantalla de configuración "APIs" (Hito 2). A diferencia de los ajustes normales
(que viven en SQLite, ver settings_service), los secretos NO van a la BBDD: siguen
en el `.env` (patrón del proyecto, fuera de git).

Reglas de oro:
  - NUNCA se devuelve la clave completa al frontend en `estado()`: solo un flag
    `configurado` y un valor ENMASCARADO. Revelar la clave es una petición aparte
    (`revelar`, para el icono del ojo 👁).
  - Escritura del `.env` con RED DE SEGURIDAD: copia previa (`.env.bak`) y escritura
    ATÓMICA (fichero temporal + `replace`), preservando comentarios y el resto de
    variables. Así un fallo a mitad no corrompe el `.env`.
  - Aplicar EN CALIENTE: al guardar una clave se actualiza también la copia en
    memoria (`os.environ` + `config`) y se INVALIDAN los clientes perezosos de
    DeepL/ElevenLabs, para que la siguiente petición use la clave nueva sin
    reiniciar el backend.
"""

import os
import shutil

from backend import config
from backend.services import (
    llm_service,
    replicate_client,
    stt_service,
    translation_service,
    voice_service,
)

# Metadatos de cada proveedor: variable del .env, nombre visible y enlace de alta.
_PROVEEDORES: dict[str, dict[str, str]] = {
    "replicate": {
        "variable": "REPLICATE_API_TOKEN",
        "nombre": "Replicate",
        "ayuda_url": "https://replicate.com/account/api-tokens",
    },
    "deepl": {
        "variable": "DEEPL_API_KEY",
        "nombre": "DeepL",
        "ayuda_url": "https://www.deepl.com/pro-api",
    },
    "elevenlabs": {
        "variable": "ELEVENLABS_API_KEY",
        "nombre": "ElevenLabs",
        "ayuda_url": "https://elevenlabs.io/app/settings/api-keys",
    },
    # Clave del endpoint openai-compatible (Hito 5). Solo se usa si LLM_PROVIDER=openai
    # (Groq, Mistral, OpenRouter…); Ollama local no la necesita.
    "llm": {
        "variable": "LLM_API_KEY",
        "nombre": "LLM (endpoint OpenAI-compatible)",
        "ayuda_url": "https://console.groq.com/keys",
    },
    # Clave de Groq para STT (Whisper), solo si STT_PROVIDER=groq (Hito 7). Separada de
    # la clave "llm" a propósito: son cuentas/servicios distintos aunque coincida Groq.
    "groq": {
        "variable": "GROQ_API_KEY",
        "nombre": "Groq (transcripción Whisper)",
        "ayuda_url": "https://console.groq.com/keys",
    },
}

# Ruta del .env (bootstrap). Módulo-variable para poder apuntarla a un fichero
# temporal en las pruebas sin tocar el .env real.
_ENV_PATH = config.PROJECT_ROOT / ".env"


def _valor(proveedor: str) -> str:
    """Valor VIGENTE de la clave (lee la copia en memoria de config, ya actualizada)."""
    return getattr(config, _PROVEEDORES[proveedor]["variable"], "") or ""


def _enmascarar(secreto: str) -> str | None:
    """Enmascara un secreto dejando visibles solo los últimos 4 (o None si vacío)."""
    if not secreto:
        return None
    if len(secreto) <= 4:
        return "•" * len(secreto)
    return "••••••" + secreto[-4:]


def estado() -> list[dict]:
    """Estado de los 3 proveedores: configurado (bool) + valor enmascarado (nunca completo)."""
    return [
        {
            "proveedor": proveedor,
            "variable": meta["variable"],
            "nombre": meta["nombre"],
            "ayuda_url": meta["ayuda_url"],
            "configurado": bool(_valor(proveedor)),
            "enmascarado": _enmascarar(_valor(proveedor)),
        }
        for proveedor, meta in _PROVEEDORES.items()
    ]


def revelar(proveedor: str) -> str | None:
    """Devuelve la clave COMPLETA de un proveedor (para el icono del ojo).

    Es una petición aparte, deliberadamente separada de `estado()`, para no enviar
    nunca la clave completa "por si acaso". El endpoint va detrás del PIN de adulto
    (requiere_admin, aplicado en bloque desde main.py).
    """
    if proveedor not in _PROVEEDORES:
        raise ValueError(f"Proveedor desconocido: '{proveedor}'.")
    return _valor(proveedor) or None


# ---------------------------------------------------------------------------
# Escritura del .env (función pura + escritura atómica con backup)
# ---------------------------------------------------------------------------
def _aplicar_cambios_env(contenido: str, cambios: dict[str, str]) -> str:
    """Devuelve el .env con las variables de `cambios` (NOMBRE→valor) actualizadas.

    Preserva comentarios y el resto de líneas. Si la variable ya existe, sustituye
    su línea; si no, la añade al final. Es una FUNCIÓN PURA (fácil de testear).
    """
    pendientes = dict(cambios)
    salida: list[str] = []
    for linea in contenido.splitlines():
        stripped = linea.lstrip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            nombre = stripped.split("=", 1)[0].strip()
            if nombre in pendientes:
                salida.append(f"{nombre}={pendientes.pop(nombre)}")
                continue
        salida.append(linea)
    # Variables que no existían aún: se añaden al final.
    for nombre, valor in pendientes.items():
        salida.append(f"{nombre}={valor}")
    texto = "\n".join(salida)
    # Conserva el salto final si el original lo tenía (o si estaba vacío).
    if not contenido or contenido.endswith("\n"):
        texto += "\n"
    return texto


def _escribir_env_atomico(cambios_env: dict[str, str]) -> None:
    """Escribe los cambios en el .env: copia de seguridad + temporal + replace."""
    ruta = _ENV_PATH
    contenido = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    nuevo = _aplicar_cambios_env(contenido, cambios_env)

    # Red de seguridad: copia previa (.env.bak) antes de tocar el original.
    if ruta.exists():
        shutil.copy2(ruta, ruta.with_name(ruta.name + ".bak"))

    # Escritura atómica: escribir a un temporal y renombrar (replace es atómico
    # dentro del mismo sistema de ficheros), para no dejar el .env a medias.
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(nuevo, encoding="utf-8")
    tmp.replace(ruta)


def guardar(cambios: dict[str, str]) -> list[dict]:
    """Guarda una o varias claves en el .env y las aplica en caliente.

    `cambios` es {proveedor: clave} (solo los proveedores que se quieran cambiar).
    Lanza ValueError (→ HTTP 400) si algún proveedor o clave es inválido, y en ese
    caso NO escribe nada. Devuelve el `estado()` actualizado (enmascarado).
    """
    # 1) Validar TODO antes de escribir (o se guarda todo, o nada).
    cambios_env: dict[str, str] = {}
    for proveedor, clave in cambios.items():
        if proveedor not in _PROVEEDORES:
            raise ValueError(f"Proveedor desconocido: '{proveedor}'.")
        clave = (clave or "").strip()
        if not clave:
            raise ValueError(f"La clave de '{proveedor}' no puede estar vacía.")
        if "\n" in clave or "\r" in clave:
            raise ValueError(f"La clave de '{proveedor}' no puede contener saltos de línea.")
        if "•" in clave:
            raise ValueError(
                f"La clave de '{proveedor}' parece el valor enmascarado, no una clave real. "
                "Escribe la clave completa."
            )
        cambios_env[_PROVEEDORES[proveedor]["variable"]] = clave

    # 2) Escribir el .env de forma segura.
    _escribir_env_atomico(cambios_env)

    # 3) Aplicar en caliente: actualizar la copia en memoria e invalidar clientes.
    for proveedor, clave in cambios.items():
        variable = _PROVEEDORES[proveedor]["variable"]
        limpio = clave.strip()
        os.environ[variable] = limpio  # respaldo (algunas libs lo leen del entorno)
        setattr(config, variable, limpio)  # lo leen los clientes perezosos de los servicios
    # Invalidar los clientes perezosos para que la siguiente petición use la clave nueva.
    translation_service.reiniciar()
    voice_service.reiniciar()
    replicate_client.reiniciar()
    llm_service.reiniciar()
    stt_service.reiniciar()

    return estado()


# ---------------------------------------------------------------------------
# Probar conexión (llamada ligera autenticada por proveedor)
# ---------------------------------------------------------------------------
def _probar_replicate() -> dict:
    token = _valor("replicate")
    if not token:
        return {"ok": False, "mensaje": "Falta la clave de Replicate."}
    try:
        import replicate

        replicate.Client(api_token=token).accounts.current()  # llamada ligera autenticada
        return {"ok": True, "mensaje": "Replicate conectado."}
    except Exception as exc:
        return {"ok": False, "mensaje": f"No se pudo conectar con Replicate: {exc}"}


def probar(proveedor: str) -> dict:
    """Prueba la conexión de un proveedor: {ok: bool, mensaje: str}."""
    if proveedor not in _PROVEEDORES:
        raise ValueError(f"Proveedor desconocido: '{proveedor}'.")
    if proveedor == "replicate":
        return _probar_replicate()
    if proveedor == "deepl":
        return translation_service.probar()
    if proveedor == "llm":
        return llm_service.probar()
    if proveedor == "groq":
        return stt_service.probar()
    return voice_service.probar()
