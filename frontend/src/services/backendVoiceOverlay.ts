import { useAppStore } from "../store/config";

let activeBackendPlaybackId: string | null = null;

/** Reset for tests. */
export function resetBackendVoiceOverlayState(): void {
  activeBackendPlaybackId = null;
}

export function handleBackendVoicePlaybackStart(payload: Record<string, unknown>): void {
  const { config, setRadioMode, setVoicePlaybackText } = useAppStore.getState();
  if (!config.voiceBackendPlayback) return;

  const playbackId = String(payload.playback_id ?? "");
  const text = String(payload.text ?? "").trim();
  activeBackendPlaybackId = playbackId || null;

  if (text) {
    setVoicePlaybackText(text);
  }
  setRadioMode("SPEAKING_ENGINE");
}

export function handleBackendVoicePlaybackEnd(payload: Record<string, unknown>): void {
  const { config, setRadioMode, setVoicePlaybackText } = useAppStore.getState();
  if (!config.voiceBackendPlayback) return;

  const playbackId = String(payload.playback_id ?? "");
  if (activeBackendPlaybackId && playbackId && activeBackendPlaybackId !== playbackId) {
    return;
  }

  activeBackendPlaybackId = null;
  setVoicePlaybackText("");
  setRadioMode("IDLE");
}
