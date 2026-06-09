import { describe, it, expect } from "vitest";
import { shouldVoiceAlert } from "../services/alertVoice";
import { classifyTtsPriority } from "../services/spotterPhrases";
import {
  ALL_AUDIO_CONTRACT_ROWS,
  ALERT_ONLY_TRIGGER_ROWS,
  LLM_TRIGGER_SAMPLE_ROWS,
  SPOTTER_AUDIO_ROWS,
} from "./fixtures/audioTriggerMatrix";

const ALERT_ROWS = ALL_AUDIO_CONTRACT_ROWS.filter((r) => r.wsEvent === "alert");

function resolveAlertTtsPriority(row: (typeof ALL_AUDIO_CONTRACT_ROWS)[0]): string {
  return classifyTtsPriority(row.sampleMessage, {
    category: row.category,
    severity: row.severity,
    audio_priority: row.audioPriority,
  });
}

describe("audioTriggerMatrix — contrato voz/TTS", () => {
  it.each(ALERT_ROWS.map((r) => [r.id, r] as const))(
    "%s shouldVoiceAlert",
    (_id, row) => {
      expect(
        shouldVoiceAlert({
          category: row.category,
          severity: row.severity,
          audio_priority: row.audioPriority,
        }),
      ).toBe(row.expectVoice);
    },
  );

  it.each(
    ALERT_ROWS.filter((r) => r.expectTtsPriority !== "N/A").map(
      (r) => [r.id, r] as const,
    ),
  )("%s classifyTtsPriority (alert path)", (_id, row) => {
    expect(resolveAlertTtsPriority(row)).toBe(row.expectTtsPriority);
  });

  it("spotter urgente siempre IMMEDIATE", () => {
    for (const row of SPOTTER_AUDIO_ROWS.filter(
      (r) => r.expectVoice && r.source === "SpotterService",
    )) {
      expect(resolveAlertTtsPriority(row)).toBe("IMMEDIATE");
    }
  });

  it("triggers LLM siempre NORMAL en advice_end", () => {
    for (const row of LLM_TRIGGER_SAMPLE_ROWS) {
      expect(
        classifyTtsPriority(row.sampleMessage, { category: "advice" }),
      ).toBe("NORMAL");
    }
  });

  it("ALERT_ONLY triggers son IMMEDIATE cuando tienen voz", () => {
    for (const row of ALERT_ONLY_TRIGGER_ROWS) {
      expect(resolveAlertTtsPriority(row)).toBe("IMMEDIATE");
    }
  });

  it("advice path no usa shouldVoiceAlert", () => {
    const adviceRows = ALL_AUDIO_CONTRACT_ROWS.filter(
      (r) => r.wsEvent === "llm_pending+advice_*",
    );
    expect(adviceRows.length).toBeGreaterThan(0);
    for (const row of adviceRows) {
      expect(row.expectVoice).toBe(true);
    }
  });
});
