/** Shared overlay layout constants (hub + Electron). */
export const OVERLAY_SPEAKING_WIDTH_PX = 400;
/** Card chrome (header + wave + footer) ≈ 152px before message body. */
export const OVERLAY_SPEAKING_MIN_HEIGHT_PX = 152;
/** Safe initial Electron bounds before first DOM measure. */
export const OVERLAY_SPEAKING_DEFAULT_HEIGHT_PX = 172;
export const OVERLAY_SPEAKING_MAX_HEIGHT_PX = 300;
export const OVERLAY_SPEAKING_MESSAGE_MAX_HEIGHT_PX = 180;

export function clampOverlaySpeakingHeight(height: number): number {
  if (!Number.isFinite(height) || height <= 0) {
    return OVERLAY_SPEAKING_DEFAULT_HEIGHT_PX;
  }
  return Math.min(
    OVERLAY_SPEAKING_MAX_HEIGHT_PX,
    Math.max(OVERLAY_SPEAKING_MIN_HEIGHT_PX, Math.ceil(height)),
  );
}

/** Natural content height — scrollHeight avoids clipping when the window is too short. */
export function measureOverlaySpeakingHeight(el: HTMLElement): number {
  const natural = Math.max(el.scrollHeight, el.offsetHeight, el.getBoundingClientRect().height);
  return clampOverlaySpeakingHeight(natural);
}
