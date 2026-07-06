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

import base64

import chromadb
import replicate

from backend import config
from backend import debug_log
from backend import personajes as personajes_cfg
from backend.services import translation_service
from backend.services import voice_service

# Cliente y colección de ChromaDB, cargados una sola vez (singleton perezoso).
_client: chromadb.ClientAPI | None = None
_collection = None

# Icono por origen, solo para la traza de consola en modo DEBUG.
_ICONO_ORIGEN = {"RAG": "🟢", "GENERAL": "🟡"}


def _trazar_origen(
    origen: str, metodo: str, distancia: float | None, pregunta_en: str
) -> None:
    """Imprime por la consola del BACKEND si la respuesta vino del RAG o no.

    Solo en modo DEBUG (config.DEBUG). Antes esto se calculaba/mostraba en el
    frontend; se hace aquí porque el backend ya tiene todos los datos, así no hay
    que enviarlos ni procesarlos en el cliente.
    """
    if not config.DEBUG:
        return
    icono = _ICONO_ORIGEN.get(origen, "⚪")
    # Qué significa el origen elegido (de dónde sale la respuesta del personaje).
    explica_origen = {
        "RAG": "respuesta FUNDAMENTADA en las fichas recuperadas de este personaje",
        "GENERAL": "las fichas no servían → responde con el conocimiento propio del LLM",
    }.get(origen, "origen desconocido")
    # Cómo se tomó la decisión RAG vs GENERAL (ver EVALUATOR_MODE).
    explica_metodo = {
        "umbral": "decidido GRATIS por la distancia coseno (sin llamar al LLM-juez)",
        "llm": "desempatado por el LLM-juez (la distancia caía en la zona dudosa)",
    }.get(metodo, metodo)

    print(f"[CHAT] {icono} Evaluator → origen={origen}: {explica_origen}")
    print(f"[CHAT]        método: {explica_metodo}")
    if distancia is not None:
        print(
            f"[CHAT]        mejor distancia d={distancia:.2f}  "
            f"(umbrales coseno: BAJO={config.EVALUATOR_UMBRAL_BAJO}→RAG, "
            f"ALTO={config.EVALUATOR_UMBRAL_ALTO}→GENERAL; entre ambos=dudoso)"
        )
    print(f'[CHAT]        pregunta traducida (EN) que se buscó: "{pregunta_en}"')


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
            "[RAG] ⚠️  La colección de ChromaDB está VACÍA: no hay ninguna ficha "
            "indexada, así que el chat responderá sin contexto (respuestas pobres o "
            "siempre 'no lo sé'). Añade documentos en backend/documentos/<personaje>/ "
            "y reconstruye el índice con:  python -m backend.ingest"
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

    El prompt va EN INGLÉS a propósito (instrucciones + pregunta ya traducida ES→EN
    + fichas, que ya están en inglés): Llama 3 sigue mejor las instrucciones en
    inglés. La RESPUESTA, en cambio, se pide explícitamente EN ESPAÑOL, porque es lo
    que leerá el niño (el modelo genera español sin problema aunque se le instruya
    en inglés).
    """
    fichas_texto = "\n".join(f"- {ficha}" for ficha in contexto) or "(no data)"

    system = (
        f"You are {nombre}, speaking in the first person to a child aged 8 to 12. "
        "ALWAYS reply in Spanish, in a short (2-4 sentences), cheerful and simple "
        "way. Use ONLY the information in the cards I give you. If the answer is not "
        "in the cards, kindly say that you do not know that, without making anything "
        "up. Never break character. "
        "Do NOT start your answer with a greeting or by introducing yourself "
        "(no 'Hola', no 'Como [name]'); answer directly as if continuing a conversation."
    )

    user = (
        f"Cards with data about me:\n{fichas_texto}\n\n"
        f"Child's question: {pregunta}\n\n"
        "Your answer (in the first person, in Spanish):"
    )
    return system, user


def _construir_prompt_general(nombre: str, pregunta: str) -> tuple[str, str]:
    """Prompt para el camino GENERAL (sin fichas relevantes).

    El personaje responde con su conocimiento propio, manteniéndose en su papel y
    con lenguaje apto para niños. Si tampoco lo sabe, lo dice con simpatía.

    Mismo criterio que _construir_prompt: instrucciones + pregunta EN INGLÉS (Llama 3
    obedece mejor), pero la RESPUESTA se pide EN ESPAÑOL (es lo que lee el niño).
    """
    system = (
        f"You are {nombre}, speaking in the first person to a child aged 8 to 12. "
        "ALWAYS reply in Spanish, in a short (2-4 sentences), cheerful and simple "
        "way, never breaking character. You have no data cards for this question: "
        "answer with your own general knowledge, and if you do not know, kindly say "
        "so without making anything up. "
        "Do NOT start your answer with a greeting or by introducing yourself "
        "(no 'Hola', no 'Como [name]'); answer directly as if continuing a conversation."
    )
    user = (
        f"Child's question: {pregunta}\n\n"
        "Your answer (in the first person, in Spanish):"
    )
    return system, user


def _llamar_llm(
    system: str,
    user: str,
    max_tokens: int | None = None,
    temperature: float = 0.3,
    etiqueta: str = "LLM",
) -> str:
    """Llama al LLM en Replicate y devuelve el texto de la respuesta.

    Los modelos de chat de Replicate devuelven la respuesta "en trocitos"
    (streaming): una secuencia de cadenas que hay que unir.

    `max_tokens` y `temperature` son configurables porque el Evaluator (juez)
    necesita una respuesta cortísima y determinista, mientras que la respuesta
    del personaje admite más longitud y algo de creatividad.

    `etiqueta` identifica el uso ("RAG", "GENERAL", "Evaluator") solo para la
    traza de prompts en modo DEBUG; no afecta a la llamada.
    """
    # En modo DEBUG, deja a la vista en consola el prompt completo (system + user)
    # que recibe el modelo. Es el ÚNICO sitio por el que pasan los 3 usos del LLM.
    debug_log.trazar_prompt(
        f"Replicate · {etiqueta} ({config.REPLICATE_LLM_MODEL})",
        system=system,
        user=user,
    )

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
    system = (
        "You are a strict evaluator for a RAG system. Your only task is to decide "
        "whether the context cards contain information to answer the question. "
        "Reply with EXACTLY one word, no explanation: 'YES' if the cards are "
        "relevant and sufficient, or 'NO' if they are not."
    )
    user = (
        f"Context cards:\n{fichas_texto}\n\n"
        f"Question: {pregunta}\n\n"
        "Are the cards relevant to answer it? Reply only YES or NO:"
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


def _sintetizar_respuesta(personaje_id: str, respuesta: str) -> str | None:
    """Devuelve la respuesta como mp3 en base64, o None.

    Degradación elegante: si el personaje no tiene voz_id, si falta la clave de
    ElevenLabs, o si el TTS falla, devuelve None. El texto de la respuesta NUNCA
    se rompe por un fallo de voz.
    """
    voz_id = personajes_cfg.VOCES.get(personaje_id)
    if not voz_id or not config.ELEVENLABS_API_KEY:
        return None
    try:
        audio_bytes = voice_service.sintetizar(respuesta, voz_id)
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    except Exception as exc:
        if config.DEBUG:
            print(
                f"[VOZ] ⚠️ TTS (síntesis de voz) FALLÓ para el personaje "
                f"'{personaje_id}' (voz_id={voz_id}): {exc}. Degradación elegante: la "
                "respuesta se entrega SOLO en texto (audio_base64=null); el chat sigue."
            )
        return None
    if config.DEBUG:
        print(
            f"[VOZ] 🔊 TTS OK · personaje={personaje_id} · voz_id={voz_id} · "
            f"{len(respuesta)} caracteres → mp3 base64 "
            f"(ElevenLabs modelo={config.ELEVENLABS_TTS_MODEL})"
        )
    return audio_b64


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
    #    traducimos la pregunta ES→EN. La versión en inglés (pregunta_en) se usa en
    #    TODAS las peticiones al modelo —retrieval, Evaluator y generación—, porque
    #    Llama 3 entiende y obedece mejor en inglés. Si DeepL no está disponible,
    #    traducir_es_en lanza TranslationError (subclase de ValueError) → el router
    #    responde 400 con un mensaje claro, en vez de dar una respuesta mala.
    #    (Solo se traduce la pregunta del niño; la RESPUESTA del personaje va en español.)
    pregunta_en = translation_service.traducir_es_en(pregunta)

    # 1) RETRIEVAL: recuperar las fichas candidatas y sus distancias (con la
    #    pregunta YA en inglés, igual que las fichas).
    contexto, distancias = _recuperar_contexto(personaje_id, pregunta_en)

    # 2) EVALUATOR + ROUTER: ¿son esas fichas relevantes? (umbral / llm / híbrido)
    es_rag, metodo, distancia = _decidir_origen(contexto, distancias, pregunta_en)

    if es_rag:
        # --- Camino RAG: respuesta FUNDAMENTADA solo en las fichas ---
        origen = "RAG"
        # Pasamos la pregunta YA traducida (pregunta_en): Llama 3 entiende y obedece
        # mejor en inglés. La respuesta, eso sí, se genera en español (lo pide el prompt).
        system, user = _construir_prompt(nombre, contexto, pregunta_en)
        respuesta = _llamar_llm(system, user, etiqueta="RAG")
        fuentes = contexto
    else:
        # --- Camino GENERAL: las fichas no sirven; el personaje responde con su
        # conocimiento propio (aquí, en el futuro, podría enrutarse a búsqueda web).
        origen = "GENERAL"
        # Igual que en RAG: la pregunta va en inglés (pregunta_en), la respuesta en español.
        system, user = _construir_prompt_general(nombre, pregunta_en)
        respuesta = _llamar_llm(system, user, etiqueta="GENERAL")
        fuentes = []  # no hay fichas detrás de esta respuesta

    # Traza de depuración (solo si DEBUG): en la consola del BACKEND, no del cliente.
    _trazar_origen(origen, metodo, distancia, pregunta_en)

    # Síntesis de voz de la respuesta (si el personaje tiene voz_id y hay clave).
    # Si falla, audio_base64 queda None y la respuesta sigue viva en texto.
    audio_base64 = _sintetizar_respuesta(personaje_id, respuesta)

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
        "audio_base64": audio_base64,
    }
