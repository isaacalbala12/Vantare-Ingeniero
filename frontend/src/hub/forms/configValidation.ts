export interface SpotterValidationInput {
  spotterClearDelayS: number;
  spotterHoldRepeatS: number;
  spotterGapFrequencyS: number;
  spotterCarLengthM: number;
  spotterMinSpeedMs: number;
  spotterRaceStartDelayS: number;
  ttsVolumeBoost: number;
}

export function validateSpotterFields(input: SpotterValidationInput): { ok: boolean; message?: string } {
  const {
    spotterClearDelayS,
    spotterHoldRepeatS,
    spotterGapFrequencyS,
    spotterCarLengthM,
    spotterMinSpeedMs,
    spotterRaceStartDelayS,
    ttsVolumeBoost,
  } = input;

  if (
    !Number.isFinite(spotterClearDelayS) ||
    spotterClearDelayS < 0.1 ||
    spotterClearDelayS > 10 ||
    !Number.isFinite(spotterHoldRepeatS) ||
    spotterHoldRepeatS < 0.5 ||
    spotterHoldRepeatS > 30 ||
    !Number.isFinite(spotterGapFrequencyS) ||
    spotterGapFrequencyS < 5 ||
    spotterGapFrequencyS > 120 ||
    !Number.isFinite(spotterCarLengthM) ||
    spotterCarLengthM < 3 ||
    spotterCarLengthM > 8 ||
    !Number.isFinite(spotterMinSpeedMs) ||
    spotterMinSpeedMs < 0 ||
    spotterMinSpeedMs > 40 ||
    !Number.isFinite(spotterRaceStartDelayS) ||
    spotterRaceStartDelayS < 0 ||
    spotterRaceStartDelayS > 120 ||
    !Number.isFinite(ttsVolumeBoost) ||
    ttsVolumeBoost < 0 ||
    ttsVolumeBoost > 100
  ) {
    return { ok: false, message: "Invalid spotter/TTS values" };
  }

  return { ok: true };
}
