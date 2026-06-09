import { SPOTTER_PREFETCH_PHRASES } from "./spotterPhrases";

const PROFILE_EXTRA: Record<string, string[]> = {
  aggressive: ["¡Aguanta! Coche por derecha.", "¡Viene muy rápido por izquierda!"],
  formal: ["Mantenga la trayectoria, vehículo por derecha.", "Aproximación rápida por izquierda."],
};

export function spotterPrefetchPhrases(profileId: string): string[] {
  const extras = PROFILE_EXTRA[profileId] ?? [];
  return [...SPOTTER_PREFETCH_PHRASES, ...extras];
}
