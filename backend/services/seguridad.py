"""
services/seguridad.py — Hashing de credenciales (Hito 9.2)
==========================================================

Utilidades compartidas para guardar credenciales **hasheadas**, nunca en claro:
PBKDF2-HMAC-SHA256 con una sal por credencial, en formato ``salt$hash`` (hex).

Es el mismo esquema que ya usaba ``admin_service`` (para la credencial de admin),
extraído aquí para reutilizarlo sin duplicarlo cuando aparecieron las **cuentas de
familia** (email + contraseña). La comparación se hace en tiempo constante (``hmac.compare_digest``)
para no filtrar información por el tiempo de respuesta.
"""

import hashlib
import hmac
import secrets

# 200k iteraciones = buen equilibrio coste/seguridad en 2026 (igual que el PIN).
_ITERACIONES = 200_000


def hashear(secreto: str, salt_hex: str | None = None) -> str:
    """Deriva el hash del secreto con PBKDF2. Devuelve ``'salt$hash'`` en hex.

    Sin ``salt_hex`` genera una sal nueva (al CREAR la credencial); al VERIFICAR se
    pasa la sal guardada para reproducir el mismo hash.
    """
    salt_hex = salt_hex or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", secreto.encode("utf-8"), bytes.fromhex(salt_hex), _ITERACIONES
    )
    return f"{salt_hex}${dk.hex()}"


def verificar(secreto: str, guardado: str) -> bool:
    """Comprueba el secreto contra el ``'salt$hash'`` guardado (tiempo constante)."""
    try:
        salt_hex, _ = guardado.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hashear(secreto, salt_hex), guardado)
