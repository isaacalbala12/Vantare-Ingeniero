import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { expiresAtFromPayload, isExpiredAt } from "../services/alertExpiry";

describe("alertExpiry", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-07T12:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("reads nested payload.ttl_ms from Crew Chief alerts", () => {
    const expiresAt = expiresAtFromPayload({
      message: "Subiste a P3.",
      ttl: 5,
      payload: { ttl_ms: 5000, event_id: "overtake_position_gain" },
    });
    expect(expiresAt).toBe(Date.now() + 5000);
  });

  it("falls back to top-level ttl in seconds", () => {
    const expiresAt = expiresAtFromPayload({
      message: "FCY.",
      ttl: 12,
      payload: { event_id: "fcy_pits_closed" },
    });
    expect(expiresAt).toBe(Date.now() + 12000);
  });

  it("isExpiredAt compares against wall clock", () => {
    const future = Date.now() + 1000;
    expect(isExpiredAt(future)).toBe(false);
    expect(isExpiredAt(Date.now() - 1)).toBe(true);
    expect(isExpiredAt(undefined)).toBe(false);
  });

  it("spotter clear uses 2s expiry", () => {
    const expiresAt = expiresAtFromPayload({
      category: "proximity",
      ttl: 2,
      payload: { ttl_ms: 2000, event_id: "spotter_clear_left" },
    });
    expect(expiresAt).toBe(Date.now() + 2000);
  });
});
