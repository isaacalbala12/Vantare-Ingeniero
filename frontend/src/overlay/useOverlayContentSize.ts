import { useLayoutEffect, useRef } from "react";
import { getPlatform } from "../core/platform";
import type { OverlayPresentation } from "./overlayPresentation";
import {
  measureOverlaySpeakingHeight,
  OVERLAY_SPEAKING_WIDTH_PX,
} from "./overlayDimensions";

const LISTENING_RESIZE_DEBOUNCE_MS = 96;
const SPEAKING_RESIZE_DEBOUNCE_MS = 120;
const LISTENING_SIZE_DELTA_PX = 4;
const SPEAKING_SIZE_DELTA_PX = 6;

/** Measure overlay content and resize Electron window (throttled while speaking). */
export function useOverlayContentSize(active: boolean, presentation: OverlayPresentation) {
  const ref = useRef<HTMLDivElement>(null);
  const lastReported = useRef({ width: 0, height: 0 });

  useLayoutEffect(() => {
    if (!active) return;

    const el = ref.current;
    if (!el) return;

    const isSpeaking = presentation === "speaking";
    const debounceMs = isSpeaking ? SPEAKING_RESIZE_DEBOUNCE_MS : LISTENING_RESIZE_DEBOUNCE_MS;
    const deltaPx = isSpeaking ? SPEAKING_SIZE_DELTA_PX : LISTENING_SIZE_DELTA_PX;

    const report = (force = false) => {
      const width = isSpeaking ? OVERLAY_SPEAKING_WIDTH_PX : el.offsetWidth;
      const height = isSpeaking ? measureOverlaySpeakingHeight(el) : el.offsetHeight;
      const prev = lastReported.current;
      if (
        !force &&
        Math.abs(width - prev.width) < deltaPx &&
        Math.abs(height - prev.height) < deltaPx
      ) {
        return;
      }
      lastReported.current = { width, height };
      getPlatform().reportOverlaySize?.({ width, height });
    };

    report(true);

    let debounceId: ReturnType<typeof setTimeout> | undefined;
    const scheduleReport = () => {
      if (debounceId !== undefined) clearTimeout(debounceId);
      debounceId = setTimeout(() => {
        debounceId = undefined;
        report(false);
      }, debounceMs);
    };

    const observer = new ResizeObserver(scheduleReport);
    observer.observe(el);
    return () => {
      if (debounceId !== undefined) clearTimeout(debounceId);
      observer.disconnect();
    };
  }, [active, presentation]);

  return ref;
}
