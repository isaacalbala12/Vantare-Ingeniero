import { describe, it, expect } from "vitest";
import { shouldVoiceAlert, shouldVoiceDuringSpeakOnly } from "../services/alertVoice";

describe("shouldVoiceDuringSpeakOnly", () => {
  it("bloquea alertas proactivas salvo voice_response", () => {
    expect(shouldVoiceDuringSpeakOnly(true, "proximity", "alert")).toBe(false);
    expect(shouldVoiceDuringSpeakOnly(true, "engineer", "alert")).toBe(false);
    expect(shouldVoiceDuringSpeakOnly(true, "voice_response", "alert")).toBe(true);
    expect(shouldVoiceDuringSpeakOnly(true, "advice", "advice")).toBe(true);
    expect(shouldVoiceDuringSpeakOnly(true, "commentary", "commentary")).toBe(false);
    expect(shouldVoiceDuringSpeakOnly(false, "proximity", "alert")).toBe(true);
  });
});

describe("shouldVoiceAlert", () => {
  it("voz por severity CRITICAL/WARNING del spotter", () => {
    expect(shouldVoiceAlert({ severity: "CRITICAL", audio_priority: "4" })).toBe(true);
    expect(shouldVoiceAlert({ severity: "WARNING", audio_priority: "3" })).toBe(true);
  });

  it("voz por audio_priority numérico >= 2 (proximidad)", () => {
    expect(shouldVoiceAlert({ severity: "INFO", audio_priority: "2" })).toBe(true);
    expect(
      shouldVoiceAlert({
        category: "proximity",
        severity: "INFO",
        audio_priority: "2",
        message: "Hypercar doblando por la derecha",
      }),
    ).toBe(true);
  });

  it("sin voz para gaps INFO priority 1", () => {
    expect(shouldVoiceAlert({ severity: "INFO", audio_priority: "1" })).toBe(false);
  });

  it("voz por nombre CRITICAL/HIGH en triggers", () => {
    expect(shouldVoiceAlert({ audio_priority: "CRITICAL", severity: "CRITICAL" })).toBe(true);
    expect(shouldVoiceAlert({ audio_priority: "HIGH", severity: "HIGH" })).toBe(true);
  });

  it("sin voz solo para system y spotter; pearl audible con priority >= 2", () => {
    expect(shouldVoiceAlert({ category: "system", severity: "CRITICAL", audio_priority: "CRITICAL" })).toBe(false);
    expect(
      shouldVoiceAlert({
        category: "spotter",
        severity: "INFO",
        audio_priority: "1",
        message: "Spotter activado.",
      }),
    ).toBe(false);
    expect(shouldVoiceAlert({ category: "pearl", severity: "INFO", audio_priority: "2" })).toBe(true);
    expect(shouldVoiceAlert({ category: "pearl", severity: "INFO", audio_priority: "1" })).toBe(false);
  });
});
