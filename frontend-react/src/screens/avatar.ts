/**
 * avatar.ts — Emoji de avatar del niño según su sexo (Hito 9.2c)
 * ==============================================================
 *
 * Pequeño ayudante compartido por "¿Quién juega?" y el editor de perfil, para que el
 * avatar del niño sea coherente en toda la app. Va en su propio módulo (no exportado
 * desde un componente) para no romper el fast-refresh de Vite.
 */

/** Emoji de avatar según el sexo ('chico' / 'chica' / '' sin especificar). */
export function avatarNino(sexo: string): string {
  return sexo === "chico" ? "👦" : sexo === "chica" ? "👧" : "🧒";
}
