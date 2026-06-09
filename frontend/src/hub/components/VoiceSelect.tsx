import { EDGE_TTS_VOICES_ES } from "../forms/edgeTtsVoices";

interface VoiceSelectProps {
  value: string;
  onChange: (voiceId: string) => void;
  id?: string;
}

export function VoiceSelect({ value, onChange, id }: VoiceSelectProps) {
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="hub-input">
      {EDGE_TTS_VOICES_ES.map((v) => (
        <option key={v.id} value={v.id}>
          {v.label}
        </option>
      ))}
    </select>
  );
}
