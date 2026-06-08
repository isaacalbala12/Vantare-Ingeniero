/** Frases spotter / urgentes — prioridad IMMEDIATE y normalización para cache TTS. */

export type TtsPriority = "IMMEDIATE" | "NORMAL";

const IMMEDIATE_PATTERNS: RegExp[] = [
  /^coche a la (izquierda|derecha)$/i,
  /^despejado (izquierda|derecha)$/i,
  /^tres coches de ancho$/i,
  /mant[eé]n la l[ií]nea/i,
  /viene r[aá]pido por/i,
  /hypercar/i,
  /doblando por la (izquierda|derecha)$/i,
  /adelantando por la (izquierda|derecha)$/i,
  /pit limiter/i,
  /combustible cr[ií]tico/i,
  /safety car/i,
  /fcy activo/i,
  /última vuelta/i,
];

export const SPOTTER_PREFETCH_PHRASES: string[] = [
  "Coche a la izquierda",
  "Coche a la derecha",
  "Hypercar doblando por la derecha",
  "GT3 adelantando por la izquierda",
  "Despejado izquierda",
  "Despejado derecha",
  "Tres coches de ancho",
  "Mantén la línea, coche por derecha.",
  "¡Viene rápido por izquierda!",
  "Pit limiter no activado al entrar en boxes.",
  "Pit limiter no desactivado al salir de boxes.",
  "¡Combustible crítico! Menos de 1 vuelta restante.",
  "Safety car desplegado / FCY activo en pista.",
  "¡Última vuelta de la carrera!",
  "Daños detectados en el monoplaza.",
];

export function normalizeTtsText(text: string): string {
  return text.trim().replace(/\s+/g, " ");
}

export function classifyTtsPriority(
  text: string,
  payload?: Record<string, unknown>,
): TtsPriority {
  const category = String(payload?.category || "").toLowerCase();
  const severity = String(payload?.severity || "").toUpperCase();
  const audioPriority = payload?.audio_priority;
  const asNum =
    typeof audioPriority === "number"
      ? audioPriority
      : parseInt(String(audioPriority ?? ""), 10);

  if (category === "proximity" || category === "limiter" || category === "fuel" || category === "safety_car") {
    return "IMMEDIATE";
  }
  if (severity === "CRITICAL" || severity === "HIGH") {
    return "IMMEDIATE";
  }
  if (!Number.isNaN(asNum) && asNum >= 3) {
    return "IMMEDIATE";
  }

  const normalized = normalizeTtsText(text);
  if (IMMEDIATE_PATTERNS.some((re) => re.test(normalized))) {
    return "IMMEDIATE";
  }
  return "NORMAL";
}
