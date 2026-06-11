// Ring buffer for TTS decision diagnostics (max 50 entries)
// Phase 6 observability — docs/voice-contract.md §7

export type TtsDecisionRecord = {
  ts: number;
  source: string;
  allow: boolean;
  reason: string;
  category?: string;
};

const MAX_BUFFER = 50;
const buffer: TtsDecisionRecord[] = [];

export function recordTtsDecision(row: Omit<TtsDecisionRecord, "ts">): void {
  buffer.unshift({ ...row, ts: Date.now() });
  if (buffer.length > MAX_BUFFER) buffer.length = MAX_BUFFER;
  if (import.meta.env?.VITE_TTS_DEBUG === "1") {
    console.warn("[TTS]", row);
  }
}

export function getTtsDiagnostics(): ReadonlyArray<TtsDecisionRecord> {
  return buffer;
}

export function clearTtsDiagnostics(): void {
  buffer.length = 0;
}
