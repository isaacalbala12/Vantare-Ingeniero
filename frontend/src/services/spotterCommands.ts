/** Comandos de voz directos al spotter (sin pasar por el LLM). */

export type SpotterCommandAction = "enable" | "disable";

const ENABLE_PATTERNS = [
  /^spot$/i,
  /^espiar$/i,
  /^activa(r)? el spotter$/i,
  /^modo spotter$/i,
];

const DISABLE_PATTERNS = [
  /^don'?t spot$/i,
  /^deja de espiar$/i,
  /^para(r)? el spotter$/i,
  /^silencio spotter$/i,
  /^spotter off$/i,
];

export function parseSpotterCommand(text: string): SpotterCommandAction | null {
  const normalized = text.trim().toLowerCase();
  if (!normalized) return null;
  if (ENABLE_PATTERNS.some((re) => re.test(normalized))) return "enable";
  if (DISABLE_PATTERNS.some((re) => re.test(normalized))) return "disable";
  return null;
}
