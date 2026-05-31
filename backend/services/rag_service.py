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

import chromadb
import replicate

from backend import config
from backend import personajes as personajes_cfg
from backend.services import translation_service

# Cliente y colección de ChromaDB, cargados una sola vez (singleton perezoso).
_client: chromadb.ClientAPI | None = None
_collection = None


def _get_collection():
    """Devuelve la colección de ChromaDB, creándola e indexándola la 1ª vez."""
    global _client, _collection
    if _collection is not None:
        return _collection

    # PersistentClient guarda los datos en disco (config.CHROMA_DIR), así que el
    # índice sobrevive entre reinicios y no hay que recalcularlo cada vez.
    _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))

    # get_or_create_collection: si ya existe la reutiliza; si no, la crea.
    # Por defecto usa su función de embeddings local (CPU).
    #
    # hnsw:space="cosine" → usamos DISTANCIA COSENO, que va de 0 (idéntico) a 2
    # (opuesto). Es más interpretable que la L2 por defecto y nos permite poner
    # umbrales fijos para el Evaluator. Usamos un nombre versionado ("..._cos")
    # para que, si ya tenías una colección antigua con otra métrica, se cree una
    # nueva limpia con coseno sin que tengas que borrar nada a mano.
    # La colección la construye el script de ingesta (python -m backend.ingest)
    # a partir de los documentos. Aquí solo la ABRIMOS para consultarla.
    _collection = _client.get_or_create_collection(
        name=config.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    # Si está vacía, avisamos: hay que ejecutar la ingesta primero.
    if _collection.count() == 0:
        print(
            "[RAG] ⚠️  La colección de documentos está vacía. Añade documentos en "
            "backend/documentos/<personaje>/ y ejecuta:  python -m backend.ingest"
        )

    return _collection


def _recuperar_contexto(
    personaje_id: str, pregunta: str
) -> tuple[list[str], list[float]]:
    """Devuelve (fichas, distancias) más relevantes para la pregunta, de ESE personaje.

    - fichas: los textos recuperados (ordenados de más a menos parecido).
    - distancias: la distancia coseno de cada ficha a la pregunta (menor = más
      parecido). Las usa el Evaluator para decidir por umbral, sin LLM.

    Usa el filtro `where` para limitar la búsqueda al personaje elegido: así un
    Triceratops nunca responde con datos de Sherlock Holmes.
    """
    collection = _get_collection()
    resultado = collection.query(
        query_texts=[pregunta],
        n_results=config.RAG_TOP_K,
        where={"personaje_id": personaje_id},   # solo fichas de este personaje
        include=["documents", "distances"],     # pedimos también las distancias
    )
    # query devuelve listas anidadas (una por consulta); tomamos la primera.
    documentos = (resultado.get("documents") or [[]])[0]
    distancias = (resultado.get("distances") or [[]])[0]
    return documentos, distancias


def _construir_prompt(nombre: str, contexto: list[str], pregunta: str) -> tuple[str, str]:
    """Construye el prompt (system + user) para el LLM.

    - system: las reglas del juego (quién eres, cómo hablar, no inventar).
    - user:   las fichas recuperadas + la pregunta concreta del niño.
    """
    fichas_texto = "\n".join(f"- {ficha}" for ficha in contexto) or "(sin datos)"

    system = (
        f"Eres {nombre} y hablas en primera persona con un niño de entre 8 y 12 "
        "años. Responde SIEMPRE en español, de forma breve (2-4 frases), alegre y "
        "sencilla. Usa ÚNICAMENTE la información de las fichas que te paso (las "
        "fichas pueden estar en inglés: entiéndelas y responde en español). Si la "
        "respuesta no está en las fichas, di con simpatía que eso no lo sabes, sin "
        "inventarte nada. No dejes de ser el personaje en ningún momento."
    )

    user = (
        f"Fichas con datos sobre mí:\n{fichas_texto}\n\n"
        f"Pregunta del niño: {pregunta}\n\n"
        "Tu respuesta (en primera persona, en español):"
    )
    return system, user


def _construir_prompt_general(nombre: str, pregunta: str) -> tuple[str, str]:
    """Prompt para el camino GENERAL (sin fichas relevantes).

    El personaje responde con su conocimiento propio, manteniéndose en su papel y
    con lenguaje apto para niños. Si tampoco lo sabe, lo dice con simpatía.
    """
    system = (
        f"Eres {nombre} y hablas en primera persona con un niño de entre 8 y 12 "
        "años. Responde SIEMPRE en español, de forma breve (2-4 frases), alegre y "
        "sencilla, sin dejar de ser el personaje. No tienes fichas de datos para "
        "esta pregunta: responde con tu propio conocimiento general y, si no lo "
        "sabes, dilo con simpatía sin inventar."
    )
    user = (
        f"Pregunta del niño: {pregunta}\n\n"
        "Tu respuesta (en primera persona, en español):"
    )
    return system, user


def _llamar_llm(
    system: str,
    user: str,
    max_tokens: int | None = None,
    temperature: float = 0.6,
) -> str:
    """Llama al LLM en Replicate y devuelve el texto de la respuesta.

    Los modelos de chat de Replicate devuelven la respuesta "en trocitos"
    (streaming): una secuencia de cadenas que hay que unir.

    `max_tokens` y `temperature` son configurables porque el Evaluator (juez)
    necesita una respuesta cortísima y determinista, mientras que la respuesta
    del personaje admite más longitud y algo de creatividad.
    """
    salida = replicate.run(
        config.REPLICATE_LLM_MODEL,
        input={
            "prompt": user,
            "system_prompt": system,
            "max_tokens": max_tokens or config.LLM_MAX_TOKENS,
            "temperature": temperature,
        },
    )
    # salida es un iterable de strings -> los concatenamos en un único texto.
    return "".join(salida).strip()


def _evaluar_relevancia(contexto: list[str], pregunta: str) -> bool:
    """NODO EVALUATOR (LLM como juez): ¿sirven las fichas para responder?

    Esta es la pieza que nos permite saber si la respuesta vendrá DEL RAG o no.
    Hacemos una primera llamada al LLM pidiéndole que actúe como juez estricto y
    responda SOLO 'SI' o 'NO':
      - 'SI'  → las fichas recuperadas son relevantes ⇒ respuesta fundamentada (RAG).
      - 'NO'  → no son relevantes ⇒ el personaje tendrá que tirar de conocimiento
                general (y, en el futuro, aquí se podría activar la búsqueda web).

    Es el mismo patrón "Evaluator → Router" de las arquitecturas RAG avanzadas,
    pero implementado a mano (sin LangGraph) para que se vea cada paso.
    """
    if not contexto:
        return False  # sin fichas no hay nada que evaluar: no es RAG

    fichas_texto = "\n".join(f"- {ficha}" for ficha in contexto)
    system = (
        "Eres un evaluador estricto de un sistema RAG. Tu única tarea es decidir "
        "si las fichas de contexto contienen información para responder la pregunta. "
        "Responde EXCLUSIVAMENTE con una palabra, sin explicar nada: 'SI' si las "
        "fichas son relevantes y suficientes, o 'NO' si no lo son."
    )
    user = (
        f"Fichas de contexto:\n{fichas_texto}\n\n"
        f"Pregunta: {pregunta}\n\n"
        "¿Las fichas son relevantes para responder? Responde solo SI o NO:"
    )

    # Respuesta cortísima y temperatura baja: queremos un juez consistente.
    veredicto = _llamar_llm(system, user, max_tokens=5, temperature=0.0)

    # Parseo robusto: nos quedamos con la primera palabra y la comparamos.
    palabras = "".join(c for c in veredicto.lower() if c.isalpha() or c.isspace()).split()
    primera = palabras[0] if palabras else ""
    return primera in ("si", "sí", "yes")


def _clasificar_umbral(distancia: float) -> str:
    """Clasifica una distancia coseno en 'relevante' / 'irrelevante' / 'dudoso'.

    Es el árbitro GRATIS: solo compara números, sin llamar a ningún LLM.
    """
    if distancia <= config.EVALUATOR_UMBRAL_BAJO:
        return "relevante"     # muy parecida a una ficha → es RAG seguro
    if distancia >= config.EVALUATOR_UMBRAL_ALTO:
        return "irrelevante"   # muy lejana → no es RAG seguro
    return "dudoso"            # zona gris


def _decidir_origen(
    contexto: list[str], distancias: list[float], pregunta: str
) -> tuple[bool, str, float | None]:
    """NODO EVALUATOR + ROUTER. Decide si la respuesta vendrá del RAG.

    Devuelve (es_rag, metodo, distancia):
      - es_rag    : True si se usará el conocimiento de las fichas.
      - metodo    : "umbral" o "llm" (cómo se tomó la decisión, útil para depurar).
      - distancia : la mejor (menor) distancia coseno encontrada (o None).

    Según config.EVALUATOR_MODE:
      • "umbral"  → decide solo el número (gratis). RAG si la mejor ficha está
                    por debajo del umbral BAJO.
      • "llm"     → decide solo el LLM-juez (cuesta una llamada).
      • "hibrido" → el umbral resuelve los casos claros (gratis) y el LLM solo
                    desempata la zona "dudosa".
    """
    # Sin fichas no hay nada que fundamentar: no puede ser RAG.
    if not contexto:
        return False, "umbral", None

    mejor = min(distancias) if distancias else None
    modo = config.EVALUATOR_MODE

    # Modo LLM puro: el juez decide siempre (ignoramos el umbral).
    if modo == "llm":
        return _evaluar_relevancia(contexto, pregunta), "llm", mejor

    banda = _clasificar_umbral(mejor) if mejor is not None else "dudoso"

    # Modo umbral puro: solo el número. Conservador: RAG únicamente si es "relevante".
    if modo == "umbral":
        return (banda == "relevante"), "umbral", mejor

    # Modo híbrido: los casos claros los cierra el umbral (gratis); el LLM solo
    # entra a desempatar cuando la distancia cae en la zona "dudosa".
    if banda == "relevante":
        return True, "umbral", mejor
    if banda == "irrelevante":
        return False, "umbral", mejor
    return _evaluar_relevancia(contexto, pregunta), "llm", mejor


def responder(personaje_id: str, pregunta: str) -> dict:
    """Función principal: dado un personaje y una pregunta, devuelve la respuesta.

    Lanza ValueError (→ 400 en el router) si el personaje no existe o falta el
    token de Replicate.
    """
    if personaje_id not in personajes_cfg.NOMBRES:
        raise ValueError(f"Personaje desconocido: '{personaje_id}'.")
    if not config.REPLICATE_API_TOKEN:
        raise ValueError(
            "Falta REPLICATE_API_TOKEN en el .env. Crea un token en "
            "https://replicate.com/account/api-tokens y añádelo al .env."
        )

    nombre = personajes_cfg.NOMBRES[personaje_id]

    # 0) TRADUCCIÓN (OBLIGATORIA): la enciclopedia está en inglés, así que
    #    traducimos la pregunta ES→EN para que la búsqueda sea precisa. Si DeepL
    #    no está disponible, traducir_es_en lanza TranslationError (subclase de
    #    ValueError) → el router responde 400 con un mensaje claro, en vez de dar
    #    una respuesta mala. (Solo se traduce la pregunta; la respuesta va en español.)
    pregunta_en = translation_service.traducir_es_en(pregunta)

    # 1) RETRIEVAL: recuperar las fichas candidatas y sus distancias (con la
    #    pregunta YA en inglés, igual que las fichas).
    contexto, distancias = _recuperar_contexto(personaje_id, pregunta_en)

    # 2) EVALUATOR + ROUTER: ¿son esas fichas relevantes? (umbral / llm / híbrido)
    es_rag, metodo, distancia = _decidir_origen(contexto, distancias, pregunta_en)

    if es_rag:
        # --- Camino RAG: respuesta FUNDAMENTADA solo en las fichas ---
        origen = "RAG"
        system, user = _construir_prompt(nombre, contexto, pregunta)
        respuesta = _llamar_llm(system, user)
        fuentes = contexto
    else:
        # --- Camino GENERAL: las fichas no sirven; el personaje responde con su
        # conocimiento propio (aquí, en el futuro, podría enrutarse a búsqueda web).
        origen = "GENERAL"
        system, user = _construir_prompt_general(nombre, pregunta)
        respuesta = _llamar_llm(system, user)
        fuentes = []  # no hay fichas detrás de esta respuesta

    return {
        "success": True,
        "personaje_id": personaje_id,
        "pregunta": pregunta,
        "respuesta": respuesta,
        # "RAG" = fundamentada en la enciclopedia · "GENERAL" = conocimiento del modelo.
        "origen": origen,
        # Cómo se decidió ("umbral"/"llm") y la mejor distancia (para depurar/calibrar).
        "metodo": metodo,
        "distancia": distancia,
        # La pregunta traducida a inglés (para verificar que DeepL está actuando).
        "pregunta_traducida": pregunta_en,
        # Fichas usadas (vacío si la respuesta no vino del RAG).
        "fuentes": fuentes,
    }
