import { describe, expect, it } from "vitest";
import { evaluateAlertTts } from "../services/ttsPlaybackGate";

describe("evaluateAlertTts voiceBackendPlayback", () => {
	it("denies alert TTS when backend owns playback", () => {
		const d = evaluateAlertTts({
			message: "Coche a la izquierda",
			payload: { category: "proximity", audio_priority: "2", severity: "INFO" },
			speakOnlyWhenSpokenTo: false,
			spotterEnabled: true,
			engineerEnabled: true,
			voiceBackendPlayback: true,
		});
		expect(d.allow).toBe(false);
		expect(d.reason).toBe("backend_playback");
	});

	it("allows alert TTS when flag false", () => {
		const d = evaluateAlertTts({
			message: "Coche a la izquierda",
			payload: { category: "proximity", audio_priority: "2", severity: "INFO" },
			speakOnlyWhenSpokenTo: false,
			spotterEnabled: true,
			engineerEnabled: true,
			voiceBackendPlayback: false,
		});
		expect(d.allow).toBe(true);
	});
});
