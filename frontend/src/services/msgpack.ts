/**
 * MessagePack + Delta encoding codec for telemetry frames.
 *
 * Provides encode/decode for binary MessagePack transport and
 * delta computation for efficient 20Hz telemetry streaming.
 *
 * Frame format:
 *   - Delta:   {_t: number, <changed fields...>}
 *   - Full:    {_t: number, _full: true, <all fields...>}
 */
import { encode, decode } from "@msgpack/msgpack";

/** Send a full snapshot every 100 frames (~5 seconds at 20Hz). */
export const SNAPSHOT_INTERVAL = 100;

/**
 * Encode a plain object to MessagePack binary.
 */
export function encodeMsgpack(data: Record<string, unknown>): Uint8Array {
  return encode(data) as Uint8Array;
}

/**
 * Decode MessagePack binary to a plain object.
 */
export function decodeMsgpack(data: Uint8Array): Record<string, unknown> {
  return decode(data) as Record<string, unknown>;
}

/**
 * Compute a delta from previous frame to current frame.
 *
 * @param current - The current telemetry frame.
 * @param previous - The previous frame, or null on first invocation.
 * @param forceFull - If true, emit a full snapshot regardless of diff.
 * @returns A delta object with _t (timestamp) and optionally _full=true.
 *          Only fields that changed vs previous are included.
 *          If previous is null, emits a full snapshot.
 */
export function computeDelta(
  current: Record<string, unknown>,
  previous: Record<string, unknown> | null,
  forceFull: boolean = false,
): Record<string, unknown> {
  const ts = Date.now() / 1000; // Unix timestamp in seconds

  if (previous === null || forceFull) {
    const result: Record<string, unknown> = { ...current, _full: true, _t: ts };
    return result;
  }

  const delta: Record<string, unknown> = { _t: ts };
  for (const key of Object.keys(current)) {
    if (!(key in previous) || previous[key] !== current[key]) {
      delta[key] = current[key];
    }
  }
  return delta;
}
