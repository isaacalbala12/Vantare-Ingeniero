import { describe, it, expect } from "vitest";
import { evaluateAlertTts, shouldDiscardTtsPlayback } from "../services/ttsPlaybackGate";

describe("VC-P06 voice_response passes all gates with release defaults", () => {
  it("allows PTT fast response when engineer and spotter off", () => {
    const decision = evaluateAlertTts({
      message: "Afirmativo, recepción clara.",
      payload: {
        category: "voice_response",
        audio_priority: "4",
        service: "engineer",
        fast_command: true,
      },
      speakOnlyWhenSpokenTo: true,
      spotterEnabled: false,
      engineerEnabled: false,
    });
    expect(decision).toEqual({ allow: true, reason: "ok" });
  });

  it("allows PTT response even with all toggles off", () => {
    const decision = evaluateAlertTts({
      message: "Negativo, copia.",
      payload: {
        category: "voice_response",
        audio_priority: "4",
      },
      speakOnlyWhenSpokenTo: true,
      spotterEnabled: false,
      engineerEnabled: false,
    });
    expect(decision.allow).toBe(true);
  });
});

describe("VC-P07 LISTENING_PILOT discards playback not enqueue", () => {
  it("shouldDiscardTtsPlayback true only for LISTENING_PILOT", () => {
    expect(shouldDiscardTtsPlayback("LISTENING_PILOT")).toBe(true);
    expect(shouldDiscardTtsPlayback("THINKING_LLM")).toBe(false);
    expect(shouldDiscardTtsPlayback("SPEAKING_ENGINE")).toBe(false);
    expect(shouldDiscardTtsPlayback("IDLE")).toBe(false);
  });
});
