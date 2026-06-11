import type React from "react";

export type ProactivityLevel = "low" | "normal" | "high";
export type ProfileId = "formal" | "standard" | "aggressive";

export function engineerTonePreview(
  profileId: ProfileId,
  sweary: boolean,
): string {
  const tones: Record<string, string> = {
    formal: "Tono profesional y preciso. Sin muletillas. Máximo 2 frases.",
    standard:
      "Tono de radio de boxes: directo, claro, motivador sin excesos.",
    aggressive:
      "Tono enérgico y exigente. Empuja al piloto. Máximo 2 frases contundentes.",
  };
  let text = tones[profileId] ?? tones.standard;
  if (sweary) {
    text +=
      " Lenguaje coloquial de paddock permitido; evita prefijos robóticos tipo «Atención».";
  }
  return text;
}

interface PersonalityPanelProps {
  personalityProfileId: ProfileId;
  swearyMessages: boolean;
  proactivityLevel: ProactivityLevel;
  pearlFrequency: number;
  onProfileId: (v: ProfileId) => void;
  onSweary: (v: boolean) => void;
  onProactivity: (v: ProactivityLevel) => void;
  onPearlFrequency: (v: number) => void;
}

export const PersonalityPanel: React.FC<PersonalityPanelProps> = ({
  personalityProfileId,
  swearyMessages,
  proactivityLevel,
  pearlFrequency,
  onProfileId: _onProfileId,
  onSweary: _onSweary,
  onProactivity,
  onPearlFrequency,
}) => {
  const preview = engineerTonePreview(personalityProfileId, swearyMessages);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <label className="hub-label">Proactividad del ingeniero</label>
        <select
          value={proactivityLevel}
          onChange={(e) =>
            onProactivity(e.target.value as ProactivityLevel)
          }
          className="hub-input"
        >
          <option value="low">Baja (solo HIGH+CRITICAL)</option>
          <option value="normal">Normal (MEDIUM+)</option>
          <option value="high">Alta (todo incluso LOW)</option>
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="hub-label">
          Frecuencia de perlas ({Math.round(pearlFrequency * 100)}%)
        </label>
        <input
          type="range"
          min={0}
          max={100}
          value={Math.round(pearlFrequency * 100)}
          onChange={(e) => onPearlFrequency(Number(e.target.value) / 100)}
          className="w-full accent-a1-accent"
        />
        <span className="text-[10px] text-a1-text-muted">
          {pearlFrequency <= 0
            ? "Sin perlas de sabiduría"
            : pearlFrequency >= 1
              ? "Máxima frecuencia de perlas"
              : "Perlas ocasionales"}
        </span>
      </div>

      <p className="text-[10px] text-a1-text-muted italic leading-relaxed">
        Preview: {preview}
      </p>
    </div>
  );
};
