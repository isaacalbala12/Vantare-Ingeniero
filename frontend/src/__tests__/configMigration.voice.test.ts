import { describe, it, expect, beforeEach, vi } from "vitest";

describe("VC-R04 config v1 migrates speakOnly and wakeWord", () => {
	beforeEach(() => {
		localStorage.clear();
		vi.resetModules();
	});

	it("legacy config without configSchemaVersion gets speakOnly=true and wakeWord=false", async () => {
		// Set up legacy config (no configSchemaVersion field)
		localStorage.setItem(
			"vantare_config",
			JSON.stringify({
				vllmIP: "127.0.0.1",
				serverPort: 8008,
				// No configSchemaVersion — triggers legacy path
			}),
		);

		// Re-import to pick up localStorage
		const { useAppStore } = await import("../store/config");
		const cfg = useAppStore.getState().config;

		expect(cfg.speakOnlyWhenSpokenTo).toBe(true);
		expect(cfg.wakeWordEnabled).toBe(false);
		expect(cfg.spotterEnabled).toBe(true);
		expect(cfg.engineerEnabled).toBe(false);
		expect(cfg.spotterMinSpeedMs).toBe(5.0);
		expect(cfg.spotterRaceStartDelayS).toBe(3.0);
	});

	it("v2 config preserves user settings", async () => {
		localStorage.setItem(
			"vantare_config",
			JSON.stringify({
				configSchemaVersion: 2,
				vllmIP: "192.168.1.100",
				serverPort: 9000,
				speakOnlyWhenSpokenTo: false,
				wakeWordEnabled: true,
				spotterEnabled: true,
				engineerEnabled: true,
			}),
		);

		const { useAppStore } = await import("../store/config");
		const cfg = useAppStore.getState().config;

		expect(cfg.speakOnlyWhenSpokenTo).toBe(false);
		expect(cfg.wakeWordEnabled).toBe(true);
		expect(cfg.spotterEnabled).toBe(true);
		expect(cfg.engineerEnabled).toBe(true);
	});

	it("legacy config migrates and persists new version", async () => {
		localStorage.setItem(
			"vantare_config",
			JSON.stringify({
				vllmIP: "10.0.0.1",
				serverPort: 8008,
			}),
		);

		const { useAppStore } = await import("../store/config");
		const cfg = useAppStore.getState().config;

		// Verify migration happened
		expect(cfg.speakOnlyWhenSpokenTo).toBe(true);
		expect(cfg.wakeWordEnabled).toBe(false);

		// Verify localStorage was updated with new version
		const stored = JSON.parse(localStorage.getItem("vantare_config") ?? "{}");
    expect(stored.configSchemaVersion).toBe(6);
	});
});
