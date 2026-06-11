import { describe, it, expect } from "vitest";
import {
	evaluateAlertTts,
	evaluateAdviceTts,
	evaluateCommentaryTts,
} from "../services/ttsPlaybackGate";
import {
	VOICE_CONTRACT_ALERT_CASES,
	VOICE_CONTRACT_ADVICE_CASES,
	VOICE_CONTRACT_COMMENTARY_CASES,
} from "./fixtures/voiceContractCases";
import { SPOTTER_VOICE_CATEGORIES } from "../services/alertVoice";

describe("voice contract — alerts (VC-A*)", () => {
	it.each(
		VOICE_CONTRACT_ALERT_CASES,
	)("$id allow=$expectAllow reason=$expectReason", (row) => {
		const decision = evaluateAlertTts({
			message: row.message,
			payload: row.payload,
			speakOnlyWhenSpokenTo: row.speakOnly,
			spotterEnabled: row.spotterEnabled,
			engineerEnabled: row.engineerEnabled,
		});
		expect(decision.allow).toBe(row.expectAllow);
		expect(decision.reason).toBe(row.expectReason);
	});
});

describe("voice contract — advice (VC-P*)", () => {
	it.each(
		VOICE_CONTRACT_ADVICE_CASES.filter((c) => c.event === "advice_end"),
	)("$id allow=$expectAllow reason=$expectReason", (row) => {
		const decision = evaluateAdviceTts({
			fullText: row.fullText,
			speakOnlyWhenSpokenTo: row.speakOnly,
			inReconnectGrace: row.expectReason === "reconnect_grace",
		});
		expect(decision.allow).toBe(row.expectAllow);
		expect(decision.reason).toBe(row.expectReason);
	});
});

describe("voice contract — commentary (VC-C*)", () => {
	it.each(
		VOICE_CONTRACT_COMMENTARY_CASES,
	)("$id allow=$expectAllow reason=$expectReason", (row) => {
		const decision = evaluateCommentaryTts({
			fullText: "Traffic ahead",
			speakOnlyWhenSpokenTo: row.speakOnly,
			engineerEnabled: row.engineerEnabled,
		});
		expect(decision.allow).toBe(row.expectAllow);
		expect(decision.reason).toBe(row.expectReason);
	});
});

describe("invariant I3: spotter categories bypass speakOnly", () => {
	it("all spotter categories are in SPOTTER_VOICE_CATEGORIES", () => {
		for (const cat of [
			"proximity",
			"fuel",
			"pit_limiter",
			"safety_car",
			"damage",
			"puncture",
			"impact",
		]) {
			expect(SPOTTER_VOICE_CATEGORIES.has(cat)).toBe(true);
		}
	});

	it("speakOnly + spotter ON + proximity → allowed (VC-A03)", () => {
		const d = evaluateAlertTts({
			message: "Coche a la derecha",
			payload: {
				category: "proximity",
				severity: "INFO",
				audio_priority: "2",
				service: "spotter",
			},
			speakOnlyWhenSpokenTo: true,
			spotterEnabled: true,
			engineerEnabled: false,
		});
		expect(d.allow).toBe(true);
	});
});

describe("invariant I6: voiceBackendPlayback silences frontend alert TTS (VC-A06)", () => {
	it("VC-A06: backend_playback denies all alert categories", () => {
		for (const cat of ["proximity", "fuel", "engineer"]) {
			const d = evaluateAlertTts({
				message: "test",
				payload: {
					category: cat,
					service: cat === "proximity" ? "spotter" : "engineer",
				},
				speakOnlyWhenSpokenTo: false,
				spotterEnabled: true,
				engineerEnabled: true,
				voiceBackendPlayback: true,
			});
			expect(d.allow).toBe(false);
			expect(d.reason).toBe("backend_playback");
		}
	});

	it("advice_end commentary_end NOT affected by voiceBackendPlayback", () => {
		const ad = evaluateAdviceTts({
			fullText: "test",
			speakOnlyWhenSpokenTo: false,
		});
		const cd = evaluateCommentaryTts({
			fullText: "test",
			speakOnlyWhenSpokenTo: false,
			engineerEnabled: true,
		});
		expect(ad.allow).toBe(true);
		expect(cd.allow).toBe(true);
	});
});

describe("invariant I2: voice_response always passes speakOnly", () => {
	it("VC-A05: speakOnly + voice_response + engineer OFF → allowed", () => {
		const d = evaluateAlertTts({
			message: "Afirmativo, recepción clara.",
			payload: {
				category: "voice_response",
				audio_priority: "4",
				service: "engineer",
				fast_command: true,
			},
			speakOnlyWhenSpokenTo: true,
			spotterEnabled: false,
			engineerEnabled: false,
		});
		expect(d.allow).toBe(true);
		expect(d.reason).toBe("ok");
	});

	it("VC-A13: voice_response no service field + all OFF → allowed", () => {
		const d = evaluateAlertTts({
			message: "Afirmativo",
			payload: { category: "voice_response", audio_priority: "4" },
			speakOnlyWhenSpokenTo: false,
			spotterEnabled: false,
			engineerEnabled: false,
		});
		expect(d.allow).toBe(true);
		expect(d.reason).toBe("ok");
	});
});
