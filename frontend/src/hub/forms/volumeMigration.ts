/** Convierte valor persistido (legacy 0.5–2.0 o nuevo 0–100) a percent entero. */
export function migrateTtsVolumePercent(raw: unknown): number {
  const n = Number(raw ?? 100);
  if (!Number.isFinite(n)) return 100;
  if (n > 0 && n <= 2) return Math.min(100, Math.max(0, Math.round(n * 100)));
  return Math.min(100, Math.max(0, Math.round(n)));
}

export function volumePercentToAudioLevel(percent: number): number {
  const p = Math.min(100, Math.max(0, Math.round(percent)));
  return p / 100;
}
