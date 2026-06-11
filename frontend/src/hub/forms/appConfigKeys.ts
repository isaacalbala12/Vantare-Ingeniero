import type { AppConfig } from "../../store/config";

export const APP_CONFIG_KEYS = [
  "vllmIP", "serverPort", "micDevice", "speakerDevice", "wakeWord", "sensitivity",
  "pttHotkey", "pttStopHotkey", "wakeWordEnabled", "swearyMessages",
  "spotterOffQualifying", "spotterExcludeStopped", "mqttEnabled", "mqttBroker", "mqttPort",
  "personalityProfileId", "verbosityLevel", "ttsVoiceEngineer", "ttsVoiceSpotter", "ttsBackend",
  "ttsProviderEngineer", "ttsProviderSpotter",
  "spotterClearDelayS", "spotterOverlapDelayS", "spotterHoldRepeatS", "spotterGapFrequencyS",
  "spotterCarLengthM", "spotterMinSpeedMs", "spotterRaceStartDelayS",
  "brakingZonesMute", "speakOnlyWhenSpokenTo", "ttsVolumeBoost",
  "spotterEnabled", "engineerEnabled",
] as const satisfies readonly (keyof AppConfig)[];

export function assertFullAppConfig(payload: AppConfig): void {
  for (const key of APP_CONFIG_KEYS) {
    if (!(key in payload)) throw new Error(`Missing profile key: ${key}`);
  }
}
