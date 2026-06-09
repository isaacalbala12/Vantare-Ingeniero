import { describe, it, expect } from "vitest";
import { classifyTtsPriority } from "../services/spotterPhrases";
import { shouldVoiceAlert } from "../services/alertVoice";

describe("spotter TTS priority", () => {
  it("proximity alert es IMMEDIATE", () => {
    const payload = {
      category: "proximity",
      severity: "INFO",
      audio_priority: "2",
      message: "Coche a la derecha",
    };
    expect(shouldVoiceAlert(payload)).toBe(true);
    expect(classifyTtsPriority(payload.message, payload)).toBe("IMMEDIATE");
  });

  it("advice LLM es NORMAL", () => {
    const text = "Tu combustible está bien, mantén el ritmo.";
    expect(classifyTtsPriority(text, { category: "advice" })).toBe("NORMAL");
  });

  it("limiter es IMMEDIATE", () => {
    expect(
      classifyTtsPriority("Pit limiter no activado al entrar en boxes.", {
        category: "limiter",
        severity: "CRITICAL",
        audio_priority: "4",
      }),
    ).toBe("IMMEDIATE");
  });

  it("gaps no tienen voz", () => {
    expect(
      shouldVoiceAlert({
        category: "gaps",
        severity: "INFO",
        audio_priority: "1",
      }),
    ).toBe(false);
  });
});
