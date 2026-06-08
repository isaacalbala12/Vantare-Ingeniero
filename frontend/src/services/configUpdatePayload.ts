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
    spotterMinSpeedMs: cfg.spotterMinSpeedMs ?? 10.0,
    spotterRaceStartDelayS: cfg.spotterRaceStartDelayS ?? 20.0,
    brakingZonesMute: cfg.brakingZonesMute ?? false,
  };
  if (typeof cfg.spotterEnabled === "boolean") {
    payload.spotterEnabled = cfg.spotterEnabled;
  }
  if (typeof cfg.engineerEnabled === "boolean") {
    payload.engineerEnabled = cfg.engineerEnabled;
  }
  return payload;
}
