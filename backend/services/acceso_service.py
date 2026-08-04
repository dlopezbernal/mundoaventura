"""
services/acceso_service.py — Candado del túnel por código de acceso (Hito 2)
============================================================================

El despliegue es un túnel público (ngrok/Colab). Los endpoints del niño (chat,
generación, voz) NO pueden ir detrás del acceso admin —los usa un niño—, pero sí
detrás de un candado ligero contra escaneo automático: un CÓDIGO DE ACCESO
compartido que el frontend envía en la cabecera `X-Access-Code`.

No es autenticación fuerte (el código viaja en el `.env` del frontend); es una
barrera para que un bot que descubre la URL del túnel no pueda vaciar el crédito
de las APIs con un par de peticiones. La comparación usa `hmac.compare_digest`
(tiempo constante, no filtra el código carácter a carácter).

Si `ACCESS_CODE` está VACÍO, el candado queda DESACTIVADO (cómodo en local). En el
túnel de la demo se pone un código en el `.env` del backend y el mismo en el del
frontend (VITE_ACCESS_CODE).
"""

import hmac

from fastapi import Header, HTTPException

from backend import config


def requiere_codigo_acceso(x_access_code: str | None = Header(default=None)) -> None:
    """Deja pasar si el candado está desactivado o la cabecera trae el código correcto.

    Se aplica a los endpoints que CUESTAN dinero (generación, chat, transcripción).
    Los catálogos (GET personajes/ubicaciones) siguen públicos: son lecturas baratas.
    """
    esperado = config.ACCESS_CODE
    if not esperado:
        return  # candado desactivado (no hay código configurado)
    if not x_access_code or not hmac.compare_digest(x_access_code, esperado):
        raise HTTPException(
            status_code=401,
            detail="Código de acceso incorrecto o ausente.",
        )
