/**
 * src/api/client.ts — Cliente HTTP hacia el backend
 * ==================================================
 *
 * Este módulo es el "teléfono" del frontend: encapsula CÓMO se habla con el
 * backend, para que la interfaz no tenga que saber de URLs ni base64.
 * Replica las 5 funciones de legacy/frontend-flet/api_client.py con fetch.
 *
 * Si mañana cambia la API, solo tocamos aquí.
 */

import type {
  AdminStatus,
  ApiProviderStatus,
  ApiTestResult,
  AskRequest,
  AskResponse,
  ConfigExport,
  ConfigResponse,
  ConfigSaveResult,
  CopiaResult,
  DocumentoContenido,
  DocumentoDTO,
  FamiliaAuthResponse,
  FamiliaReenviarResponse,
  FamiliaSesion,
  FamiliasEstado,
  FamiliaSignupResponse,
  GenerateRequest,
  GenerateResponse,
  HealthResponse,
  ImportResult,
  PersonajeCrear,
  PersonajeDTO,
  PersonajesInfo,
  ReindexEstado,
  ReindexResult,
  SettingMeta,
  SubidaMultipleResult,
  TranscribeResponse,
  UbicacionCrear,
  UbicacionDTO,
  VocesResponse,
} from "./types";

// URL del backend. Vacía = mismo origen (en dev, el proxy de vite.config.ts
// redirige /api y /health al backend local). Con Colab, se pone la del túnel
// en VITE_BACKEND_URL (ver .env.example).
const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL ?? "").replace(/\/+$/, "");

// Código de acceso del túnel (Hito 2). Si el backend tiene ACCESS_CODE configurado,
// los endpoints del niño (chat/generación/voz) exigen esta cabecera. Vacío = el
// backend no tiene candado (dev). Se define en frontend-react/.env (VITE_ACCESS_CODE).
const ACCESS_CODE = (import.meta.env.VITE_ACCESS_CODE ?? "").trim();

// Timeouts (ms), equivalentes a los del cliente Flet.
const TIMEOUT_HEALTH = 10_000;
const TIMEOUT_GENERATE = 120_000;
const TIMEOUT_GENERATE_ON_PHOTO = 180_000; // la edición (Kontext) tarda más que schnell
const TIMEOUT_ASK = 120_000;
const TIMEOUT_TRANSCRIBE = 60_000;
const TIMEOUT_CONFIG = 30_000; // config: lecturas rápidas y "probar conexión"
const TIMEOUT_DOCS = 180_000; // subir/URL/reindex: traducción DeepL + embeddings
const TIMEOUT_VOZ_PROBAR = 30_000; // TTS de una frase corta

/** Error al comunicarnos con el backend (lo mostramos al usuario). */
export class BackendError extends Error {
  /** Código HTTP de la respuesta, si la hubo (p. ej. 409 = conflicto de nombre). */
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "BackendError";
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Token de administrador (Hito 7). El área de configuración va detrás de un PIN
// de adulto; tras iniciar sesión guardamos el token aquí y en sessionStorage (se
// borra al cerrar la pestaña) y lo enviamos en cada petición como X-Admin-Token.
// ---------------------------------------------------------------------------
const _ADMIN_KEY = "mdt_admin_token";
let _adminToken: string | null =
  typeof sessionStorage !== "undefined" ? sessionStorage.getItem(_ADMIN_KEY) : null;

/** Guarda (o borra, con null) el token de sesión de administrador. */
export function setAdminToken(token: string | null): void {
  _adminToken = token;
  try {
    if (token) sessionStorage.setItem(_ADMIN_KEY, token);
    else sessionStorage.removeItem(_ADMIN_KEY);
  } catch {
    /* sessionStorage puede no estar disponible; el token vive en memoria igualmente */
  }
}

/** Token de administrador actual (o null si no hay sesión). */
export function getAdminToken(): string | null {
  return _adminToken;
}

// ---------------------------------------------------------------------------
// Token de FAMILIA (Hito 9.2). La app va detrás de una sesión de familia. A
// diferencia del token de admin (sessionStorage: se borra al cerrar la pestaña),
// el de familia se guarda en localStorage para que la sesión PERSISTA en el
// dispositivo (no volver a pedir login). Se envía como X-Family-Token.
// ---------------------------------------------------------------------------
const _FAMILY_KEY = "mdt_family_token";
let _familyToken: string | null =
  typeof localStorage !== "undefined" ? localStorage.getItem(_FAMILY_KEY) : null;

/** Guarda (o borra, con null) el token de sesión de familia. */
export function setFamilyToken(token: string | null): void {
  _familyToken = token;
  try {
    if (token) localStorage.setItem(_FAMILY_KEY, token);
    else localStorage.removeItem(_FAMILY_KEY);
  } catch {
    /* localStorage puede no estar disponible; el token vive en memoria igualmente */
  }
}

/** Token de familia actual (o null si no hay sesión). */
export function getFamilyToken(): string | null {
  return _familyToken;
}

/**
 * fetch con timeout vía AbortController.
 * Lanza BackendError con mensaje amigable si la petición falla, expira o el
 * backend responde con error (extrayendo "detail" del JSON si existe, igual
 * que hacía api_client.py).
 */
async function fetchBackend(
  path: string,
  options: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  // Añadimos el token de adulto (si hay) a TODAS las peticiones: los endpoints
  // del flujo del niño lo ignoran, y los protegidos lo exigen.
  const headers: Record<string, string> = { ...((options.headers as Record<string, string>) ?? {}) };
  if (_adminToken) headers["X-Admin-Token"] = _adminToken;
  // Token de familia (sesión de la app): los endpoints de familia lo exigen; los
  // demás lo ignoran. Enviarlo en todas es inofensivo.
  if (_familyToken) headers["X-Family-Token"] = _familyToken;
  // Candado del túnel: los endpoints del niño lo exigen si el backend tiene
  // ACCESS_CODE; los demás lo ignoran. Enviarlo en todas es inofensivo.
  if (ACCESS_CODE) headers["X-Access-Code"] = ACCESS_CODE;

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (exc) {
    if (exc instanceof DOMException && exc.name === "AbortError") {
      throw new BackendError(
        "La máquina del tiempo está tardando mucho. Espera un poquito y vuelve a intentarlo.",
      );
    }
    throw new BackendError(
      "No pude conectar con la máquina del tiempo. Pide a un adulto que compruebe que está encendida.",
    );
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    // Intentamos extraer el "detail" del JSON de error de FastAPI.
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? "";
    } catch {
      try {
        detail = await response.text();
      } catch {
        detail = "";
      }
    }
    // 429 (rate limit / cupo diario agotado): el backend manda un mensaje amable y
    // en personaje. Se muestra TAL CUAL, sin el prefijo "Algo ha salido mal".
    if (response.status === 429 && detail) {
      throw new BackendError(detail, 429);
    }
    throw new BackendError(
      `Algo ha salido mal: ${detail || `error ${response.status}`}`,
      response.status,
    );
  }

  return response;
}

/** Pregunta al backend por su estado (/health). Devuelve el JSON o lanza error. */
export async function checkHealth(): Promise<HealthResponse> {
  try {
    const response = await fetchBackend("/health", { method: "GET" }, TIMEOUT_HEALTH);
    return (await response.json()) as HealthResponse;
  } catch (exc) {
    if (exc instanceof BackendError) {
      throw new BackendError(
        `No se pudo contactar con el backend en ${BACKEND_URL || "el mismo origen"}: ${exc.message}`,
      );
    }
    throw exc;
  }
}

/**
 * Pide al backend generar la escena del personaje en la ubicación elegidos.
 *
 * Devuelve, entre otros, result_png_base64: la escena generada (imagen en base64).
 */
export async function generate(
  ubicacionId: string,
  personajeId: string,
): Promise<GenerateResponse> {
  const payload: GenerateRequest = {
    personaje_id: personajeId,
    ubicacion_id: ubicacionId,
  };
  const response = await fetchBackend(
    "/api/generate",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    TIMEOUT_GENERATE,
  );
  return (await response.json()) as GenerateResponse;
}

/**
 * Pide al backend estilizar la foto del niño y añadir el personaje.
 *
 * Sube la foto (multipart) a /api/generate-on-photo. Devuelve, entre otros,
 * result_png_base64: la foto en estilo Pixar 3D con el personaje añadido.
 */
export async function generateOnPhoto(
  imageFile: File,
  personajeId: string,
): Promise<GenerateResponse> {
  const formData = new FormData();
  formData.append("image", imageFile, imageFile.name);
  formData.append("personaje_id", personajeId);
  const response = await fetchBackend(
    "/api/generate-on-photo",
    { method: "POST", body: formData },
    TIMEOUT_GENERATE_ON_PHOTO,
  );
  return (await response.json()) as GenerateResponse;
}

/**
 * Envía una pregunta (texto) al personaje y devuelve su respuesta (RAG).
 *
 * Devuelve, entre otros:
 *   - respuesta:    el texto que dice el personaje (en primera persona).
 *   - fuentes:      las fichas de la enciclopedia en las que se apoyó.
 *   - audio_base64: la respuesta en voz (mp3 base64) o null si no hay voz.
 */
export async function ask(
  personajeId: string,
  pregunta: string,
): Promise<AskResponse> {
  const payload: AskRequest = { personaje_id: personajeId, pregunta };
  const response = await fetchBackend(
    "/api/ask",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    TIMEOUT_ASK,
  );
  return (await response.json()) as AskResponse;
}

/**
 * Callbacks del streaming de la respuesta (Hito 8). Cada uno se invoca según van
 * llegando los eventos SSE del backend, para pintar/hablar de forma incremental.
 */
export interface StreamCallbacks {
  /** Fuentes del RAG (una vez, al principio; vacío si no aplica). */
  onFuentes?: (fuentes: string[]) => void;
  /** Un trozo de texto de la respuesta (se van concatenando). */
  onToken?: (texto: string) => void;
  /** Audio (mp3 base64) de una FRASE ya sintetizada, para encolar y reproducir. */
  onAudio?: (audioBase64: string) => void;
  /** Fin: la respuesta completa (texto ya unido). */
  onFin?: (respuesta: string) => void;
  /** Error emitido por el backend a mitad de stream (mensaje ya apto para el niño). */
  onError?: (mensaje: string) => void;
}

/** Procesa un frame SSE (`event: <tipo>` + `data: <json>`) y llama al callback. */
function _procesarFrameSSE(frame: string, cb: StreamCallbacks): void {
  let evento = "message";
  const datos: string[] = [];
  for (const linea of frame.split("\n")) {
    if (linea.startsWith("event:")) evento = linea.slice(6).trim();
    else if (linea.startsWith("data:")) datos.push(linea.slice(5).trim());
  }
  if (datos.length === 0) return;
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(datos.join("\n")) as Record<string, unknown>;
  } catch {
    return; // frame incompleto o no-JSON: se ignora
  }
  if (evento === "fuentes") cb.onFuentes?.((payload.fuentes as string[]) ?? []);
  else if (evento === "token") cb.onToken?.((payload.texto as string) ?? "");
  else if (evento === "audio_chunk") cb.onAudio?.((payload.audio_base64 as string) ?? "");
  else if (evento === "fin") cb.onFin?.((payload.respuesta as string) ?? "");
  else if (evento === "error") cb.onError?.((payload.mensaje as string) ?? "Algo ha salido mal.");
}

/**
 * Como `ask`, pero en STREAMING (SSE): invoca los callbacks según llegan el texto
 * (token a token) y el audio (frase a frase). Baja la latencia PERCIBIDA (Hito 8).
 * No lleva timeout por AbortController (un stream dura lo que dure); se puede cortar
 * con `signal`. El endpoint JSON `ask` sigue disponible para quien prefiera la
 * respuesta de una vez.
 */
export async function askStream(
  personajeId: string,
  pregunta: string,
  cb: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const payload: AskRequest = { personaje_id: personajeId, pregunta };
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (_adminToken) headers["X-Admin-Token"] = _adminToken;
  if (_familyToken) headers["X-Family-Token"] = _familyToken;
  if (ACCESS_CODE) headers["X-Access-Code"] = ACCESS_CODE;

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/api/ask/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal,
    });
  } catch (exc) {
    if (exc instanceof DOMException && exc.name === "AbortError") return; // cancelado a propósito
    throw new BackendError(
      "No pude conectar con la máquina del tiempo. Pide a un adulto que compruebe que está encendida.",
    );
  }

  if (!response.ok || !response.body) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? "";
    } catch {
      detail = "";
    }
    if (response.status === 429 && detail) throw new BackendError(detail, 429);
    throw new BackendError(`Algo ha salido mal: ${detail || `error ${response.status}`}`, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // Los frames SSE se separan por una línea en blanco (\n\n).
    let corte = buffer.indexOf("\n\n");
    while (corte !== -1) {
      _procesarFrameSSE(buffer.slice(0, corte), cb);
      buffer = buffer.slice(corte + 2);
      corte = buffer.indexOf("\n\n");
    }
  }
}

/**
 * Sube el audio grabado (multipart) a /api/transcribe y devuelve el texto.
 *
 * Se usa cuando el niño pregunta por voz: graba → transcribe → el texto entra
 * al mismo flujo que una pregunta escrita.
 */
export async function transcribe(
  audio: Blob,
  filename = "grabacion.webm",
): Promise<string> {
  const formData = new FormData();
  formData.append("audio", audio, filename);
  const response = await fetchBackend(
    "/api/transcribe",
    { method: "POST", body: formData },
    TIMEOUT_TRANSCRIBE,
  );
  const body = (await response.json()) as TranscribeResponse;
  return body.texto ?? "";
}

// ---------------------------------------------------------------------------
// Configuración · APIs (Hito 2). Las claves NUNCA llegan completas salvo revealApi.
// ---------------------------------------------------------------------------

/** Estado de los 3 proveedores (claves enmascaradas). GET /api/apis. */
export async function getApis(): Promise<ApiProviderStatus[]> {
  const response = await fetchBackend("/api/apis", { method: "GET" }, TIMEOUT_CONFIG);
  const body = (await response.json()) as { proveedores: ApiProviderStatus[] };
  return body.proveedores;
}

/** Guarda claves en el .env (solo los proveedores incluidos). PUT /api/apis. */
export async function saveApis(
  claves: Record<string, string>,
): Promise<ApiProviderStatus[]> {
  const response = await fetchBackend(
    "/api/apis",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ claves }),
    },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as { proveedores: ApiProviderStatus[] };
  return body.proveedores;
}

/** Prueba la conexión de un proveedor. POST /api/apis/{proveedor}/test. */
export async function testApi(proveedor: string): Promise<ApiTestResult> {
  const response = await fetchBackend(
    `/api/apis/${proveedor}/test`,
    { method: "POST" },
    TIMEOUT_CONFIG,
  );
  return (await response.json()) as ApiTestResult;
}

/** Revela la clave COMPLETA de un proveedor (icono del ojo). POST .../reveal. */
export async function revealApi(proveedor: string): Promise<string | null> {
  const response = await fetchBackend(
    `/api/apis/${proveedor}/reveal`,
    { method: "POST" },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as { clave: string | null };
  return body.clave;
}

// ---------------------------------------------------------------------------
// Configuración · Ajustes del motor (Hito 3). Parámetros de IA, prompts y DEBUG.
// ---------------------------------------------------------------------------

/** Ajustes vigentes + metadatos (para pintar la UI). GET /api/config. */
export async function getConfig(): Promise<SettingMeta[]> {
  const response = await fetchBackend("/api/config", { method: "GET" }, TIMEOUT_CONFIG);
  const body = (await response.json()) as ConfigResponse;
  return body.ajustes;
}

/**
 * Guarda ajustes y los aplica en caliente (sin reiniciar). PUT /api/config.
 * Devuelve qué ajustes exigen reindexar ChromaDB (lista vacía si ninguno).
 */
export async function saveConfig(
  ajustes: Record<string, number | string | boolean>,
): Promise<string[]> {
  const response = await fetchBackend(
    "/api/config",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ajustes }),
    },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as ConfigSaveResult;
  return body.reindex_necesario;
}

// ---------------------------------------------------------------------------
// Configuración · Personajes (Hito 4). Catálogo consumido por la pantalla del
// niño y por la pestaña de configuración (CRUD).
// ---------------------------------------------------------------------------

/** Catálogo de personajes. Por defecto solo activos; `todos=true` incluye inactivos. */
export async function getPersonajes(todos = false): Promise<PersonajeDTO[]> {
  const query = todos ? "?todos=1" : "";
  const response = await fetchBackend(`/api/personajes${query}`, { method: "GET" }, TIMEOUT_CONFIG);
  const body = (await response.json()) as { personajes: PersonajeDTO[] };
  return body.personajes;
}

/**
 * Igual que `getPersonajes`, pero incluye `limite` (MAX_PERSONAJES): lo usa la
 * pestaña de configuración para deshabilitar "Nuevo personaje" al llegar al tope.
 */
export async function getPersonajesInfo(todos = false): Promise<PersonajesInfo> {
  const query = todos ? "?todos=1" : "";
  const response = await fetchBackend(`/api/personajes${query}`, { method: "GET" }, TIMEOUT_CONFIG);
  return (await response.json()) as PersonajesInfo;
}

/** Crea un personaje nuevo. POST /api/personajes. */
export async function createPersonaje(datos: PersonajeCrear): Promise<PersonajeDTO> {
  const response = await fetchBackend(
    "/api/personajes",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as { personaje: PersonajeDTO };
  return body.personaje;
}

/** Edita campos de un personaje (solo los incluidos). PUT /api/personajes/{id}. */
export async function updatePersonaje(
  id: string,
  cambios: Partial<Omit<PersonajeDTO, "id">>,
): Promise<PersonajeDTO> {
  const response = await fetchBackend(
    `/api/personajes/${id}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cambios),
    },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as { personaje: PersonajeDTO };
  return body.personaje;
}

/** Borra un personaje del catálogo. DELETE /api/personajes/{id}. */
export async function deletePersonaje(id: string): Promise<void> {
  await fetchBackend(`/api/personajes/${id}`, { method: "DELETE" }, TIMEOUT_CONFIG);
}

/** Voces disponibles en ElevenLabs para el desplegable. GET /api/voices. */
export async function getVoices(): Promise<VocesResponse> {
  const response = await fetchBackend("/api/voices", { method: "GET" }, TIMEOUT_CONFIG);
  return (await response.json()) as VocesResponse;
}

/**
 * Sintetiza la frase de prueba con `vozId` (botón "🔊 Probar voz"). Devuelve el
 * audio en base64 (mp3), listo para `new Audio("data:audio/mpeg;base64,...")`.
 */
export async function probarVoz(vozId: string): Promise<string> {
  const response = await fetchBackend(
    "/api/voices/probar",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voz_id: vozId }),
    },
    TIMEOUT_VOZ_PROBAR,
  );
  const body = (await response.json()) as { audio_base64: string };
  return body.audio_base64;
}

// ---------------------------------------------------------------------------
// Configuración · Documentos del RAG por personaje (Hito 5).
// ---------------------------------------------------------------------------

/** Documentos de un personaje. GET /api/personajes/{id}/documentos. */
export async function getDocumentos(personajeId: string): Promise<DocumentoDTO[]> {
  const response = await fetchBackend(
    `/api/personajes/${personajeId}/documentos`,
    { method: "GET" },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as { documentos: DocumentoDTO[] };
  return body.documentos;
}

/** ¿Este error es un conflicto de "ya existe un documento con ese nombre" (409)? */
export function esConflictoDocumento(exc: unknown): boolean {
  return exc instanceof BackendError && exc.status === 409;
}

/** Respuesta mixta de subir 1 o varios documentos (ver uploadDocumentos). */
export type SubidaResult = { documento?: DocumentoDTO } & Partial<SubidaMultipleResult>;

/**
 * Sube uno o varios ficheros (.pdf/.txt/.md) al RAG de un personaje (multipart).
 * El idioma se detecta automáticamente (DeepL) y se traduce a inglés si hace
 * falta — no hay que indicarlo. Con un solo fichero, `documento` viene poblado;
 * con varios, `documentos`/`errores` (mejor esfuerzo: un fichero inválido no
 * aborta el resto). Si algún nombre ya existe y `sobrescribir` es false, lanza
 * BackendError con status 409 (usar `esConflictoDocumento` para detectarlo y
 * ofrecer reintentar).
 */
export async function uploadDocumentos(
  personajeId: string,
  archivos: File[],
  sobrescribir = false,
): Promise<SubidaResult> {
  const formData = new FormData();
  for (const archivo of archivos) formData.append("archivos", archivo, archivo.name);
  formData.append("sobrescribir", String(sobrescribir));
  const response = await fetchBackend(
    `/api/personajes/${personajeId}/documentos`,
    { method: "POST", body: formData },
    TIMEOUT_DOCS,
  );
  return (await response.json()) as SubidaResult;
}

/**
 * Ingesta un artículo de Wikipedia por URL. POST .../documentos/url. El idioma
 * se detecta automáticamente y se traduce si hace falta.
 * Lanza BackendError (status 409) si ya existe un documento con ese nombre y
 * `sobrescribir` es false.
 */
export async function addDocumentoUrl(
  personajeId: string,
  url: string,
  sobrescribir = false,
): Promise<DocumentoDTO> {
  const response = await fetchBackend(
    `/api/personajes/${personajeId}/documentos/url`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, sobrescribir }),
    },
    TIMEOUT_DOCS,
  );
  const body = (await response.json()) as { documento: DocumentoDTO };
  return body.documento;
}

/** Texto actual de un documento (para el visor). GET .../documentos/{id}/contenido. */
export async function getDocumentoContenido(
  personajeId: string,
  documentoId: number,
): Promise<DocumentoContenido> {
  const response = await fetchBackend(
    `/api/personajes/${personajeId}/documentos/${documentoId}/contenido`,
    { method: "GET" },
    TIMEOUT_CONFIG,
  );
  return (await response.json()) as DocumentoContenido;
}

/**
 * Edita el texto de un documento .txt/.md existente (no PDF). PUT .../contenido.
 * El idioma se detecta automáticamente (DeepL) y se traduce si hace falta.
 */
export async function updateDocumentoContenido(
  personajeId: string,
  documentoId: number,
  contenido: string,
): Promise<DocumentoDTO> {
  const response = await fetchBackend(
    `/api/personajes/${personajeId}/documentos/${documentoId}/contenido`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contenido }),
    },
    TIMEOUT_DOCS,
  );
  const body = (await response.json()) as { documento: DocumentoDTO };
  return body.documento;
}

/**
 * Descarga el fichero original de un documento. GET .../documentos/{id}/descargar.
 * Va por `fetchBackend` (fetch + blob), no un `<a href>` plano: el token admin
 * viaja como cabecera X-Admin-Token, que una navegación directa de <a> no envía
 * (el endpoint gated respondería 401).
 */
export async function descargarDocumento(
  personajeId: string,
  documentoId: number,
  nombreArchivo: string,
): Promise<void> {
  const response = await fetchBackend(
    `/api/personajes/${personajeId}/documentos/${documentoId}/descargar`,
    { method: "GET" },
    TIMEOUT_CONFIG,
  );
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombreArchivo;
  enlace.click();
  URL.revokeObjectURL(url);
}

/**
 * Copia (de forma independiente) un documento a uno o varios personajes destino.
 * POST .../documentos/{id}/copiar. Mejor esfuerzo por destino: un destino que
 * falle (no existe, o conflicto de nombre sin `sobrescribir`) va a `errores` sin
 * abortar los demás.
 */
export async function copiarDocumento(
  personajeId: string,
  documentoId: number,
  personajesDestino: string[],
  sobrescribir = false,
): Promise<CopiaResult> {
  const response = await fetchBackend(
    `/api/personajes/${personajeId}/documentos/${documentoId}/copiar`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ personajes_destino: personajesDestino, sobrescribir }),
    },
    TIMEOUT_DOCS,
  );
  return (await response.json()) as CopiaResult;
}

/** Borra un documento. DELETE /api/personajes/{id}/documentos/{docId}. */
export async function deleteDocumento(personajeId: string, documentoId: number): Promise<void> {
  await fetchBackend(
    `/api/personajes/${personajeId}/documentos/${documentoId}`,
    { method: "DELETE" },
    TIMEOUT_DOCS,
  );
}

/** Reindexa (incremental) los documentos de un personaje. POST .../reindex. */
export async function reindexPersonaje(personajeId: string): Promise<ReindexResult> {
  const response = await fetchBackend(
    `/api/personajes/${personajeId}/reindex`,
    { method: "POST" },
    TIMEOUT_DOCS,
  );
  const body = (await response.json()) as { resultado: ReindexResult };
  return body.resultado;
}

/** Reindexa TODA la colección (global). POST /api/reindex. */
export async function reindexGlobal(): Promise<ReindexResult> {
  const response = await fetchBackend("/api/reindex", { method: "POST" }, TIMEOUT_DOCS);
  const body = (await response.json()) as { resultado: ReindexResult };
  return body.resultado;
}

/**
 * Progreso del reindexado global en curso (GET /api/reindex/estado). Se sondea
 * mientras dura `reindexGlobal()` para pintar una barra de progreso real.
 */
export async function getReindexEstado(): Promise<ReindexEstado> {
  const response = await fetchBackend("/api/reindex/estado", { method: "GET" }, TIMEOUT_CONFIG);
  return (await response.json()) as ReindexEstado;
}

// ---------------------------------------------------------------------------
// Configuración · Ubicaciones (Hito 6). Catálogo consumido por la pantalla del
// niño (elegir mundo) y por la pestaña de configuración (CRUD).
// ---------------------------------------------------------------------------

/** Catálogo de ubicaciones. Por defecto solo activas; `todos=true` incluye inactivas. */
export async function getUbicaciones(todos = false): Promise<UbicacionDTO[]> {
  const query = todos ? "?todos=1" : "";
  const response = await fetchBackend(`/api/ubicaciones${query}`, { method: "GET" }, TIMEOUT_CONFIG);
  const body = (await response.json()) as { ubicaciones: UbicacionDTO[] };
  return body.ubicaciones;
}

/** Crea una ubicación nueva. POST /api/ubicaciones. */
export async function createUbicacion(datos: UbicacionCrear): Promise<UbicacionDTO> {
  const response = await fetchBackend(
    "/api/ubicaciones",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as { ubicacion: UbicacionDTO };
  return body.ubicacion;
}

/** Edita campos de una ubicación (solo los incluidos). PUT /api/ubicaciones/{id}. */
export async function updateUbicacion(
  id: string,
  cambios: Partial<Omit<UbicacionDTO, "id">>,
): Promise<UbicacionDTO> {
  const response = await fetchBackend(
    `/api/ubicaciones/${id}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cambios),
    },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as { ubicacion: UbicacionDTO };
  return body.ubicacion;
}

/** Borra una ubicación del catálogo. DELETE /api/ubicaciones/{id}. */
export async function deleteUbicacion(id: string): Promise<void> {
  await fetchBackend(`/api/ubicaciones/${id}`, { method: "DELETE" }, TIMEOUT_CONFIG);
}

// ---------------------------------------------------------------------------
// Configuración · Admin (Hito 7): PIN de adulto + import/export.
// ---------------------------------------------------------------------------

/** ¿Hay PIN configurado? ¿La sesión (token) sigue activa? GET /api/admin/status. */
export async function adminStatus(): Promise<AdminStatus> {
  const response = await fetchBackend("/api/admin/status", { method: "GET" }, TIMEOUT_CONFIG);
  return (await response.json()) as AdminStatus;
}

async function _postPin(path: string, pin: string): Promise<void> {
  const response = await fetchBackend(
    path,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pin }) },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as { token: string };
  setAdminToken(body.token); // guarda el token y lo aplica a las siguientes peticiones
}

/** Crea el PIN por primera vez (auto-login). POST /api/admin/setup. */
export async function adminSetup(pin: string): Promise<void> {
  await _postPin("/api/admin/setup", pin);
}

/** Inicia sesión con el PIN. POST /api/admin/login. */
export async function adminLogin(pin: string): Promise<void> {
  await _postPin("/api/admin/login", pin);
}

/** Cierra la sesión (invalida el token en el backend y lo olvida aquí). */
export async function adminLogout(): Promise<void> {
  try {
    await fetchBackend("/api/admin/logout", { method: "POST" }, TIMEOUT_CONFIG);
  } finally {
    setAdminToken(null);
  }
}

/** Cambia el PIN (requiere el actual). POST /api/admin/change. */
export async function adminChangePin(pinActual: string, pinNuevo: string): Promise<void> {
  await fetchBackend(
    "/api/admin/change",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin_actual: pinActual, pin_nuevo: pinNuevo }),
    },
    TIMEOUT_CONFIG,
  );
}

/** Descarga la configuración completa (sin secretos). GET /api/admin/export. */
export async function adminExport(): Promise<ConfigExport> {
  const response = await fetchBackend("/api/admin/export", { method: "GET" }, TIMEOUT_CONFIG);
  return (await response.json()) as ConfigExport;
}

/** Restaura una configuración (con copia de seguridad previa). POST /api/admin/import. */
export async function adminImport(datos: unknown): Promise<ImportResult> {
  const response = await fetchBackend(
    "/api/admin/import",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ datos }) },
    TIMEOUT_DOCS,
  );
  return (await response.json()) as ImportResult;
}

// ---------------------------------------------------------------------------
// Familias (Hito 9.2): cuentas (email + contraseña) + sesión persistente.
// La sesión gatea el uso de la app; el token se guarda en localStorage.
// ---------------------------------------------------------------------------

/** ¿Hay ya alguna familia registrada? (alta vs login en el primer arranque). */
export async function familiaEstado(): Promise<FamiliasEstado> {
  const response = await fetchBackend("/api/familias/estado", { method: "GET" }, TIMEOUT_CONFIG);
  return (await response.json()) as FamiliasEstado;
}

/** ¿Hay sesión de familia válida? Devuelve los datos de la familia o autenticada=false. */
export async function familiaMe(): Promise<FamiliaSesion> {
  const response = await fetchBackend("/api/familias/me", { method: "GET" }, TIMEOUT_CONFIG);
  return (await response.json()) as FamiliaSesion;
}

/** POST que devuelve un token de sesión (login/verificar): lo guarda y lo aplica. */
async function _postFamiliaAuth(
  path: string,
  cuerpo: Record<string, string>,
): Promise<FamiliaAuthResponse> {
  const response = await fetchBackend(
    path,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as FamiliaAuthResponse;
  setFamilyToken(body.token); // guarda el token y lo aplica a las siguientes peticiones
  return body;
}

/**
 * Alta de una familia. POST /api/familias/signup.
 * Sin verificación de correo: la respuesta trae `token` (se guarda) y `familia`.
 * Con verificación: `verificacion_requerida=true` y NO hay token todavía (hay que
 * llamar a `familiaVerificar` con el código).
 */
export async function familiaSignup(
  email: string,
  password: string,
  nombreFamilia: string,
): Promise<FamiliaSignupResponse> {
  const response = await fetchBackend(
    "/api/familias/signup",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, nombre_familia: nombreFamilia }),
    },
    TIMEOUT_CONFIG,
  );
  const body = (await response.json()) as FamiliaSignupResponse;
  if (body.token) setFamilyToken(body.token); // solo hay token si no hacía falta verificar
  return body;
}

/** Verifica el código (OTP) de un alta pendiente y abre sesión. POST /api/familias/verificar. */
export async function familiaVerificar(
  email: string,
  codigo: string,
): Promise<FamiliaAuthResponse> {
  return _postFamiliaAuth("/api/familias/verificar", { email, codigo });
}

/** Reenvía el código de verificación. POST /api/familias/reenviar. */
export async function familiaReenviar(email: string): Promise<FamiliaReenviarResponse> {
  const response = await fetchBackend(
    "/api/familias/reenviar",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) },
    TIMEOUT_CONFIG,
  );
  return (await response.json()) as FamiliaReenviarResponse;
}

/** Inicia sesión de familia. POST /api/familias/login. */
export async function familiaLogin(
  email: string,
  password: string,
): Promise<FamiliaAuthResponse> {
  return _postFamiliaAuth("/api/familias/login", { email, password });
}

/** Cierra la sesión de familia (invalida el token en el backend y lo olvida aquí). */
export async function familiaLogout(): Promise<void> {
  try {
    await fetchBackend("/api/familias/logout", { method: "POST" }, TIMEOUT_CONFIG);
  } finally {
    setFamilyToken(null);
  }
}
