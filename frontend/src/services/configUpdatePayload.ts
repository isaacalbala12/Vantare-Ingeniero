import type { AppConfig } from "../store/config";

export function buildConfigUpdatePayload(cfg: AppConfig): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    swearyMessages: cfg.swearyMessages ?? false,
    spotterOffQualifying: cfg.spotterOffQualifying ?? true,
    spotterExcludeStopped: cfg.spotterExcludeStopped ?? true,
    personalityProfileId: cfg.personalityProfileId ?? "standard",
    verbosityLevel: cfg.verbosityLevel ?? "normal",
    spotterClearDelayS: cfg.spotterClearDelayS ?? 0.15,
    spotterOverlapDelayS: cfg.spotterOverlapDelayS ?? 2.0,
    spotterHoldRepeatS: cfg.spotterHoldRepeatS ?? 3.0,
    spotterGapFrequencyS: cfg.spotterGapFrequencyS ?? 30.0,
    spotterCarLengthM: cfg.spotterCarLengthM ?? 4.5,
    spotterMinSpeedMs: cfg.spotterMinSpeedMs ?? 5.0,
    spotterRaceStartDelayS: cfg.spotterRaceStartDelayS ?? 3.0,
    brakingZonesMute: cfg.brakingZonesMute ?? false,
    spotterEnabled: cfg.spotterEnabled ?? true,
  };
  if (typeof cfg.speakOnlyWhenSpokenTo === "boolean") {
    payload.speakOnlyWhenSpokenTo = cfg.speakOnlyWhenSpokenTo;
  }
  if (typeof cfg.engineerEnabled === "boolean") {
    payload.engineerEnabled = cfg.engineerEnabled;
  }
  return payload;
}
