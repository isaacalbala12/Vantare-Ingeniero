import type React from "react";
import { t, type AppLanguage } from "../../i18n/strings";
import { useAppStore } from "../../store/config";

export type ProactivityLevel = "low" | "normal" | "high";
export type ProfileId = "formal" | "standard" | "aggressive";

export function engineerTonePreview(
  profileId: ProfileId,
  sweary: boolean,
  language: AppLanguage = "es",
): string {
  const tones: Record<string, string> = {
    formal: t(language, "toneFormal"),
    standard: t(language, "toneStandard"),
    aggressive: t(language, "toneAggressive"),
  };
  let text = tones[profileId] ?? tones.standard;
  if (sweary) {
    text += t(language, "toneSwearySuffix");
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
  const uiLanguage = useAppStore((s) => s.config.uiLanguage);
  const preview = engineerTonePreview(personalityProfileId, swearyMessages, uiLanguage);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <label className="hub-label">{t(uiLanguage, "engineerProactivity")}</label>
        <select
          value={proactivityLevel}
          onChange={(e) =>
            onProactivity(e.target.value as ProactivityLevel)
          }
          className="hub-input"
        >
          <option value="low">{t(uiLanguage, "proactivityLow")}</option>
          <option value="normal">{t(uiLanguage, "proactivityNormal")}</option>
          <option value="high">{t(uiLanguage, "proactivityHigh")}</option>
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="hub-label">
          {t(uiLanguage, "pearlFrequency")} ({Math.round(pearlFrequency * 100)}%)
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
            ? t(uiLanguage, "noPearls")
            : pearlFrequency >= 1
              ? t(uiLanguage, "maxPearls")
              : t(uiLanguage, "occasionalPearls")}
        </span>
      </div>

      <p className="text-[10px] text-a1-text-muted italic leading-relaxed">
        {t(uiLanguage, "preview")}: {preview}
      </p>
    </div>
  );
};
