import {
	flattenAlertPayload,
	shouldVoiceAlert,
	shouldVoiceDuringSpeakOnly,
	shouldVoiceForServiceToggle,
} from "./alertVoice";
import { isInternalRadioText } from "../hub/forms/telemetryFilters";
import { recordTtsDecision } from "./ttsDiagnostics";

export type TtsPlaybackDecision = {
	allow: boolean;
	reason: string;
};

function recordDeny(
	source: "alert" | "advice" | "commentary",
	reason: string,
	category = "",
): TtsPlaybackDecision {
	recordTtsDecision({ source, allow: false, reason, category });
	return { allow: false, reason };
}

/** Una sola puerta para alertas WS → TTS (facilita depuración). */
export function evaluateAlertTts(params: {
	message: string;
	payload: Record<string, unknown>;
	speakOnlyWhenSpokenTo: boolean;
	spotterEnabled: boolean;
	engineerEnabled: boolean;
	voiceBackendPlayback?: boolean;
}): TtsPlaybackDecision {
	const {
		message,
		payload,
		speakOnlyWhenSpokenTo,
		spotterEnabled,
		engineerEnabled,
		voiceBackendPlayback,
	} = params;

	if (voiceBackendPlayback) {
		return recordDeny(
			"alert",
			"backend_playback",
			String(payload?.category ?? ""),
		);
	}

	const trimmed = message.trim();
	const voicePayload = flattenAlertPayload(payload);
	const category = String(
		voicePayload.category || payload.category || "",
	).toLowerCase();

	if (!trimmed) {
		return recordDeny("alert", "empty_message", category);
	}
	if (isInternalRadioText(trimmed)) {
		return recordDeny("alert", "internal_radio_text", category);
	}
	if (!shouldVoiceAlert(voicePayload)) {
		return recordDeny("alert", "low_priority_or_no_voice_category", category);
	}
	if (!shouldVoiceDuringSpeakOnly(speakOnlyWhenSpokenTo, category, "alert")) {
		return recordDeny(
			"alert",
			"speak_only_blocks_proactive_engineer",
			category,
		);
	}
	if (
		!shouldVoiceForServiceToggle(
			category,
			spotterEnabled,
			engineerEnabled,
			voicePayload,
		)
	) {
		return recordDeny("alert", "service_toggle_off", category);
	}
	recordTtsDecision({ source: "alert", allow: true, reason: "ok", category });
	return { allow: true, reason: "ok" };
}

/** Puerta para advice_end (PTT respuesta del ingeniero). */
export function evaluateAdviceTts(params: {
	fullText: string;
	speakOnlyWhenSpokenTo: boolean;
	inReconnectGrace?: boolean;
}): TtsPlaybackDecision {
	const trimmed = params.fullText.trim();
	if (!trimmed) return recordDeny("advice", "empty_message");
	if (isInternalRadioText(trimmed))
		return recordDeny("advice", "internal_radio_text");
	if (params.inReconnectGrace) return recordDeny("advice", "reconnect_grace");
	if (
		!shouldVoiceDuringSpeakOnly(
			params.speakOnlyWhenSpokenTo,
			"advice",
			"advice",
		)
	) {
		return recordDeny("advice", "speak_only_blocks_advice");
	}
	recordTtsDecision({ source: "advice", allow: true, reason: "ok" });
	return { allow: true, reason: "ok" };
}

/** Puerta para commentary_end (ingeniero proactivo batch). */
export function evaluateCommentaryTts(params: {
	fullText: string;
	speakOnlyWhenSpokenTo: boolean;
	engineerEnabled: boolean;
	inReconnectGrace?: boolean;
}): TtsPlaybackDecision {
	const trimmed = params.fullText.trim();
	if (!trimmed) return recordDeny("commentary", "empty_message");
	if (isInternalRadioText(trimmed))
		return recordDeny("commentary", "internal_radio_text");
	if (params.inReconnectGrace)
		return recordDeny("commentary", "reconnect_grace");
	if (!params.engineerEnabled)
		return recordDeny("commentary", "engineer_disabled");
	if (
		!shouldVoiceDuringSpeakOnly(
			params.speakOnlyWhenSpokenTo,
			"commentary",
			"commentary",
		)
	) {
		return recordDeny("commentary", "speak_only_blocks_commentary");
	}
	recordTtsDecision({ source: "commentary", allow: true, reason: "ok" });
	return { allow: true, reason: "ok" };
}

/** Descarta playback de TTS cuando el piloto está en modo LISTENING_PILOT (PTT abierto). */
export function shouldDiscardTtsPlayback(radioMode: string): boolean {
	return radioMode === "LISTENING_PILOT";
}

export function logTtsBlocked(
	source: string,
	reason: string,
	extra?: Record<string, unknown>,
): void {
	if (reason === "ok") return;
	console.warn(`[TTS] Bloqueado (${source}): ${reason}`, extra ?? "");
	recordTtsDecision({
		source,
		allow: false,
		reason,
		category: String(extra?.category ?? ""),
	});
}
