/**
 * Tests for frontend/src/services/msgpack.ts — MessagePack + Delta encoding.
 */
import { describe, it, expect } from "vitest";
import {
  encodeMsgpack,
  decodeMsgpack,
  computeDelta,
  SNAPSHOT_INTERVAL,
} from "../services/msgpack";

describe("encodeMsgpack / decodeMsgpack", () => {
  it("roundtrip: flat object survives encode→decode without loss", () => {
    const data = { fuel: 42.3, speed: 180, gear: 3, lap: 26 };
    const raw = encodeMsgpack(data);
    expect(raw).toBeInstanceOf(Uint8Array);
    const result = decodeMsgpack(raw);
    expect(result).toEqual(data);
  });

  it("roundtrip: nested object survives encode→decode", () => {
    const data = {
      player: { fuel: 42.3, lap: 26 },
      tyres: { wear: [72, 68, 65, 63] },
    };
    const raw = encodeMsgpack(data);
    const result = decodeMsgpack(raw);
    expect(result).toEqual(data);
  });

  it("roundtrip: empty object", () => {
    const data = {};
    const raw = encodeMsgpack(data);
    const result = decodeMsgpack(raw);
    expect(result).toEqual(data);
  });

  it("encode returns Uint8Array, not string", () => {
    const raw = encodeMsgpack({ x: 1 });
    expect(raw).toBeInstanceOf(Uint8Array);
    expect(typeof raw).not.toBe("string");
  });

  it("decode throws on invalid data", () => {
    const invalid = new Uint8Array([0xff, 0xfe, 0xfd, 0x00]);
    expect(() => decodeMsgpack(invalid)).toThrow();
  });
});

describe("computeDelta", () => {
  it("null previous → returns current with _full=true", () => {
    const current = { fuel: 42.3, speed: 180 };
    const delta = computeDelta(current, null);
    expect(delta._full).toBe(true);
    expect(delta._t).toBeTypeOf("number");
    expect(delta.fuel).toBe(42.3);
    expect(delta.speed).toBe(180);
  });

  it("identical frames → only _t in delta", () => {
    const frame = { fuel: 42.3, speed: 180, gear: 3 };
    const delta = computeDelta(frame, frame);
    expect(delta._t).toBeTypeOf("number");
    expect(delta).not.toHaveProperty("fuel");
    expect(delta).not.toHaveProperty("speed");
    expect(delta).not.toHaveProperty("gear");
  });

  it("only changed fields appear in delta", () => {
    const prev = { fuel: 42.3, speed: 180, gear: 3 };
    const curr = { fuel: 40.1, speed: 180, gear: 3 };
    const delta = computeDelta(curr, prev);
    expect(delta.fuel).toBe(40.1);
    expect(delta).not.toHaveProperty("speed");
    expect(delta).not.toHaveProperty("gear");
  });

  it("all fields changed → all appear", () => {
    const prev = { fuel: 42.3, speed: 180, gear: 3 };
    const curr = { fuel: 40.1, speed: 178, gear: 4 };
    const delta = computeDelta(curr, prev);
    expect(delta.fuel).toBe(40.1);
    expect(delta.speed).toBe(178);
    expect(delta.gear).toBe(4);
  });

  it("forceFull emits _full=true and all fields", () => {
    const prev = { fuel: 42.3, speed: 180 };
    const curr = { fuel: 42.3, speed: 180 };
    const delta = computeDelta(curr, prev, true);
    expect(delta._full).toBe(true);
    expect(delta.fuel).toBe(42.3);
    expect(delta.speed).toBe(180);
  });

  it("_t is a positive number", () => {
    const delta = computeDelta({ x: 1 }, null);
    expect(delta._t).toBeGreaterThan(0);
  });

  it("does not mutate input objects", () => {
    const prev = { fuel: 42.3 };
    const curr = { fuel: 40.1 };
    const delta = computeDelta(curr, prev);
    expect(prev.fuel).toBe(42.3);
    expect(curr.fuel).toBe(40.1);
    expect(delta).not.toBe(curr as unknown as typeof delta);
    expect(delta).not.toBe(prev as unknown as typeof delta);
  });
});

describe("SNAPSHOT_INTERVAL", () => {
  it("is 100 (every ~5s at 20Hz)", () => {
    expect(SNAPSHOT_INTERVAL).toBe(100);
  });
});
