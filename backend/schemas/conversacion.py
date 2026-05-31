"""
schemas/conversacion.py — Forma de los datos de la conversación (RAG)
=====================================================================

Define la ENTRADA y la SALIDA del endpoint POST /api/ask: el niño manda un
personaje y una pregunta (texto), y recibe la respuesta del personaje junto a
las fichas en las que se ha basado.

(La pregunta llega como texto. En el siguiente paso añadiremos la versión por
voz: el audio se transcribirá con Whisper y alimentará este mismo flujo.)
"""

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Petición del endpoint POST /api/ask."""

    personaje_id: str = Field(
        ..., description="Identificador del personaje al que se pregunta (ej. 't-rex')."
    )
    pregunta: str = Field(
        ..., min_length=1, description="La pregunta del niño, en texto."
    )


class AskResponse(BaseModel):
    """Respuesta del endpoint POST /api/ask."""

    success: bool = Field(..., description="True si se generó la respuesta.")
    personaje_id: str = Field(..., description="Personaje que respondió.")
    pregunta: str = Field(..., description="Eco de la pregunta recibida.")
    respuesta: str = Field(
        ..., description="Respuesta del personaje, en primera persona y en español."
    )
    origen: str = Field(
        ...,
        description="De dónde sale la respuesta: 'RAG' (fundamentada en la "
        "enciclopedia) o 'GENERAL' (conocimiento propio del modelo).",
    )
    metodo: str = Field(
        default="",
        description="Cómo se decidió el origen: 'umbral' (distancia) o 'llm' (juez).",
    )
    pregunta_traducida: str = Field(
        default="",
        description="La pregunta traducida a inglés (DeepL) usada para buscar. "
        "Si es igual a la original, la traducción no se aplicó.",
    )
    distancia: float | None = Field(
        default=None,
        description="Mejor distancia coseno encontrada (menor = más parecido). "
        "Útil para calibrar los umbrales del Evaluator.",
    )
    fuentes: list[str] = Field(
        default_factory=list,
        description="Fragmentos (chunks) de los documentos usados para fundamentar "
        "la respuesta.",
    )
