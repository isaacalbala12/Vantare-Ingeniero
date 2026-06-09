import { describe, it, expect } from "vitest";
import { migrateTtsVolumePercent, volumePercentToAudioLevel } from "../hub/forms/volumeMigration";

describe("volumeMigration", () => {
  it("migra legacy boost 1.0 a 100", () => {
    expect(migrateTtsVolumePercent(1.0)).toBe(100);
    expect(migrateTtsVolumePercent(0.5)).toBe(50);
  });

  it("deja percent 0-100 intacto", () => {
    expect(migrateTtsVolumePercent(75)).toBe(75);
    expect(migrateTtsVolumePercent(0)).toBe(0);
  });

  it("convierte a audio.volume 0-1", () => {
    expect(volumePercentToAudioLevel(100)).toBe(1);
    expect(volumePercentToAudioLevel(50)).toBe(0.5);
    expect(volumePercentToAudioLevel(0)).toBe(0);
  });
});
