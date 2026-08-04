"""Tests del troceado estructural y el formato de fuentes (H4.2).

No tocan ChromaDB ni red: prueban la función pura de troceado y el formateo de la
procedencia. El backend de embeddings no interviene aquí.
"""

from backend.services import documentos_service, rag_service, settings_service

_MD = """# Tyrannosaurus

Intro sobre el dinosaurio.

## Description

### Skull

The skull was massive and wide at the rear.
"""


def test_troceado_estructura_saca_ruta_de_encabezados(monkeypatch):
    monkeypatch.setattr(
        settings_service,
        "get",
        _stub_settings({"CHUNKING": "estructura", "CHUNK_SIZE": 800, "CHUNK_OVERLAP": 120}),
    )
    pares = documentos_service._trocear(_MD, ".md")
    rutas = {ruta for _, ruta in pares}
    # La sección profunda expone su ruta completa de encabezados.
    assert "Tyrannosaurus > Description > Skull" in rutas
    # El texto del chunk NO lleva la ruta prefijada (decisión medida en ADR-005).
    skull = next(texto for texto, ruta in pares if ruta.endswith("Skull"))
    assert skull.startswith("The skull")


def test_troceado_recursivo_no_pone_ruta(monkeypatch):
    monkeypatch.setattr(
        settings_service,
        "get",
        _stub_settings({"CHUNKING": "recursivo", "CHUNK_SIZE": 800, "CHUNK_OVERLAP": 120}),
    )
    pares = documentos_service._trocear(_MD, ".md")
    assert all(ruta == "" for _, ruta in pares)


def test_formatear_fuente_antepone_seccion():
    meta = {"header_path": "Peter Pan > Neverland"}
    assert rag_service._formatear_fuente("vive alli", meta) == "[Peter Pan > Neverland] vive alli"
    # Sin ruta, la fuente se muestra tal cual.
    assert rag_service._formatear_fuente("texto", {}) == "texto"
    assert rag_service._formatear_fuente("texto", None) == "texto"


def _stub_settings(valores: dict):
    """Devuelve un get(clave) que usa `valores` y cae al real para el resto."""
    real = settings_service.get

    def _get(clave):
        return valores.get(clave, real(clave))

    return _get
