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
