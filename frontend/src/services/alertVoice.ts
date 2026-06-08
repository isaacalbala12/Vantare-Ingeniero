/** Bloquea TTS proactivo cuando el piloto pidió silencio ("cállate"); solo voice_response y advice PTT. */
export function shouldVoiceDuringSpeakOnly(
  speakOnly: boolean,
  category: string,
  source: "alert" | "advice" | "commentary" = "alert",
): boolean {
  if (!speakOnly) {
    return true;
  }
  if (source === "advice") {
    return true;
  }
  if (source === "commentary") {
    return false;
  }
  return category === "voice_response";
}
const NAMED_VOICE_PRIORITIES = new Set(["CRITICAL", "HIGH", "WARNING"]);
/** Solo alertas sin voz por diseño (gaps = visual; system/spotter = interno o UI-only). Perlas audibles en A2. */
const NO_VOICE_CATEGORIES = new Set(["gaps", "system", "spotter"]);

/**
 * El spotter usa audio_priority numérico (1–4); los triggers usan nombres (CRITICAL, HIGH…).
 * 4 = CRITICAL, 3 = WARNING, 2 = proximidad/última vuelta, 1 = gaps INFO (solo visual, sin voz).
 */
export function shouldVoiceAlert(payload: Record<string, unknown>): boolean {
  const category = String(payload.category || "").toLowerCase();
  if (NO_VOICE_CATEGORIES.has(category)) {
    return false;
  }

  const severity = String(payload.severity || "").toUpperCase();
  if (NAMED_VOICE_PRIORITIES.has(severity)) {
    return true;
  }

  const raw = payload.audio_priority;
  const asNum = typeof raw === "number" ? raw : parseInt(String(raw ?? ""), 10);
  if (!Number.isNaN(asNum)) {
    return asNum >= 2;
  }

  const named = String(raw || "").toUpperCase();
  return NAMED_VOICE_PRIORITIES.has(named);
}
