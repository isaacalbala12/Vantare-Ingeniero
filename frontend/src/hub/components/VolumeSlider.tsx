interface VolumeSliderProps {
  value: number;
  onChange: (percent: number) => void;
}

export function VolumeSlider({ value, onChange }: VolumeSliderProps) {
  const safe = Math.min(100, Math.max(0, Math.round(value)));
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-between text-xs text-a1-text-muted">
        <span>Volumen TTS</span>
        <span>{safe}%</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={safe}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-a1-accent"
      />
    </div>
  );
}
