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
  AskRequest,
  AskResponse,
  GenerateRequest,
  GenerateResponse,
  HealthResponse,
  TranscribeResponse,
} from "./types";

// URL del backend. Vacía = mismo origen (en dev, el proxy de vite.config.ts
// redirige /api y /health al backend local). Con Colab, se pone la del túnel
// en VITE_BACKEND_URL (ver .env.example).
const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL ?? "").replace(/\/+$/, "");

// Timeouts (ms), equivalentes a los del cliente Flet.
const TIMEOUT_HEALTH = 10_000;
const TIMEOUT_GENERATE = 120_000;
const TIMEOUT_GENERATE_ON_PHOTO = 180_000; // la edición (Kontext) tarda más que schnell
const TIMEOUT_ASK = 120_000;
const TIMEOUT_TRANSCRIBE = 60_000;

/** Error al comunicarnos con el backend (lo mostramos al usuario). */
export class BackendError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BackendError";
  }
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

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}${path}`, {
      ...options,
      signal: controller.signal,
    });
  } catch (exc) {
    if (exc instanceof DOMException && exc.name === "AbortError") {
      throw new BackendError(
        "El backend ha tardado demasiado en responder. Inténtalo de nuevo.",
      );
    }
    throw new BackendError(`Fallo de conexión con el backend: ${exc}`);
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
    throw new BackendError(
      `El backend devolvió un error: ${detail || `HTTP ${response.status}`}`,
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
