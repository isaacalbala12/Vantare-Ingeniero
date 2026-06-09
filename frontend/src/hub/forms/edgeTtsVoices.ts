export interface EdgeTtsVoiceOption {
  id: string;
  label: string;
}

export const EDGE_TTS_VOICES_ES: EdgeTtsVoiceOption[] = [
  { id: "es-ES-AlvaroNeural", label: "Hombre — Español" },
  { id: "es-ES-ElviraNeural", label: "Mujer — Español" },
];

const LABEL_BY_ID = Object.fromEntries(EDGE_TTS_VOICES_ES.map((v) => [v.id, v.label]));

export function voiceLabel(voiceId: string): string {
  return LABEL_BY_ID[voiceId] ?? voiceId;
}

export function isKnownEdgeVoice(voiceId: string): boolean {
  return voiceId in LABEL_BY_ID;
}
