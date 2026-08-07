/**
 * src/api/types.ts — Contrato de la API (tipos), AUTOGENERADO desde el backend
 * ============================================================================
 *
 * Estos tipos ya NO se escriben a mano: son alias sobre `schema.d.ts`, que se
 * genera del esquema OpenAPI del backend (sus `response_model`/schemas Pydantic).
 * Para regenerar tras cambiar un schema del backend:
 *
 *     uv run python -m scripts.gen_types
 *
 * Este archivo solo re-exporta los tipos generados con nombres estables y cómodos,
 * para que el resto del frontend importe `PersonajeDTO`, `AskResponse`, etc. sin
 * conocer la forma `components["schemas"][...]`. Si añades un endpoint con un nuevo
 * `response_model`, regenera y añade aquí su alias.
 */

import type { components } from "./schema";

type Schemas = components["schemas"];

// --- Generación de imagen ---
export type GenerateRequest = Schemas["GenerateRequest"];
export type GenerateResponse = Schemas["GenerateResponse"];

// --- Chat (RAG) ---
export type AskRequest = Schemas["AskRequest"];
export type AskResponse = Schemas["AskResponse"];

// --- Voz ---
export type TranscribeResponse = Schemas["TranscribeResponse"];

// --- APIs (secretos) ---
export type ApiProviderStatus = Schemas["ApiProviderStatus"];
export type ApiTestResult = Schemas["ApiTestResult"];
export type ApiSaldoResult = Schemas["ApiSaldoResult"];
export type SaldoMedida = Schemas["SaldoMedida"];

// --- Configuración (ajustes en caliente) ---
export type SettingMeta = Schemas["SettingMeta"];
export type ConfigResponse = Schemas["ConfigResponse"];
export type ConfigSaveResult = Schemas["ConfigSaveResult"];

// --- Personajes ---
export type PersonajeDTO = Schemas["PersonajeDTO"];
export type PersonajesInfo = Schemas["PersonajesInfo"];
export type PersonajeCrear = Schemas["PersonajeCrear"];

// --- Voces ---
export type VozDTO = Schemas["VozDTO"];
export type VocesResponse = Schemas["VocesResponse"];

// --- Documentos del RAG ---
export type DocumentoDTO = Schemas["DocumentoDTO"];
export type DocumentoContenido = Schemas["DocumentoContenido"];
/** Subida múltiple (mejor esfuerzo): documentos subidos + errores por fichero. */
export type SubidaMultipleResult = {
  documentos: DocumentoDTO[];
  errores: Schemas["ErrorNombre"][];
};
/** Copia de un documento a uno o varios personajes (mejor esfuerzo por destino). */
export type CopiaResult = Schemas["CopiaResponse"];
export type ReindexResult = Schemas["ReindexResult"];
export type ReindexEstado = Schemas["ReindexEstado"];

// --- Ubicaciones ---
export type UbicacionDTO = Schemas["UbicacionDTO"];
export type UbicacionCrear = Schemas["UbicacionCrear"];

// --- Admin (contraseña, 2FA, import/export) ---
export type AdminStatus = Schemas["AdminStatus"];
export type AdminLoginResponse = Schemas["AdminLoginResponse"];
export type Admin2FAEnrol = Schemas["Admin2FAEnrol"];
export type Admin2FARecovery = Schemas["Admin2FARecovery"];
export type ConfigExport = Schemas["ConfigExport"];
export type ImportResult = Schemas["ImportResult"];

// --- Familias (cuentas + sesión, Hito 9.2) ---
export type FamiliaDTO = Schemas["FamiliaDTO"];
export type NinoDTO = Schemas["NinoDTO"];
export type FamiliaSesion = Schemas["FamiliaSesion"];
export type FamiliaAuthResponse = Schemas["FamiliaAuthResponse"];
export type FamiliaSignupResponse = Schemas["FamiliaSignupResponse"];
export type FamiliaReenviarResponse = Schemas["FamiliaReenviarResponse"];
export type FamiliasEstado = Schemas["FamiliasEstado"];

// --- Auditoría de uso (informe para el adulto) ---
export type AuditoriaEvento = Schemas["AuditoriaEvento"];
export type AuditoriaLista = Schemas["AuditoriaLista"];

// --- Salud ---
export type HealthResponse = Schemas["HealthResponse"];
