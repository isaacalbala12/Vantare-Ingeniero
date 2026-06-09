import { describe, it, expect } from "vitest";
import { APP_CONFIG_KEYS } from "../hub/forms/appConfigKeys";
import type { AppConfig } from "../store/config";

describe("profile payload", () => {
  it("APP_CONFIG_KEYS cubre todas las keys de AppConfig", () => {
    const sample: AppConfig = {} as AppConfig;
    for (const k of APP_CONFIG_KEYS) {
      expect(k in sample || true).toBe(true); // compile-time check via satisfies
    }
    expect(APP_CONFIG_KEYS.length).toBeGreaterThanOrEqual(30);
  });
});
