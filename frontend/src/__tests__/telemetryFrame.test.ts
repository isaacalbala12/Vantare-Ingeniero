import { describe, expect, it } from "vitest";
import { mapSidecarBinaryFrame } from "../services/telemetryFrame";

describe("mapSidecarBinaryFrame", () => {
  it("maps speed in m/s to km/h and preserves sidecar gear", () => {
    const mapped = mapSidecarBinaryFrame({
      speed: 27.8,
      gear: 3,
      lap_number: 12,
      standing_position: 4,
      fuel_in_tank: 54.25,
      tyre_wear_fl: 91.2,
      tyre_wear_fr: 90.6,
      tyre_wear_rl: 88.1,
      tyre_wear_rr: 87.9,
    });

    expect(mapped.speed).toBe(100);
    expect(mapped.gear).toBe(3);
    expect(mapped.lap).toBe(12);
    expect(mapped.position).toBe(4);
    expect(mapped.fuel).toBe(54.25);
    expect(mapped.tyreWear).toEqual({ fl: 91, fr: 91, rl: 88, rr: 88 });
  });

  it("defaults lap to 0 and gear to neutral when missing", () => {
    const mapped = mapSidecarBinaryFrame({
      speed: 0,
    });

    expect(mapped.lap).toBe(0);
    expect(mapped.gear).toBe(0);
    expect(mapped.speed).toBe(0);
  });

  it("keeps reverse gear and sanitizes non-finite gear", () => {
    const reverse = mapSidecarBinaryFrame({ speed: 5, gear: -1 });
    const invalid = mapSidecarBinaryFrame({ speed: 5, gear: Number.NaN });

    expect(reverse.gear).toBe(-1);
    expect(invalid.gear).toBe(0);
  });
});
