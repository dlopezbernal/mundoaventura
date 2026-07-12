/**
 * src/api/types.ts — Contrato de la API (tipos)
 * ==============================================
 *
 * Interfaces TypeScript que replican EXACTAMENTE los schemas Pydantic del
 * backend (backend/schemas/generation.py y backend/schemas/conversacion.py).
 * Si el backend cambia un schema, este archivo debe cambiar con él.
 */

/** Petición del endpoint POST /api/generate. */
export interface GenerateRequest {
  /** Identificador del personaje (ej. "t-rex"). */
  personaje_id: string;
  /** Identificador de la ubicación (ej. "laboratorio"). */
  ubicacion_id: string;
}

/** Respuesta del endpoint POST /api/generate (y de /api/generate-on-photo). */
export interface GenerateResponse {
  /** True si se generó la imagen correctamente. */
  success: boolean;
  /** Identificador del personaje generado (eco de lo pedido). */
  personaje_id: string;
  /** Identificador de la ubicación generada (eco de lo pedido). */
  ubicacion_id: string;
  /** Escena generada (personaje + ubicación), codificada en base64. */
  result_png_base64: string;
}

/** Petición del endpoint POST /api/ask. */
export interface AskRequest {
  /** Identificador del personaje al que se pregunta (ej. "t-rex"). */
  personaje_id: string;
  /** La pregunta del niño, en texto. */
  pregunta: string;
}

/** Respuesta del endpoint POST /api/ask. */
export interface AskResponse {
  /** True si se generó la respuesta. */
  success: boolean;
  /** Personaje que respondió. */
  personaje_id: string;
  /** Eco de la pregunta recibida. */
  pregunta: string;
  /** Respuesta del personaje, en primera persona y en español. */
  respuesta: string;
  /**
   * De dónde sale la respuesta: "RAG" (fundamentada en la enciclopedia) o
   * "GENERAL" (conocimiento propio del modelo).
   */
  origen: string;
  /** Cómo se decidió el origen: "umbral" (distancia) o "llm" (juez). */
  metodo: string;
  /**
   * La pregunta traducida a inglés (DeepL) usada para buscar.
   * Si es igual a la original, la traducción no se aplicó.
   */
  pregunta_traducida: string;
  /**
   * Mejor distancia coseno encontrada (menor = más parecido).
   * Útil para calibrar los umbrales del Evaluator.
   */
  distancia: number | null;
  /** Fragmentos (chunks) de los documentos usados para fundamentar la respuesta. */
  fuentes: string[];
  /**
   * Respuesta del personaje sintetizada a voz (mp3 en base64), o null si el
   * personaje no tiene voz o si el TTS falló (el texto no se rompe).
   */
  audio_base64: string | null;
}

/** Respuesta del endpoint POST /api/transcribe. */
export interface TranscribeResponse {
  /** El texto transcrito del audio del niño. */
  texto: string;
}

/**
 * Estado de un proveedor de API (GET /api/apis). La clave NUNCA llega completa:
 * solo `configurado` y el valor `enmascarado`. Replica secrets_service.estado().
 */
export interface ApiProviderStatus {
  /** "replicate" | "deepl" | "elevenlabs". */
  proveedor: string;
  /** Nombre de la variable en el .env (p. ej. "DEEPL_API_KEY"). */
  variable: string;
  /** Nombre visible del proveedor (p. ej. "DeepL"). */
  nombre: string;
  /** Enlace para darse de alta y crear la clave. */
  ayuda_url: string;
  /** ¿Hay una clave configurada? */
  configurado: boolean;
  /** Clave enmascarada ("••••••1234") o null si no hay. */
  enmascarado: string | null;
}

/** Resultado de POST /api/apis/{proveedor}/test (probar conexión). */
export interface ApiTestResult {
  ok: boolean;
  mensaje: string;
}

/**
 * Metadatos + valor vigente de UN ajuste editable (Hito 3). Replica una entrada
 * de settings_service.exportar(): describe qué es el ajuste y cómo pintarlo.
 */
export interface SettingMeta {
  /** Clave interna (p. ej. "EVALUATOR_UMBRAL_BAJO"). */
  clave: string;
  /** Valor vigente, ya tipado (number | string | boolean). */
  valor: number | string | boolean;
  /** Tipo del ajuste: "int" | "float" | "str" | "bool". */
  tipo: string;
  /** Categoría para agrupar en la UI (p. ej. "rag", "llm", "prompts", "general"). */
  categoria: string;
  /** Si cambiarlo obliga a reindexar ChromaDB (chunking). */
  requiere_reindex: boolean;
  /** Texto de ayuda en español para el adulto. */
  ayuda: string;
  /** Mínimo (solo int/float). */
  min?: number;
  /** Máximo (solo int/float). */
  max?: number;
  /** Salto del control numérico (solo float). */
  paso?: number;
  /** Opciones cerradas (si el ajuste es un desplegable). */
  opciones?: string[];
  /** Si el texto es largo → la UI lo pinta como área de texto. */
  multilinea?: boolean;
}

/** Respuesta del endpoint GET /api/config (ajustes + estado de secretos). */
export interface ConfigResponse {
  ajustes: SettingMeta[];
  secretos: ApiProviderStatus[];
}

/**
 * Un personaje del catálogo (GET /api/personajes). Replica el dict de
 * personajes_service: el `id` es el invariante `personaje_id`.
 */
export interface PersonajeDTO {
  /** Id invariante (minúsculas, números, - y _). */
  id: string;
  /** Nombre con el que se presenta en el chat. */
  nombre: string;
  /** "prehistorico" | "historico" | "ficticio" (o null). */
  categoria: string | null;
  /** Emoji de la carta (miniatura), o null. */
  emoji: string | null;
  /** Descripción en inglés para generar su imagen. */
  prompt_imagen: string;
  /** Voz de ElevenLabs (voz_id), o null = responde solo en texto. */
  voz_id: string | null;
  /** Si aparece en el catálogo del niño. */
  activo: boolean;
  /** Prompt de sistema propio (opcional; si null, usa el general). */
  prompt_sistema_override: string | null;
}

/** Datos para crear un personaje (POST /api/personajes). */
export interface PersonajeCrear {
  id: string;
  nombre: string;
  prompt_imagen: string;
  categoria?: string | null;
  emoji?: string | null;
  voz_id?: string | null;
  prompt_sistema_override?: string | null;
  activo?: boolean;
}

/** Una voz de ElevenLabs (GET /api/voices). */
export interface VozDTO {
  voz_id: string;
  nombre: string;
  categoria: string | null;
}

/** Respuesta de GET /api/voices: lista de voces + aviso si no está disponible. */
export interface VocesResponse {
  disponible: boolean;
  voces: VozDTO[];
  mensaje: string;
}

/**
 * Un documento del RAG de un personaje (GET /api/personajes/{id}/documentos).
 * Replica el dict de documentos_service (metadatos; el fichero vive en disco).
 */
export interface DocumentoDTO {
  id: number;
  personaje_id: string;
  /** Nombre del fichero guardado en documentos/<id>/. */
  nombre_archivo: string;
  /** "subido" | "url". */
  origen: string;
  /** URL de origen si vino de Wikipedia, o null. */
  url_origen: string | null;
  /** Idioma detectado/asumido del original ("es" | "en" | null). */
  idioma_original: string | null;
  /** Si se tradujo a inglés al guardarlo. */
  traducido: boolean;
  /** Fecha de alta (ISO). */
  creado_en: string;
}

/** Resultado de un reindexado (por personaje o global). */
export interface ReindexResult {
  personaje_id?: string;
  personajes?: number;
  archivos: number;
  chunks: number;
}

/**
 * Una ubicación del catálogo (GET /api/ubicaciones). Replica el dict de
 * ubicaciones_service: el `id` es el invariante de la ubicación.
 */
export interface UbicacionDTO {
  id: string;
  /** Nombre visible en la carta. */
  nombre: string;
  /** Emoji de la carta (miniatura), o null. */
  emoji: string | null;
  /** Descripción en inglés del fondo de la escena. */
  prompt_imagen: string;
  /** Si aparece en el catálogo del niño. */
  activo: boolean;
}

/** Datos para crear una ubicación (POST /api/ubicaciones). */
export interface UbicacionCrear {
  id: string;
  nombre: string;
  prompt_imagen: string;
  emoji?: string | null;
  activo?: boolean;
}

/** Estado del acceso de administrador (GET /api/admin/status). */
export interface AdminStatus {
  /** ¿Hay ya un PIN de adulto creado? */
  configurado: boolean;
  /** ¿El token actual (si hay) sigue siendo válido? */
  sesion_activa: boolean;
}

/** Configuración exportada (GET /api/admin/export). Sin secretos. */
export interface ConfigExport {
  version: number;
  exportado_en: string;
  ajustes: Record<string, unknown>;
  personajes: PersonajeDTO[];
  ubicaciones: UbicacionDTO[];
}

/** Resultado de importar configuración (POST /api/admin/import). */
export interface ImportResult {
  ok: boolean;
  resumen: { ajustes: number; personajes: number; ubicaciones: number };
  /** Ruta de la copia de seguridad del SQLite hecha antes de importar (o null). */
  backup: string | null;
}

/** Respuesta del endpoint PUT /api/config (guardar ajustes en caliente). */
export interface ConfigSaveResult {
  ok: boolean;
  /** Ajustes cambiados que exigen reindexar ChromaDB (vacío si ninguno). */
  reindex_necesario: string[];
}

/**
 * Respuesta del endpoint GET /health. No tiene schema Pydantic en el backend
 * (es un dict ad-hoc en main.py); tipamos los campos que el frontend consulta
 * y dejamos el resto abiertos.
 */
export interface HealthResponse {
  status: string;
  token_configurado?: boolean;
  deepl_ok?: boolean;
  elevenlabs_ok?: boolean;
  [key: string]: unknown;
}
