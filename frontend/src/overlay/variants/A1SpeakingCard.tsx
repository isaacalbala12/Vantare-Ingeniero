import { memo } from "react";
import { useAppStore } from "../../store/config";
import { t } from "../../i18n/strings";
import {
  OVERLAY_SPEAKING_MESSAGE_MAX_HEIGHT_PX,
  OVERLAY_SPEAKING_WIDTH_PX,
} from "../overlayDimensions";

const WAVE_HEIGHTS = [45, 70, 55, 80, 60, 75];

export const A1SpeakingCard = memo(function A1SpeakingCard() {
  const uiLanguage = useAppStore((s) => s.config.uiLanguage);
  const voicePlaybackText = useAppStore((s) => s.radio.voicePlaybackText);
  const activeMessage = voicePlaybackText.trim() || "…";

  return (
    <div
      className="relative w-fit rounded-[5px] overflow-hidden shadow-[0_10px_36px_rgba(0,0,0,0.55)] bg-[#121216] border border-[rgba(237,237,240,0.08)]"
      style={{
        fontFamily: "var(--font-a1-body)",
        width: OVERLAY_SPEAKING_WIDTH_PX,
        contain: "layout style paint",
      }}
    >
      <div className="overlay-a1-aurora absolute inset-0 opacity-25 pointer-events-none" />
      <div
        className="overlay-a1-stripe absolute top-4 bottom-4 left-3 w-[3px] rounded-sm opacity-70"
        style={{ background: "linear-gradient(180deg, transparent, #c42040, #9b1b32, #c42040, transparent)" }}
      />

      <div className="relative z-10 px-5 py-4 pl-7">
        <div className="flex items-baseline gap-3 mb-3">
          <div
            className="text-[20px] font-bold tracking-[0.15em] uppercase text-[#ededf0]"
            style={{ fontFamily: "var(--font-a1-display)" }}
          >
            Vantare
          </div>
          <div className="text-[10px] font-medium tracking-[0.35em] uppercase text-[#c42040]">{t(uiLanguage, "speaking")}</div>
        </div>

        <div className="flex items-end gap-[2.5px] h-[18px] mb-3">
          {WAVE_HEIGHTS.map((h, i) => (
            <div
              key={i}
              className="overlay-a1-wave-bar w-[3px] rounded-[1.5px] opacity-60"
              style={{
                height: `${h}%`,
                background: "linear-gradient(180deg, #c42040, #9b1b32)",
                animationDelay: `${i * 0.12}s`,
              }}
            />
          ))}
        </div>

        <div
          className="overflow-y-auto text-[14.5px] font-medium leading-[1.55] tracking-[0.02em] text-[#f4f4f5] whitespace-pre-wrap break-words"
          style={{
            maxHeight: OVERLAY_SPEAKING_MESSAGE_MAX_HEIGHT_PX,
          }}
        >
          {activeMessage}
        </div>

        <div className="flex justify-between items-center mt-3 pt-2 border-t border-[rgba(237,237,240,0.08)]">
          <div
            className="text-[8.5px] font-medium tracking-[0.25em] uppercase text-[rgba(244,244,245,0.35)]"
            style={{ fontFamily: "var(--font-a1-display)" }}
          >
            {t(uiLanguage, "engineerChannel")}
          </div>
          <div className="overlay-a1-live-dot text-[9px] font-semibold tracking-[0.15em] uppercase text-[#c42040] flex items-center gap-1.5">
            <span className="inline-block w-[5px] h-[5px] rounded-full bg-[#c42040]" />
            {t(uiLanguage, "live")}
          </div>
        </div>
      </div>
    </div>
  );
});
