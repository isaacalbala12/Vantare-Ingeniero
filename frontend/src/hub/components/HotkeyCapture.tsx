import { useCallback, useEffect, useRef, useState } from "react";
import {
  formatGamepadHotkeyLabel,
  gamepadButtonToHotkey,
  isGamepadHotkey,
  isMouseHotkey,
  keyboardEventToHotkey,
  mouseButtonToHotkey,
  normalizeHotkey,
} from "../forms/hotkeyFormat";
import { t } from "../../i18n/strings";
import { useAppStore } from "../../store/config";

interface HotkeyCaptureProps {
  value: string;
  onChange: (hotkey: string) => void;
  label: string;
}

function formatHotkeyLabel(value: string, uiLanguage: "es" | "en"): string {
  if (isGamepadHotkey(value)) return formatGamepadHotkeyLabel(value);
  return value || t(uiLanguage, "unassigned");
}

export function HotkeyCapture({ value, onChange, label }: HotkeyCaptureProps) {
  const uiLanguage = useAppStore((s) => s.config.uiLanguage);
  const [listening, setListening] = useState(false);
  const pressedRef = useRef<Set<string>>(new Set());

  const stop = useCallback(() => {
    setListening(false);
    pressedRef.current.clear();
  }, []);

  useEffect(() => {
    if (!listening) return;

    const onKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.key === "Escape") {
        stop();
        return;
      }
      const hk = keyboardEventToHotkey(e);
      if (hk) {
        onChange(hk);
        stop();
      }
    };

    const onMouseDown = (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const hk = mouseButtonToHotkey(e.button);
      if (hk) {
        onChange(normalizeHotkey(hk));
        stop();
      }
    };

    const pollGamepads = () => {
      const pads = navigator.getGamepads?.() ?? [];
      for (let padIndex = 0; padIndex < pads.length; padIndex += 1) {
        const pad = pads[padIndex];
        if (!pad) continue;
        for (let buttonIndex = 0; buttonIndex < pad.buttons.length; buttonIndex += 1) {
          const pressed = pad.buttons[buttonIndex]?.pressed ?? false;
          const key = `${padIndex}:${buttonIndex}`;
          if (pressed && !pressedRef.current.has(key)) {
            pressedRef.current.add(key);
            onChange(gamepadButtonToHotkey(padIndex, buttonIndex));
            stop();
            return;
          }
          if (!pressed) pressedRef.current.delete(key);
        }
      }
    };

    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("mousedown", onMouseDown, true);
    const timer = window.setInterval(pollGamepads, 40);
    return () => {
      window.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("mousedown", onMouseDown, true);
      window.clearInterval(timer);
    };
  }, [listening, onChange, stop]);

  return (
    <div className="flex flex-col gap-1">
      <span className="hub-label">{label}</span>
      <button
        type="button"
        onClick={() => setListening(true)}
        className={`hub-input text-left ${listening ? "ring-2 ring-a1-accent" : ""}`}
      >
        {listening
          ? t(uiLanguage, "captureHotkey")
          : formatHotkeyLabel(value, uiLanguage)}
      </button>
      {isMouseHotkey(value) ? (
        <p className="text-[10px] text-a1-text-muted">{t(uiLanguage, "mouseHubOnly")}</p>
      ) : null}
      {isGamepadHotkey(value) ? (
        <p className="text-[10px] text-a1-text-muted">
          {t(uiLanguage, "gamepadWorksOnTrack")}
        </p>
      ) : null}
    </div>
  );
}
