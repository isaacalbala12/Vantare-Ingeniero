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

export function mapSidecarBinaryFrame(decoded: Record<string, unknown>) {
  const speedMs = Number(decoded.speed ?? 0);

  return {
    speed: Math.round(speedMs * 3.6),
    rpm: 0,
    gear: 0,
    fuel: Number(decoded.fuel_in_tank ?? 0),
    lap: Number(decoded.lap_number ?? 1),
    position: Number(decoded.standing_position ?? 1),
    tyreWear: {
      fl: Math.round(Number(decoded.tyre_wear_fl ?? 0)),
      fr: Math.round(Number(decoded.tyre_wear_fr ?? 0)),
      rl: Math.round(Number(decoded.tyre_wear_rl ?? 0)),
      rr: Math.round(Number(decoded.tyre_wear_rr ?? 0)),
    },
  };
}
