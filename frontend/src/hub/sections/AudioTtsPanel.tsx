import { CollapsibleSection } from "../components/CollapsibleSection";
import { VoiceSelect } from "../components/VoiceSelect";
import { VolumeSlider } from "../components/VolumeSlider";

interface AudioTtsPanelProps {
  ttsVoiceEngineer: string;
  ttsVoiceSpotter: string;
  ttsVolumeBoost: number;
  onEngineerVoice: (v: string) => void;
  onSpotterVoice: (v: string) => void;
  onVolume: (n: number) => void;
}

export function AudioTtsPanel({
  ttsVoiceEngineer,
  ttsVoiceSpotter,
  ttsVolumeBoost,
  onEngineerVoice,
  onSpotterVoice,
  onVolume,
}: AudioTtsPanelProps) {
  return (
    <div className="flex flex-col gap-2">
      <CollapsibleSection title="Voz TTS spotter">
        <label className="hub-label" htmlFor="tts-spotter-voice">Voz del spotter</label>
        <VoiceSelect id="tts-spotter-voice" value={ttsVoiceSpotter} onChange={onSpotterVoice} />
      </CollapsibleSection>
      <CollapsibleSection title="Voz TTS ingeniero">
        <label className="hub-label" htmlFor="tts-engineer-voice">Voz del ingeniero</label>
        <VoiceSelect id="tts-engineer-voice" value={ttsVoiceEngineer} onChange={onEngineerVoice} />
      </CollapsibleSection>
      <CollapsibleSection title="Volumen TTS">
        <VolumeSlider value={ttsVolumeBoost} onChange={onVolume} />
      </CollapsibleSection>
    </div>
  );
}
