/** Mapeo TelemetryFrame (sidecar, plano) → telemetría del store UI. */

function sanitizeGapSeconds(value: number): number {
  if (!Number.isFinite(value) || value <= 0 || value > 3600) {
    return 0;
  }
  return value;
}

/** Gaps nativos LMU: coche adelante/detrás en pista (todas las clases). */
export function gapsFromNativeFrame(decoded: Record<string, unknown>): { ahead: number; behind: number } | null {
  const ahead = sanitizeGapSeconds(Number(decoded.time_gap_car_ahead ?? 0));
  const behind = sanitizeGapSeconds(Number(decoded.time_gap_car_behind ?? 0));
  if (ahead > 0 || behind > 0) {
    return { ahead, behind };
  }
  const placeAhead = sanitizeGapSeconds(Number(decoded.time_gap_place_ahead ?? 0));
  const placeBehind = sanitizeGapSeconds(Number(decoded.time_gap_place_behind ?? 0));
  if (placeAhead > 0 || placeBehind > 0) {
    return { ahead: placeAhead, behind: placeBehind };
  }
  return null;
}

/** Fallback: gaps estimados desde rivales de estrategia (puede omitir otras clases en vuelta). */
export function gapsFromCompetitorPace(competitors: unknown[]): { ahead: number; behind: number } {
  let ahead = 99.0;
  let behind = 99.0;
  for (const raw of competitors) {
    if (!raw || typeof raw !== "object") continue;
    const c = raw as Record<string, unknown>;
    const gap = Number(c.gap_to_player ?? c.gap ?? 99);
    if (Number.isNaN(gap)) continue;
    if (gap < 0) ahead = Math.min(ahead, Math.abs(gap));
    if (gap > 0) behind = Math.min(behind, gap);
  }
  return {
    ahead: ahead >= 99 ? 0 : ahead,
    behind: behind >= 99 ? 0 : behind,
  };
}

/**
 * Map native sidecar MessagePack frame → partial UI telemetry store patch.
 * Native frames expose speed in m/s; store `telemetry.speed` is always km/h.
 * Gear can be present in sidecar (`gear`) and may be 0 (neutral) / -1 (reverse).
 */
export function mapSidecarBinaryFrame(decoded: Record<string, unknown>) {
  const speedMs = Number(decoded.speed ?? 0);
  const speedKmh = Math.round(speedMs * 3.6);
  const lapRaw = Number(decoded.lap_number ?? 0);
  const gearRaw = Number(decoded.gear ?? 0);

  return {
    speed: speedKmh,
    rpm: 0,
    gear: Number.isFinite(gearRaw) ? Math.trunc(gearRaw) : 0,
    fuel: Number(decoded.fuel_in_tank ?? 0),
    lap: lapRaw > 0 ? lapRaw : 0,
    position: Number(decoded.standing_position ?? 0),
    tyreWear: {
      fl: Math.round(Number(decoded.tyre_wear_fl ?? 0)),
      fr: Math.round(Number(decoded.tyre_wear_fr ?? 0)),
      rl: Math.round(Number(decoded.tyre_wear_rl ?? 0)),
      rr: Math.round(Number(decoded.tyre_wear_rr ?? 0)),
    },
  };
}
