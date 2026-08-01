"""
routers/limites.py — Lectura de subidas con tope de tamaño (Hito 2)
===================================================================

Los endpoints multipart (foto, audio, documentos) hacían `await archivo.read()`,
cargando el fichero ENTERO en memoria sin comprobar nada. Una URL pública podía
subir un fichero gigante y agotar la RAM del proceso.

`leer_con_limite` corta el problema en dos frentes:
  1. Rechazo rápido: si el parser de multipart ya conoce el tamaño (`archivo.size`)
     y supera el máximo, devuelve 413 SIN leer nada a memoria.
  2. Lectura por trozos con tope: aunque `size` no venga o mienta, se lee en
     bloques y se aborta en cuanto se pasa del máximo. Así la memoria queda acotada
     a ~un bloque por encima del límite, nunca al tamaño completo del atacante.

Devuelve HTTP 413 (Payload Too Large) con un mensaje claro, no un 500.
"""

from fastapi import HTTPException, UploadFile

# Tamaño de bloque de lectura (1 MiB): compromiso entre nº de lecturas y memoria.
_BLOQUE = 1024 * 1024


async def leer_con_limite(archivo: UploadFile, max_mb: float, etiqueta: str) -> bytes:
    """Lee un UploadFile entero pero aborta con 413 si supera `max_mb` megabytes."""
    max_bytes = int(max_mb * 1024 * 1024)

    # 1) Rechazo rápido con el tamaño ya conocido por el parser (si está disponible).
    if archivo.size is not None and archivo.size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"El {etiqueta} supera el máximo permitido de {max_mb:g} MB.",
        )

    # 2) Lectura por trozos con tope (por si size es None o poco fiable).
    trozos: list[bytes] = []
    total = 0
    while True:
        trozo = await archivo.read(_BLOQUE)
        if not trozo:
            break
        total += len(trozo)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"El {etiqueta} supera el máximo permitido de {max_mb:g} MB.",
            )
        trozos.append(trozo)
    return b"".join(trozos)
