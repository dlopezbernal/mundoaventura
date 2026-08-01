"""
evals/esquema.py — Forma y validación de los sets de preguntas (Hito 3)
=======================================================================

Los sets viven en YAML (fáciles de leer y editar a mano). Aquí se definen su forma
(modelos Pydantic) y los cargadores que los validan al leerlos: un id repetido, un
`tipo` inválido o un campo que falta se detectan al arrancar el runner, no a mitad
de una corrida cara.

Set DORADO (`set_dorado.yaml`) — mide CALIDAD:
  - 20 preguntas por personaje activo, con la distribución del doc de H3
    (6 literal / 5 inferencial / 4 fuera de dominio / 3 sin respuesta / 2 ambigua).
  - Escritas en ESPAÑOL INFANTIL REAL (faltas, sin acentos, frases cortas).

Set de SEGURIDAD (`set_seguridad.yaml`) — mide TACTO y robustez del papel:
  - preguntas sobre muerte/violencia/miedo, intentos de sacar al personaje de su
    papel, datos personales del niño e inyección de prompt.
"""

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_DIR = Path(__file__).resolve().parent
_RUTA_DORADO = _DIR / "set_dorado.yaml"
_RUTA_SEGURIDAD = _DIR / "set_seguridad.yaml"


class TipoPregunta(str, Enum):
    """Los 5 tipos del set dorado (ver la tabla de distribución en el doc de H3)."""

    LITERAL = "literal"  # la respuesta está tal cual en un documento
    INFERENCIAL = "inferencial"  # hay que combinar dos fragmentos
    FUERA_DOMINIO = "fuera_dominio"  # razonable pero fuera de los documentos
    SIN_RESPUESTA = "sin_respuesta"  # fuera de dominio y sin respuesta posible
    AMBIGUA = "ambigua"  # mal formulada; se mide que no rompa


class OrigenEsperado(str, Enum):
    """Origen que se espera que decida el Evaluator (o 'cualquiera' si da igual)."""

    RAG = "RAG"
    GENERAL = "GENERAL"
    SIN_INFO = "SIN_INFO"
    CUALQUIERA = "cualquiera"  # para las ambiguas: solo se mide que no rompa


class CategoriaSeguridad(str, Enum):
    """Categorías del set adversarial de seguridad."""

    MUERTE = "muerte"
    VIOLENCIA = "violencia"
    MIEDO = "miedo"
    SALIR_DEL_PAPEL = "salir_del_papel"
    DATOS_PERSONALES = "datos_personales"
    INYECCION = "inyeccion"


class PreguntaDorada(BaseModel):
    """Una entrada del set dorado."""

    id: str
    personaje_id: str
    pregunta: str = Field(min_length=1)
    tipo: TipoPregunta
    origen_esperado: OrigenEsperado
    # Fichero(s) de documento donde está la respuesta (para medir recall@3). Puede ser
    # uno o una lista (cuando el mismo dato vive en varios ficheros del personaje, y el
    # retriever puede traer cualquiera). Solo en literal/inferencial; en las demás, None.
    chunk_esperado: str | list[str] | None = None
    notas: str = ""


class PreguntaSeguridad(BaseModel):
    """Una entrada del set adversarial de seguridad."""

    id: str
    personaje_id: str
    pregunta: str = Field(min_length=1)
    categoria: CategoriaSeguridad
    # Qué se espera del sistema (texto legible, para revisión humana; en H3 no se
    # puntúa automáticamente — el juicio de tacto es humano).
    espera: str = ""
    notas: str = ""


def _cargar_yaml(ruta: Path) -> list[dict]:
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el set de preguntas: {ruta}")
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or []
    if not isinstance(datos, list):
        raise ValueError(f"{ruta.name} debe ser una lista de preguntas.")
    return datos


def _validar_ids_unicos(items: list[BaseModel], nombre: str) -> None:
    vistos: set[str] = set()
    for it in items:
        if it.id in vistos:
            raise ValueError(f"{nombre}: id repetido '{it.id}'.")
        vistos.add(it.id)


def cargar_set_dorado(ruta: Path | None = None) -> list[PreguntaDorada]:
    """Lee y valida el set dorado. Lanza si hay ids repetidos o campos inválidos."""
    preguntas = [PreguntaDorada(**d) for d in _cargar_yaml(ruta or _RUTA_DORADO)]
    _validar_ids_unicos(preguntas, "set_dorado")
    return preguntas


def cargar_set_seguridad(ruta: Path | None = None) -> list[PreguntaSeguridad]:
    """Lee y valida el set de seguridad."""
    preguntas = [PreguntaSeguridad(**d) for d in _cargar_yaml(ruta or _RUTA_SEGURIDAD)]
    _validar_ids_unicos(preguntas, "set_seguridad")
    return preguntas


def resumen_distribucion(preguntas: list[PreguntaDorada]) -> dict[str, dict[str, int]]:
    """Cuenta preguntas por personaje y por tipo (para verificar la distribución de §1).

    Devuelve {personaje_id: {tipo: n, ..., "total": n}}.
    """
    resumen: dict[str, dict[str, int]] = {}
    for p in preguntas:
        por_tipo = resumen.setdefault(p.personaje_id, {})
        por_tipo[p.tipo.value] = por_tipo.get(p.tipo.value, 0) + 1
        por_tipo["total"] = por_tipo.get("total", 0) + 1
    return resumen
