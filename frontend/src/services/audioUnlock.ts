/** Desbloqueo de audio WebView2 — debe registrarse desde useAudioContext en App. */
let unlockFn: (() => Promise<void>) | null = null;

export function registerAudioUnlock(fn: () => Promise<void>): void {
  unlockFn = fn;
}

export async function ensureAudioUnlocked(): Promise<void> {
  if (unlockFn) {
    await unlockFn();
  }
}
