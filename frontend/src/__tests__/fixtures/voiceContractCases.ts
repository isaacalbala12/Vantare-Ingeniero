// Voice contract matrix — mirrors docs/voice-contract.md §4
// Used by voiceContractMatrix.test.ts, voiceContractPtt.test.ts

export type VoiceContractAlertCase = {
  id: string;
  speakOnly: boolean;
  spotterEnabled: boolean;
  engineerEnabled: boolean;
  payload: Record<string, unknown>;
  message: string;
  expectAllow: boolean;
  expectReason: string;
};

/** §4.1 Alertas — config × categoría */
export const VOICE_CONTRACT_ALERT_CASES: VoiceContractAlertCase[] = [
  {
    id: "VC-A01",
    speakOnly: false,
    spotterEnabled: true,
    engineerEnabled: false,
    message: "Coche a la derecha",
    payload: { category: "proximity", severity: "INFO", audio_priority: "2", service: "spotter" },
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-A02",
    speakOnly: false,
    spotterEnabled: false,
    engineerEnabled: false,
    message: "Coche a la derecha",
    payload: { category: "proximity", severity: "INFO", audio_priority: "2", service: "spotter" },
    expectAllow: false,
    expectReason: "service_toggle_off",
  },
  {
    id: "VC-A03",
    speakOnly: true,
    spotterEnabled: true,
    engineerEnabled: false,
    message: "Coche a la derecha",
    payload: { category: "proximity", severity: "INFO", audio_priority: "2", service: "spotter" },
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-A04",
    speakOnly: true,
    spotterEnabled: true,
    engineerEnabled: false,
    message: "Box esta vuelta",
    payload: { category: "engineer", severity: "CRITICAL", audio_priority: "4", service: "engineer" },
    expectAllow: false,
    expectReason: "speak_only_blocks_proactive_engineer",
  },
  {
    id: "VC-A05",
    speakOnly: true,
    spotterEnabled: false,
    engineerEnabled: false,
    message: "Afirmativo, recepción clara.",
    payload: { category: "voice_response", severity: "INFO", audio_priority: "4", service: "engineer", fast_command: true },
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-A06",
    speakOnly: false,
    spotterEnabled: false,
    engineerEnabled: true,
    message: "Buen trabajo piloto.",
    payload: { category: "pearl", severity: "INFO", audio_priority: "2" },
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-A07",
    speakOnly: false,
    spotterEnabled: false,
    engineerEnabled: false,
    message: "Buen trabajo piloto.",
    payload: { category: "pearl", severity: "INFO", audio_priority: "2" },
    expectAllow: false,
    expectReason: "service_toggle_off",
  },
  {
    id: "VC-A08",
    speakOnly: false,
    spotterEnabled: true,
    engineerEnabled: true,
    message: "+1.2s",
    payload: { category: "gaps", severity: "INFO", audio_priority: "1" },
    expectAllow: false,
    expectReason: "low_priority_or_no_voice_category",
  },
  {
    id: "VC-A09",
    speakOnly: false,
    spotterEnabled: true,
    engineerEnabled: true,
    message: "Sistema actualizado",
    payload: { category: "system", severity: "CRITICAL", audio_priority: "4" },
    expectAllow: false,
    expectReason: "low_priority_or_no_voice_category",
  },
  {
    id: "VC-A10",
    speakOnly: false,
    spotterEnabled: true,
    engineerEnabled: true,
    message: "Coche a 0.3s",
    payload: { category: "proximity", severity: "INFO", audio_priority: "1" },
    expectAllow: false,
    expectReason: "low_priority_or_no_voice_category",
  },
  {
    id: "VC-A11",
    speakOnly: false,
    spotterEnabled: false,
    engineerEnabled: true,
    message: "Coche a la derecha",
    payload: { category: "proximity", severity: "INFO", audio_priority: "2" },
    expectAllow: false,
    expectReason: "service_toggle_off",
  },
  {
    id: "VC-A12",
    speakOnly: false,
    spotterEnabled: true,
    engineerEnabled: true,
    message: "   ",
    payload: { category: "proximity", severity: "INFO", audio_priority: "2" },
    expectAllow: false,
    expectReason: "empty_message",
  },
  {
    id: "VC-A13",
    speakOnly: false,
    spotterEnabled: false,
    engineerEnabled: false,
    message: "Afirmativo",
    payload: { category: "voice_response", severity: "INFO", audio_priority: "4" },
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-A14",
    speakOnly: false,
    spotterEnabled: true,
    engineerEnabled: false,
    message: "Combustible bajo",
    payload: { category: "fuel", severity: "INFO", audio_priority: "4" },
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-A15",
    speakOnly: false,
    spotterEnabled: true,
    engineerEnabled: false,
    message: "Safety car desplegado",
    payload: { category: "safety_car", severity: "INFO", audio_priority: "4" },
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-A16",
    speakOnly: false,
    spotterEnabled: true,
    engineerEnabled: false,
    message: "Daños detectados",
    payload: { category: "damage", severity: "INFO", audio_priority: "3" },
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-A17",
    speakOnly: false,
    spotterEnabled: true,
    engineerEnabled: false,
    message: "Pit limiter no activado",
    payload: { category: "pit_limiter", severity: "INFO", audio_priority: "4" },
    expectAllow: true,
    expectReason: "ok",
  },
  // VC-A18 is N/A for alerts — use VC-C* commentary tests instead
];

export type VoiceContractAdviceCase = {
  id: string;
  speakOnly: boolean;
  engineerEnabled: boolean;
  event: string;
  fullText: string;
  expectAllow: boolean;
  expectReason: string;
};

/** §4.2 Advice / PTT */
export const VOICE_CONTRACT_ADVICE_CASES: VoiceContractAdviceCase[] = [
  {
    id: "VC-P01",
    speakOnly: true,
    engineerEnabled: false,
    event: "advice_end",
    fullText: "Tienes 5 vueltas de fuel",
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-P02",
    speakOnly: true,
    engineerEnabled: false,
    event: "advice_end",
    fullText: "",
    expectAllow: false,
    expectReason: "empty_message",
  },
  {
    id: "VC-P03",
    speakOnly: true,
    engineerEnabled: false,
    event: "advice_end",
    fullText: "---texto interno---",
    expectAllow: false,
    expectReason: "internal_radio_text",
  },
  {
    id: "VC-P04",
    speakOnly: false,
    engineerEnabled: false,
    event: "advice_end",
    fullText: "Respuesta válida",
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-P05",
    speakOnly: false,
    engineerEnabled: false,
    event: "advice_end",
    fullText: "Mensaje válido",
    expectAllow: false,
    expectReason: "reconnect_grace",
  },
  // VC-P06 / VC-P07: ver voiceContractPtt.test.ts (gate + shouldDiscardTtsPlayback)
];

export type VoiceContractCommentaryCase = {
  id: string;
  speakOnly: boolean;
  engineerEnabled: boolean;
  expectAllow: boolean;
  expectReason: string;
};

/** §4.3 Commentary proactivo */
export const VOICE_CONTRACT_COMMENTARY_CASES: VoiceContractCommentaryCase[] = [
  {
    id: "VC-C01",
    speakOnly: false,
    engineerEnabled: true,
    expectAllow: true,
    expectReason: "ok",
  },
  {
    id: "VC-C02",
    speakOnly: true,
    engineerEnabled: true,
    expectAllow: false,
    expectReason: "speak_only_blocks_commentary",
  },
  {
    id: "VC-C03",
    speakOnly: false,
    engineerEnabled: false,
    expectAllow: false,
    expectReason: "engineer_disabled",
  },
  {
    id: "VC-C04",
    speakOnly: true,
    engineerEnabled: false,
    expectAllow: false,
    expectReason: "engineer_disabled",
  },
];
