import { describe, it, expect, beforeEach } from "vitest";
import { recordTtsDecision, getTtsDiagnostics, clearTtsDiagnostics } from "../services/ttsDiagnostics";

describe("ttsDiagnostics", () => {
  beforeEach(() => {
    clearTtsDiagnostics();
  });

  it("records decisions and returns them", () => {
    recordTtsDecision({ source: "alert", allow: false, reason: "service_toggle_off", category: "proximity" });
    const rows = getTtsDiagnostics();
    expect(rows).toHaveLength(1);
    expect(rows[0].reason).toBe("service_toggle_off");
    expect(rows[0].allow).toBe(false);
    expect(rows[0].source).toBe("alert");
    expect(rows[0].category).toBe("proximity");
    expect(rows[0].ts).toBeGreaterThan(0);
  });

  it("limits buffer to 50 entries", () => {
    for (let i = 0; i < 60; i++) {
      recordTtsDecision({ source: "test", allow: true, reason: "ok" });
    }
    expect(getTtsDiagnostics()).toHaveLength(50);
    // Most recent first
    expect(getTtsDiagnostics()[0].reason).toBe("ok");
  });

  it("clears buffer", () => {
    recordTtsDecision({ source: "test", allow: true, reason: "ok" });
    clearTtsDiagnostics();
    expect(getTtsDiagnostics()).toHaveLength(0);
  });

  it("records multiple sources", () => {
    recordTtsDecision({ source: "alert", allow: true, reason: "ok" });
    recordTtsDecision({ source: "advice", allow: false, reason: "empty_message" });
    recordTtsDecision({ source: "commentary", allow: false, reason: "engineer_disabled" });
    const rows = getTtsDiagnostics();
    expect(rows).toHaveLength(3);
    expect(rows[0].source).toBe("commentary"); // most recent first
    expect(rows[1].source).toBe("advice");
    expect(rows[2].source).toBe("alert");
  });
});
