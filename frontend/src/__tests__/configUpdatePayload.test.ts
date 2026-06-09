import { describe, it, expect } from "vitest";
import { buildConfigUpdatePayload } from "../services/configUpdatePayload";

describe("buildConfigUpdatePayload", () => {
  it("includes personality and spotter delays", () => {
    const p = buildConfigUpdatePayload({
      personalityProfileId: "aggressive",
      verbosityLevel: "detailed",
      spotterClearDelayS: 0.15,
      spotterOverlapDelayS: 2.0,
      spotterHoldRepeatS: 3.0,
      spotterGapFrequencyS: 40,
      spotterCarLengthM: 4.5,
      spotterMinSpeedMs: 10,
      spotterRaceStartDelayS: 20,
    } as any);
    expect(p.personalityProfileId).toBe("aggressive");
    expect(p.spotterClearDelayS).toBe(0.15);
    expect(p.spotterHoldRepeatS).toBe(3.0);
    expect(p.spotterCarLengthM).toBe(4.5);
    expect(p.spotterMinSpeedMs).toBe(10);
    expect(p.spotterRaceStartDelayS).toBe(20);
  });

  it("omits power toggles when not provided", () => {
    const p = buildConfigUpdatePayload({ personalityProfileId: "standard" } as any);
    expect(p.spotterEnabled).toBeUndefined();
    expect(p.engineerEnabled).toBeUndefined();
  });

  it("includes power toggles when boolean", () => {
    const p = buildConfigUpdatePayload({
      spotterEnabled: true,
      engineerEnabled: false,
    } as any);
    expect(p.spotterEnabled).toBe(true);
    expect(p.engineerEnabled).toBe(false);
  });
});
