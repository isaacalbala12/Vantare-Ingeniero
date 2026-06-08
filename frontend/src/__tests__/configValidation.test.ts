import { describe, it, expect } from "vitest";
import { validateSpotterFields } from "../hub/forms/configValidation";

describe("validateSpotterFields", () => {
  it("rejects clear delay below 0.1", () => {
    expect(
      validateSpotterFields({
        spotterClearDelayS: 0.05,
        spotterHoldRepeatS: 3,
        spotterGapFrequencyS: 30,
        spotterCarLengthM: 4.5,
        spotterMinSpeedMs: 10,
        spotterRaceStartDelayS: 20,
        ttsVolumeBoost: 1,
      }).ok,
    ).toBe(false);
  });

  it("accepts valid defaults", () => {
    expect(
      validateSpotterFields({
        spotterClearDelayS: 0.15,
        spotterHoldRepeatS: 3,
        spotterGapFrequencyS: 30,
        spotterCarLengthM: 4.5,
        spotterMinSpeedMs: 10,
        spotterRaceStartDelayS: 20,
        ttsVolumeBoost: 1,
      }).ok,
    ).toBe(true);
  });
});
