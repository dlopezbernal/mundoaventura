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

import chromadb

from backend import config
from backend.services import (
    embeddings,
    llm_service,
    personajes_service,
    reranker,
    settings_service,
    translation_service,
)

logger = logging.getLogger(__name__)

# Cliente y colección de ChromaDB, cargados una sola vez (singleton perezoso).
_client: chromadb.ClientAPI | None = None
_collection = None
_collection_nombre: str | None = None  # nombre con el que se abrió (para detectar cambios)

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
    """Devuelve la colección del backend de embeddings vigente (singleton perezoso).

    El nombre depende de `EMBEDDING_BACKEND`; si cambia (p. ej. al comparar backends),
    se reabre la colección correcta en vez de servir la cacheada del backend anterior.
    """
    global _client, _collection, _collection_nombre
    nombre = embeddings.coleccion_actual()
    if _collection is not None and _collection_nombre == nombre:
        return _collection

    # PersistentClient guarda los datos en disco (config.CHROMA_DIR), así que el
    # índice sobrevive entre reinicios y no hay que recalcularlo cada vez.
    if _client is None:
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
        name=nombre,
        metadata={"hnsw:space": "cosine"},
    )
    _collection_nombre = nombre

    # Si está vacía, avisamos: hay que ejecutar la ingesta primero.
    if _collection.count() == 0:
        logger.warning(
            "La colección de ChromaDB está VACÍA: no hay ninguna ficha indexada, así "
            "que el chat responderá sin contexto (respuestas pobres o siempre 'no lo "
            "sé'). Añade documentos en backend/documentos/<personaje>/ y reconstruye el "
            "índice con:  python -m backend.ingest"
        )

    return _collection


def reiniciar_coleccion() -> None:
    """Olvida el cliente/colección cacheados de ChromaDB.

    Lo llama documentos_service tras un REINDEXADO GLOBAL (que borra y recrea la
    colección): el handle cacheado apuntaría a una colección eliminada, así que se
    fuerza a reabrirla en la siguiente pregunta. Tras un reindexado incremental
    (borrar+reañadir chunks de un personaje) NO hace falta: la colección es la misma.
    """
    global _client, _collection, _collection_nombre
    _client = None
    _collection = None
    _collection_nombre = None


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
        return False, "umbral", None, None

    mejor_dist = min(distancias) if distancias else None

    # --- Camino RERANKER: decide la puntuación del cross-encoder, sin LLM-juez ---
    if scores:
        mejor_score = max(scores)
        es_rag = mejor_score >= settings_service.get("RERANK_UMBRAL")
        return es_rag, "rerank", mejor_dist, mejor_score

    # --- Camino coseno (sin reranker): umbral / llm / híbrido de siempre ---
    modo = settings_service.get("EVALUATOR_MODE")

    # Modo LLM puro: el juez decide siempre (ignoramos el umbral).
    if modo == "llm":
        return _evaluar_relevancia(contexto, pregunta), "llm", mejor_dist, None

    banda = _clasificar_umbral(mejor_dist) if mejor_dist is not None else "dudoso"

    # Modo umbral puro: solo el número. Conservador: RAG únicamente si es "relevante".
    if modo == "umbral":
        return (banda == "relevante"), "umbral", mejor_dist, None

    # Modo híbrido: los casos claros los cierra el umbral (gratis); el LLM solo
    # entra a desempatar cuando la distancia cae en la zona "dudosa".
    if banda == "relevante":
        return True, "umbral", mejor_dist, None
    if banda == "irrelevante":
        return False, "umbral", mejor_dist, None
    return _evaluar_relevancia(contexto, pregunta), "llm", mejor_dist, None


def responder(personaje_id: str, pregunta: str) -> dict:
    """Genera la respuesta de TEXTO del personaje (RAG). SIN voz (Hito 5).

    La síntesis de voz (TTS) ya NO vive aquí: este servicio recupera y genera
    TEXTO, y no tiene por qué saber que existe ElevenLabs. El orquestador
    `chat_service.responder` añade el audio sobre este resultado (subir el TTS un
    nivel era la fuga de capas principal del backend, y estorba al streaming de H8).

    Lanza ValueError (→ 400 en el router) si el personaje no existe o falta el
    token de Replicate.
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

    # 0) TRADUCCIÓN (OBLIGATORIA): la enciclopedia está en inglés, así que
    #    traducimos la pregunta ES→EN. La versión en inglés (pregunta_en) se usa en
    #    TODAS las peticiones al modelo —retrieval, Evaluator y generación—, porque
    #    Llama 3 entiende y obedece mejor en inglés. Si DeepL no está disponible,
    #    traducir_es_en lanza TranslationError (subclase de ValueError) → el router
    #    responde 400 con un mensaje claro, en vez de dar una respuesta mala.
    #    (Solo se traduce la pregunta del niño; la RESPUESTA del personaje va en español.)
    pregunta_en = translation_service.traducir_es_en(pregunta)

    # 1) RETRIEVAL (+ RERANK si está activo): recuperar las fichas candidatas, sus
    #    distancias y —si hay reranker— sus puntuaciones (con la pregunta YA en inglés).
    contexto, distancias, metadatos, scores = _recuperar_contexto(personaje_id, pregunta_en)

    # 2) EVALUATOR + ROUTER: ¿son esas fichas relevantes? (rerank / umbral / llm / híbrido)
    es_rag, metodo, distancia, score = _decidir_origen(contexto, distancias, scores, pregunta_en)

    if es_rag:
        # --- Camino RAG: respuesta FUNDAMENTADA solo en las fichas ---
        origen = "RAG"
        # Pasamos la pregunta YA traducida (pregunta_en): Llama 3 entiende y obedece
        # mejor en inglés. La respuesta, eso sí, se genera en español (lo pide el prompt).
        system, user = _construir_prompt(nombre, contexto, pregunta_en)
        respuesta = _llamar_llm(system, user, etiqueta="RAG")
        # MOSTRAR_FUENTES (flag propio, ya no atado a DEBUG) decide si el niño VE el
        # desplegable "¿De dónde lo he sacado?" en el chat (Chat.tsx lo pinta si
        # `fuentes` no viene vacío). Enseñar la procedencia es pedagogía, no depuración.
        # No afecta a que la respuesta siga fundamentada en el RAG, solo a si se
        # enseña el porqué (con troceado estructural, la ruta de encabezados va incluida).
        fuentes = (
            [_formatear_fuente(c, m) for c, m in zip(contexto, metadatos, strict=False)]
            if settings_service.get("MOSTRAR_FUENTES")
            else []
        )
    elif settings_service.get("PERMITIR_CONOCIMIENTO_GENERAL"):
        # --- Camino GENERAL: las fichas no sirven; el personaje responde con su
        # conocimiento propio (aquí, en el futuro, podría enrutarse a búsqueda web).
        origen = "GENERAL"
        # Igual que en RAG: la pregunta va en inglés (pregunta_en), la respuesta en español.
        system, user = _construir_prompt_general(nombre, pregunta_en)
        respuesta = _llamar_llm(system, user, etiqueta="GENERAL")
        fuentes = []  # no hay fichas detrás de esta respuesta
    else:
        # --- Camino SIN_INFO: las fichas no sirven y el conocimiento propio del LLM
        # está desactivado (PERMITIR_CONOCIMIENTO_GENERAL=false). Mensaje FIJO, sin
        # llamar a ningún modelo (ni el LLM del personaje ni el juez): coste cero y
        # respuesta anclada estrictamente a los documentos subidos.
        origen = "SIN_INFO"
        respuesta = settings_service.rellenar(
            settings_service.get("MENSAJE_SIN_INFORMACION"), nombre=nombre
        )
        fuentes = []

    # Traza de depuración (solo si DEBUG): en la consola del BACKEND, no del cliente.
    _trazar_origen(origen, metodo, distancia, score, pregunta_en)

    return {
        "success": True,
        "personaje_id": personaje_id,
        "pregunta": pregunta,
        "respuesta": respuesta,
        # "RAG" = fundamentada en la enciclopedia · "GENERAL" = conocimiento del modelo.
        "origen": origen,
        # Cómo se decidió ("rerank"/"umbral"/"llm") y las señales para depurar/calibrar:
        # la mejor distancia coseno y, si hubo reranker, la mejor puntuación.
        "metodo": metodo,
        "distancia": distancia,
        "rerank_score": score,
        # La pregunta traducida a inglés (para verificar que DeepL está actuando).
        "pregunta_traducida": pregunta_en,
        # Fichas usadas (vacío si la respuesta no vino del RAG).
        "fuentes": fuentes,
        # El audio (TTS) lo añade el orquestador chat_service; aquí NO (capa de texto).
    }
