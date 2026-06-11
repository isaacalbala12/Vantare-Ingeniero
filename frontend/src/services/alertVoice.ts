/** Une campos anidados de AlertMessage.payload con el envelope WS para gates de voz. */
export function flattenAlertPayload(data: Record<string, unknown>): Record<string, unknown> {
  const inner = data.payload;
  if (inner && typeof inner === "object" && !Array.isArray(inner)) {
    return { ...(inner as Record<string, unknown>), ...data };
  }
  return data;
}

/** Bloquea TTS proactivo del ingeniero; spotter y respuestas PTT siguen audibles. */
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
  const cat = category.toLowerCase();
  if (cat === "voice_response") {
    return true;
  }
  if (SPOTTER_VOICE_CATEGORIES.has(cat)) {
    return true;
  }
  return false;
}
const NAMED_VOICE_PRIORITIES = new Set(["CRITICAL", "HIGH", "WARNING"]);
/** Solo alertas sin voz por diseño (gaps = visual; system/spotter = interno o UI-only). Perlas audibles en A2. */
const NO_VOICE_CATEGORIES = new Set(["gaps", "system", "spotter"]);

export const SPOTTER_VOICE_CATEGORIES = new Set([
  "proximity",
  "pit_limiter",
  "fuel",
  "safety_car",
  "damage",
  "puncture",
  "impact",
  "gaps",
]);

/** Respeta toggles ON/OFF de Inicio (defensa en profundidad; backend también filtra). */
export function shouldVoiceForServiceToggle(
  category: string,
  spotterEnabled: boolean,
  engineerEnabled: boolean,
  payload?: Record<string, unknown>,
): boolean {
  const cat = category.toLowerCase();
  if (cat === "voice_response") {
    return true;
  }
  const service = String(payload?.service ?? "").toLowerCase();
  if (service === "spotter") {
    return spotterEnabled;
  }
  if (service === "engineer") {
    return engineerEnabled;
  }
  if (SPOTTER_VOICE_CATEGORIES.has(cat)) {
    return spotterEnabled;
  }
  return engineerEnabled;
}

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
