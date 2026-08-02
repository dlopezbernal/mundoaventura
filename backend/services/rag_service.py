"""
services/rag_service.py — NÚCLEO de la conversación (RAG)
=========================================================

RAG = Retrieval-Augmented Generation. La idea, paso a paso:

  1) INDEXAR (fase aparte): el script backend/ingest.py trocea los documentos
     (chunking con solape, vía LangChain) y guarda cada fragmento como un "vector"
     en ChromaDB. Este archivo NO indexa: solo consulta lo ya indexado.

  2) RECUPERAR (en cada pregunta): convertimos la pregunta del niño en un vector
     y le pedimos a ChromaDB los fragmentos MÁS PARECIDOS (los más cercanos en
     significado). Además filtramos por personaje, para no mezclar al t-rex con
     Sherlock Holmes.

  3) GENERAR: le pasamos al LLM (vía Replicate) esos fragmentos como CONTEXTO y le
     pedimos que responda en primera persona, como el personaje, usando SOLO esa
     información. Así la respuesta es fiable y apta para niños.

Decisiones para mantenerlo simple y sin GPU local:
  - ChromaDB usa por defecto un modelo de embeddings pequeño que corre en CPU
    (se descarga solo la primera vez). No necesitamos torch ni claves extra.
  - El LLM sí está en la nube (Replicate), reutilizando tu token.
  - El filtro por personaje (metadato) hace que la recuperación sea robusta y
    cada personaje solo "vea" sus propios documentos.
"""

import logging
from collections.abc import Iterator
from typing import TypedDict

from backend import config
from backend.enums import MetodoDecision, ModoEvaluator, Origen
from backend.services import (
    embeddings,
    llm_service,
    personajes_service,
    reranker,
    settings_service,
    translation_service,
    vector_store,
)

logger = logging.getLogger(__name__)


class RespuestaRAG(TypedDict):
    """Retorno de `responder`: la respuesta de TEXTO del chat (sin voz).

    Es un TypedDict (un dict normal en runtime, sin coste), solo para dejar por
    escrito el contrato que antes era un `-> dict` opaco. El audio lo añade
    `chat_service` sobre esto (ver RespuestaChat allí).
    """

    success: bool
    personaje_id: str
    pregunta: str
    respuesta: str
    origen: str  # Origen (StrEnum): RAG / GENERAL / SIN_INFO
    metodo: str  # MetodoDecision (StrEnum): umbral / llm / rerank
    distancia: float | None
    rerank_score: float | None
    pregunta_traducida: str
    fuentes: list[str]


# Icono por origen, solo para la traza de consola en modo DEBUG.
_ICONO_ORIGEN = {"RAG": "🟢", "GENERAL": "🟡", "SIN_INFO": "🔴"}


def _trazar_origen(
    origen: str, metodo: str, distancia: float | None, score: float | None, pregunta_en: str
) -> None:
    """Imprime por la consola del BACKEND si la respuesta vino del RAG o no.

    Solo en modo DEBUG (settings_service). Antes esto se calculaba/mostraba en el
    frontend; se hace aquí porque el backend ya tiene todos los datos, así no hay
    que enviarlos ni procesarlos en el cliente.
    """
    if not settings_service.get("DEBUG"):
        return
    icono = _ICONO_ORIGEN.get(origen, "⚪")
    # Qué significa el origen elegido (de dónde sale la respuesta del personaje).
    explica_origen = {
        "RAG": "respuesta FUNDAMENTADA en las fichas recuperadas de este personaje",
        "GENERAL": "las fichas no servían → responde con el conocimiento propio del LLM",
        "SIN_INFO": "las fichas no servían y PERMITIR_CONOCIMIENTO_GENERAL está "
        "desactivado → mensaje fijo, SIN llamar a ningún modelo",
    }.get(origen, "origen desconocido")
    # Cómo se tomó la decisión RAG vs GENERAL (ver EVALUATOR_MODE).
    explica_metodo = {
        "umbral": "decidido GRATIS por la distancia coseno (sin llamar al LLM-juez)",
        "llm": "desempatado por el LLM-juez (la distancia caía en la zona dudosa)",
        "rerank": "decidido por la puntuación del reranker (cross-encoder, sin LLM-juez)",
    }.get(metodo, metodo)

    lineas = [
        f"[CHAT] {icono} Evaluator → origen={origen}: {explica_origen}",
        f"[CHAT]        método: {explica_metodo}",
    ]
    # Con reranker, la señal que decide es la PUNTUACIÓN (más alto = más relevante);
    # sin reranker, la distancia coseno (menor = más relevante).
    if score is not None:
        lineas.append(
            f"[CHAT]        mejor puntuación reranker={score:.2f}  "
            f"(umbral: >={settings_service.get('RERANK_UMBRAL')}→RAG)  "
            f"[distancia coseno de esa ficha d={distancia:.2f}]"
        )
    elif distancia is not None:
        lineas.append(
            f"[CHAT]        mejor distancia d={distancia:.2f}  "
            f"(umbrales coseno: BAJO={settings_service.get('EVALUATOR_UMBRAL_BAJO')}→RAG, "
            f"ALTO={settings_service.get('EVALUATOR_UMBRAL_ALTO')}→GENERAL; entre ambos=dudoso)"
        )
    lineas.append(f'[CHAT]        pregunta traducida (EN) que se buscó: "{pregunta_en}"')
    logger.debug("\n".join(lineas))


def _get_collection():
    """Abre la colección del backend de embeddings vigente (vía el cliente único).

    Delega en `vector_store` (única fuente del cliente ChromaDB). Devuelve la
    colección fresca: sin objeto-colección cacheado no hay handle que se quede
    obsoleto tras un reindexado global (por eso ya no existe `reiniciar_coleccion`).
    Solo LEE la colección; la construye la ingesta (`python -m backend.ingest`).
    """
    collection = vector_store.coleccion()
    # Si está vacía, avisamos: hay que ejecutar la ingesta primero.
    if collection.count() == 0:
        logger.warning(
            "La colección de ChromaDB está VACÍA: no hay ninguna ficha indexada, así "
            "que el chat responderá sin contexto (respuestas pobres o siempre 'no lo "
            "sé'). Añade documentos en backend/documentos/<personaje>/ y reconstruye el "
            "índice con:  python -m backend.ingest"
        )
    return collection


def _recuperar_contexto(
    personaje_id: str, pregunta: str
) -> tuple[list[str], list[float], list[dict], list[float] | None]:
    """Devuelve (fichas, distancias, metadatos, scores) más relevantes, de ESE personaje.

    - fichas: los textos recuperados (ordenados de más a menos relevante).
    - distancias: la distancia coseno de cada ficha (menor = más parecido). Las usa
      el Evaluator para decidir por umbral cuando NO hay reranker.
    - metadatos: source y header_path de cada ficha (para la procedencia del chat).
    - scores: la puntuación del reranker de cada ficha (más alto = más relevante), o
      None si el reranker está desactivado. Cuando hay scores, el Evaluator decide
      por ellos en vez de por la distancia coseno.

    EMBUDO (Hito 4.3): si hay reranker, se recuperan RERANK_CANDIDATOS candidatos
    baratos (bi-encoder), un cross-encoder los reordena y nos quedamos con el top-K.
    Sin reranker, se recupera directamente el top-K por distancia coseno.

    Usa el filtro `where` para limitar la búsqueda al personaje elegido: así un
    Triceratops nunca responde con datos de Sherlock Holmes.
    """
    collection = _get_collection()
    top_k = settings_service.get("RAG_TOP_K")
    # Con reranker recuperamos ANCHO (más candidatos) para que el cross-encoder tenga
    # de dónde elegir; sin reranker, justo los top_k que van al LLM.
    n_recuperar = settings_service.get("RERANK_CANDIDATOS") if reranker.activo() else top_k
    comun = {
        "n_results": n_recuperar,
        "where": {"personaje_id": personaje_id},  # solo fichas de este personaje
        "include": ["documents", "distances", "metadatas"],
    }
    # Backend multilingüe: embebemos NOSOTROS la consulta (como 'query') y pasamos el
    # vector. Backend original: la embebe Chroma a partir del texto (query_texts).
    if embeddings.usa_manuales():
        resultado = collection.query(query_embeddings=[embeddings.embed_query(pregunta)], **comun)
    else:
        resultado = collection.query(query_texts=[pregunta], **comun)
    # query devuelve listas anidadas (una por consulta); tomamos la primera.
    documentos = (resultado.get("documents") or [[]])[0]
    distancias = (resultado.get("distances") or [[]])[0]
    metadatos = (resultado.get("metadatas") or [[]])[0]

    if not reranker.activo() or not documentos:
        return documentos, distancias, metadatos, None

    # REORDENADO: el cross-encoder puntúa cada candidato (más alto = más relevante) y
    # reordenamos las tres listas en paralelo por esa puntuación, quedándonos con top_k.
    scores = reranker.rerank(pregunta, documentos)
    orden = sorted(range(len(documentos)), key=lambda i: scores[i], reverse=True)[:top_k]
    documentos = [documentos[i] for i in orden]
    distancias = [distancias[i] for i in orden]
    metadatos = [metadatos[i] for i in orden]
    scores = [scores[i] for i in orden]
    return documentos, distancias, metadatos, scores


def _formatear_fuente(texto: str, meta: dict | None) -> str:
    """Antepone la ruta de encabezados a la ficha, para la procedencia del chat."""
    ruta = (meta or {}).get("header_path") or ""
    return f"[{ruta}] {texto}" if ruta else texto


def _construir_prompt(nombre: str, contexto: list[str], pregunta: str) -> tuple[str, str]:
    """Construye el prompt (system + user) para el LLM.

    - system: las reglas del juego (quién eres, cómo hablar, no inventar).
    - user:   las fichas recuperadas + la pregunta concreta del niño.

    El prompt va EN INGLÉS a propósito (instrucciones + pregunta ya traducida ES→EN
    + fichas, que ya están en inglés): Llama 3 sigue mejor las instrucciones en
    inglés. La RESPUESTA, en cambio, se pide explícitamente EN ESPAÑOL, porque es lo
    que leerá el niño (el modelo genera español sin problema aunque se le instruya
    en inglés).
    """
    fichas_texto = "\n".join(f"- {ficha}" for ficha in contexto) or "(no data)"
    # Plantillas editables desde el menú de configuración (settings_service);
    # sus valores por defecto son los prompts en inglés de siempre.
    system = settings_service.rellenar(settings_service.get("PROMPT_RAG_SYSTEM"), nombre=nombre)
    user = settings_service.rellenar(
        settings_service.get("PROMPT_RAG_USER"),
        fichas=fichas_texto,
        pregunta=pregunta,
    )
    return system, user


def _construir_prompt_general(nombre: str, pregunta: str) -> tuple[str, str]:
    """Prompt para el camino GENERAL (sin fichas relevantes).

    El personaje responde con su conocimiento propio, manteniéndose en su papel y
    con lenguaje apto para niños. Si tampoco lo sabe, lo dice con simpatía.

    Mismo criterio que _construir_prompt: instrucciones + pregunta EN INGLÉS (Llama 3
    obedece mejor), pero la RESPUESTA se pide EN ESPAÑOL (es lo que lee el niño).
    """
    system = settings_service.rellenar(settings_service.get("PROMPT_GENERAL_SYSTEM"), nombre=nombre)
    user = settings_service.rellenar(settings_service.get("PROMPT_GENERAL_USER"), pregunta=pregunta)
    return system, user


def _llamar_llm(
    system: str,
    user: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
    etiqueta: str = "LLM",
) -> str:
    """Genera una respuesta del LLM (delega en la capa de proveedor, Hito 5).

    Antes esto hablaba directamente el dialecto de Replicate; ahora TODA llamada al
    LLM pasa por `llm_service`, que despacha por proveedor (replicate/openai) sin que
    rag_service sepa cuál. `max_tokens`/`temperature` siguen siendo configurables
    (el Evaluator los fuerza a 5/0.0); `etiqueta` identifica el uso para la traza.
    """
    return llm_service.completar(
        system, user, max_tokens=max_tokens, temperature=temperature, etiqueta=etiqueta
    )


def _evaluar_relevancia(contexto: list[str], pregunta: str) -> bool:
    """NODO EVALUATOR (LLM como juez): ¿sirven las fichas para responder?

    Esta es la pieza que nos permite saber si la respuesta vendrá DEL RAG o no.
    Hacemos una primera llamada al LLM pidiéndole que actúe como juez estricto y
    responda SOLO 'YES' o 'NO':
      - 'YES' → las fichas recuperadas son relevantes ⇒ respuesta fundamentada (RAG).
      - 'NO'  → no son relevantes ⇒ el personaje tendrá que tirar de conocimiento
                general (y, en el futuro, aquí se podría activar la búsqueda web).

    El prompt va EN INGLÉS a propósito: este juez razona sobre material 100% en
    inglés (las fichas vienen en inglés y la pregunta llega ya traducida ES→EN),
    así que darle las instrucciones en el mismo idioma lo hace más consistente.
    Nota: NO lo traducimos en runtime con DeepL (sería malgastar cuota en un texto
    fijo); está escrito directamente en inglés aquí.

    Es el mismo patrón "Evaluator → Router" de las arquitecturas RAG avanzadas,
    pero implementado a mano (sin LangGraph) para que se vea cada paso.
    """
    if not contexto:
        return False  # sin fichas no hay nada que evaluar: no es RAG

    fichas_texto = "\n".join(f"- {ficha}" for ficha in contexto)
    system = settings_service.get("PROMPT_EVALUATOR_SYSTEM")
    user = settings_service.rellenar(
        settings_service.get("PROMPT_EVALUATOR_USER"),
        fichas=fichas_texto,
        pregunta=pregunta,
    )

    # Respuesta cortísima y temperatura baja: queremos un juez consistente.
    veredicto = _llamar_llm(
        system, user, max_tokens=5, temperature=0.0, etiqueta="Evaluator (juez)"
    )

    # Parseo robusto: nos quedamos con la primera palabra y la comparamos.
    palabras = "".join(c for c in veredicto.lower() if c.isalpha() or c.isspace()).split()
    primera = palabras[0] if palabras else ""
    return primera in ("si", "sí", "yes")


def _clasificar_umbral(distancia: float) -> str:
    """Clasifica una distancia coseno en 'relevante' / 'irrelevante' / 'dudoso'.

    Es el árbitro GRATIS: solo compara números, sin llamar a ningún LLM.
    """
    if distancia <= settings_service.get("EVALUATOR_UMBRAL_BAJO"):
        return "relevante"  # muy parecida a una ficha → es RAG seguro
    if distancia >= settings_service.get("EVALUATOR_UMBRAL_ALTO"):
        return "irrelevante"  # muy lejana → no es RAG seguro
    return "dudoso"  # zona gris


def _decidir_origen(
    contexto: list[str], distancias: list[float], scores: list[float] | None, pregunta: str
) -> tuple[bool, str, float | None, float | None]:
    """NODO EVALUATOR + ROUTER. Decide si la respuesta vendrá del RAG.

    Devuelve (es_rag, metodo, distancia, score):
      - es_rag    : True si se usará el conocimiento de las fichas.
      - metodo    : "umbral", "llm" o "rerank" (cómo se tomó la decisión).
      - distancia : la mejor (menor) distancia coseno encontrada (o None).
      - score     : la mejor (mayor) puntuación del reranker (o None si no hay reranker).

    CON RERANKER (Hito 4.3): la decisión la toma la PUNTUACIÓN del cross-encoder, que
    es una señal de relevancia mucho más fina que la distancia coseno. RAG si la mejor
    ficha puntúa >= RERANK_UMBRAL. Esto SUSTITUYE al LLM-juez (una llamada menos) — el
    reranker ya "lee" pregunta+ficha juntas, que es justo lo que hacía el juez.

    SIN RERANKER, según EVALUATOR_MODE (settings_service):
      • "umbral"  → decide solo el número (gratis). RAG si la mejor ficha está
                    por debajo del umbral BAJO.
      • "llm"     → decide solo el LLM-juez (cuesta una llamada).
      • "hibrido" → el umbral resuelve los casos claros (gratis) y el LLM solo
                    desempata la zona "dudosa".
    """
    # Sin fichas no hay nada que fundamentar: no puede ser RAG.
    if not contexto:
        return False, MetodoDecision.UMBRAL, None, None

    mejor_dist = min(distancias) if distancias else None

    # --- Camino RERANKER: decide la puntuación del cross-encoder, sin LLM-juez ---
    if scores:
        mejor_score = max(scores)
        es_rag = mejor_score >= settings_service.get("RERANK_UMBRAL")
        return es_rag, MetodoDecision.RERANK, mejor_dist, mejor_score

    # --- Camino coseno (sin reranker): umbral / llm / híbrido de siempre ---
    modo = settings_service.get("EVALUATOR_MODE")

    # Modo LLM puro: el juez decide siempre (ignoramos el umbral).
    if modo == ModoEvaluator.LLM:
        return _evaluar_relevancia(contexto, pregunta), MetodoDecision.LLM, mejor_dist, None

    banda = _clasificar_umbral(mejor_dist) if mejor_dist is not None else "dudoso"

    # Modo umbral puro: solo el número. Conservador: RAG únicamente si es "relevante".
    if modo == ModoEvaluator.UMBRAL:
        return (banda == "relevante"), MetodoDecision.UMBRAL, mejor_dist, None

    # Modo híbrido: los casos claros los cierra el umbral (gratis); el LLM solo
    # entra a desempatar cuando la distancia cae en la zona "dudosa".
    if banda == "relevante":
        return True, MetodoDecision.UMBRAL, mejor_dist, None
    if banda == "irrelevante":
        return False, MetodoDecision.UMBRAL, mejor_dist, None
    return _evaluar_relevancia(contexto, pregunta), MetodoDecision.LLM, mejor_dist, None


def _preparar(personaje_id: str, pregunta: str) -> dict:
    """Fase COMÚN de responder/responder_streaming (todo menos generar el texto final).

    Valida, traduce (ES→EN), recupera, decide el origen (Evaluator+Router) y construye
    el prompt (o el texto fijo de SIN_INFO). NO llama al LLM de generación: eso lo hace
    quien llame, de golpe (`responder`) o en streaming (`responder_streaming`). Así la
    lógica de decisión vive en un solo sitio y las dos salidas no divergen.

    Devuelve un dict con: origen/metodo/distancia/rerank_score/pregunta_traducida/
    fuentes/nombre y, según el camino, (system, user, etiqueta) para generar o
    `respuesta_fija` (SIN_INFO).

    Lanza ValueError (→ 400 en el router) si el personaje no existe o falta el token.
    """
    ficha_personaje = personajes_service.obtener(personaje_id)
    if ficha_personaje is None:
        raise ValueError(f"Personaje desconocido: '{personaje_id}'.")
    if not config.REPLICATE_API_TOKEN:
        raise ValueError(
            "Falta REPLICATE_API_TOKEN en el .env. Crea un token en "
            "https://replicate.com/account/api-tokens y añádelo al .env."
        )

    nombre = ficha_personaje["nombre"]

    # 0) TRADUCCIÓN (OBLIGATORIA): la enciclopedia está en inglés, así que traducimos
    #    la pregunta ES→EN. La versión en inglés (pregunta_en) se usa en TODAS las
    #    peticiones al modelo (retrieval, Evaluator y generación): Llama 3 entiende y
    #    obedece mejor en inglés. Si DeepL no está, lanza TranslationError (→ 400).
    #    (Solo se traduce la pregunta; la RESPUESTA del personaje va en español.)
    pregunta_en = translation_service.traducir_es_en(pregunta)

    # 1) RETRIEVAL (+ RERANK si está activo).
    contexto, distancias, metadatos, scores = _recuperar_contexto(personaje_id, pregunta_en)

    # 2) EVALUATOR + ROUTER: ¿son relevantes las fichas? (rerank / umbral / llm / híbrido)
    es_rag, metodo, distancia, score = _decidir_origen(contexto, distancias, scores, pregunta_en)

    prep: dict = {
        "personaje_id": personaje_id,
        "pregunta": pregunta,
        "nombre": nombre,
        "metodo": metodo,
        "distancia": distancia,
        "rerank_score": score,
        "pregunta_traducida": pregunta_en,
        "system": None,
        "user": None,
        "etiqueta": None,
        "respuesta_fija": None,
    }

    if es_rag:
        # --- Camino RAG: respuesta FUNDAMENTADA solo en las fichas ---
        prep["origen"] = Origen.RAG
        prep["system"], prep["user"] = _construir_prompt(nombre, contexto, pregunta_en)
        prep["etiqueta"] = "RAG"
        # MOSTRAR_FUENTES (flag propio, ya no atado a DEBUG) decide si el niño VE el
        # desplegable "¿De dónde lo he sacado?" (Chat.tsx lo pinta si `fuentes` no está
        # vacío). Enseñar la procedencia es pedagogía, no depuración.
        prep["fuentes"] = (
            [_formatear_fuente(c, m) for c, m in zip(contexto, metadatos, strict=False)]
            if settings_service.get("MOSTRAR_FUENTES")
            else []
        )
    elif settings_service.get("PERMITIR_CONOCIMIENTO_GENERAL"):
        # --- Camino GENERAL: las fichas no sirven; el personaje tira de su conocimiento.
        prep["origen"] = Origen.GENERAL
        prep["system"], prep["user"] = _construir_prompt_general(nombre, pregunta_en)
        prep["etiqueta"] = "GENERAL"
        prep["fuentes"] = []
    else:
        # --- Camino SIN_INFO: fichas no válidas y conocimiento general desactivado.
        # Mensaje FIJO, sin llamar a ningún modelo: coste cero, anclado a los documentos.
        prep["origen"] = Origen.SIN_INFO
        prep["respuesta_fija"] = settings_service.rellenar(
            settings_service.get("MENSAJE_SIN_INFORMACION"), nombre=nombre
        )
        prep["fuentes"] = []
    return prep


def _resultado(prep: dict, respuesta: str) -> RespuestaRAG:
    """Arma el dict de RespuestaRAG a partir de la preparación y el texto generado."""
    return {
        "success": True,
        "personaje_id": prep["personaje_id"],
        "pregunta": prep["pregunta"],
        "respuesta": respuesta,
        "origen": prep["origen"],
        "metodo": prep["metodo"],
        "distancia": prep["distancia"],
        "rerank_score": prep["rerank_score"],
        "pregunta_traducida": prep["pregunta_traducida"],
        "fuentes": prep["fuentes"],
    }


def responder(personaje_id: str, pregunta: str) -> RespuestaRAG:
    """Genera la respuesta de TEXTO del personaje (RAG), de una vez. SIN voz (Hito 5).

    La síntesis de voz (TTS) NO vive aquí: este servicio recupera y genera TEXTO. El
    orquestador `chat_service` añade el audio. `responder_streaming` es la variante que
    cede el texto por trozos (Hito 8); ambas comparten `_preparar` para no divergir.

    Lanza ValueError (→ 400) si el personaje no existe o falta el token de Replicate.
    """
    prep = _preparar(personaje_id, pregunta)
    if prep["origen"] == Origen.SIN_INFO:
        respuesta = prep["respuesta_fija"]
    else:
        respuesta = _llamar_llm(prep["system"], prep["user"], etiqueta=prep["etiqueta"])
    _trazar_origen(
        prep["origen"],
        prep["metodo"],
        prep["distancia"],
        prep["rerank_score"],
        prep["pregunta_traducida"],
    )
    return _resultado(prep, respuesta)


def responder_streaming(personaje_id: str, pregunta: str) -> Iterator[dict]:
    """Variante en STREAMING de `responder`: cede el TEXTO por trozos (Hito 8).

    Emite dicts con `tipo`:
      - {"tipo": "meta", ...}   una vez al principio: origen, fuentes, metadatos.
      - {"tipo": "token", "texto": <trozo>}   por cada fragmento del LLM.
    NO añade voz: el TTS por frases lo orquesta `chat_service` sobre estos eventos
    (separación de capas). El endpoint JSON `responder` sigue intacto.
    """
    prep = _preparar(personaje_id, pregunta)
    yield {
        "tipo": "meta",
        "personaje_id": prep["personaje_id"],
        "pregunta": prep["pregunta"],
        "origen": prep["origen"],
        "metodo": prep["metodo"],
        "distancia": prep["distancia"],
        "rerank_score": prep["rerank_score"],
        "pregunta_traducida": prep["pregunta_traducida"],
        "fuentes": prep["fuentes"],
    }
    if prep["origen"] == Origen.SIN_INFO:
        # Texto fijo: un único "token" (no hay LLM que streamear).
        yield {"tipo": "token", "texto": prep["respuesta_fija"]}
    else:
        for trozo in llm_service.completar_streaming(
            prep["system"], prep["user"], etiqueta=prep["etiqueta"]
        ):
            yield {"tipo": "token", "texto": trozo}
    _trazar_origen(
        prep["origen"],
        prep["metodo"],
        prep["distancia"],
        prep["rerank_score"],
        prep["pregunta_traducida"],
    )
