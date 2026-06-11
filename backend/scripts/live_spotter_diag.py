"""Diagnóstico en vivo: telemetría LMU + detectores de proximidad del spotter."""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared-strategy" / "src"))
sys.path.insert(0, str(ROOT / "shared-telemetry" / "src"))
sys.path.insert(0, str(ROOT / "backend"))

from shared_telemetry import TelemetryReader  # noqa: E402
from src.services.strategy_service import StrategyService  # noqa: E402
from src.intelligence.spotter_adapter import frame_to_spotter_tick  # noqa: E402
from src.intelligence.spotter_geometry import (  # noqa: E402
    detect_lateral_proximity,
    detect_path_lateral_proximity,
)
from src.intelligence.cartesian_spotter import (  # noqa: E402
    detect_cartesian_overlap,
    resolve_player_forward_xz,
)


def main() -> None:
    reader = TelemetryReader(offline=False)
    reader.start()
    time.sleep(0.5)
    svc = StrategyService(reader)
    frame_dict = svc.snapshot_frame()
    if not frame_dict:
        print("NO SHM DATA — ¿LMU en pista?")
        raise SystemExit(1)

    tick = frame_to_spotter_tick(frame_dict)
    comps = tick.get("competitors") or []
    player_lap = tick.get("lap_number")
    speed = math.hypot(tick.get("vel_x", 0.0), tick.get("vel_z", 0.0))
    print(
        f"player lap={player_lap} dist={tick.get('lap_distance', 0):.0f} "
        f"path_lat={tick.get('path_lateral', 0):.2f} track_len={tick.get('track_length_m', 0):.0f} "
        f"comps={len(comps)} speed={speed:.1f} m/s"
    )

    lap_counts: dict[int, int] = {}
    for c in comps:
        ln = int(c.get("lap_number") or 0)
        lap_counts[ln] = lap_counts.get(ln, 0) + 1
    top_laps = sorted(lap_counts.items(), key=lambda x: -x[1])[:5]
    print(f"rival lap distribution (top): {top_laps}")

    px, pz = tick["pos_x"], tick["pos_z"]
    closest = None
    for c in comps:
        if c.get("in_pits"):
            continue
        d = math.hypot(c["pos_x"] - px, c["pos_z"] - pz)
        if closest is None or d < closest[0]:
            closest = (d, c)
    if closest:
        d, c = closest
        print(
            f"closest rival d={d:.1f}m lap={c.get('lap_number')} "
            f"path_lat={c.get('path_lateral', 0):.2f} lap_dist={c.get('lap_distance', 0):.0f}"
        )

    threshold = 3.0
    track_len = float(tick.get("track_length_m") or 0)
    path_hits = detect_path_lateral_proximity(
        int(player_lap or 0),
        float(tick.get("lap_distance", 0)),
        float(tick.get("path_lateral", 0)),
        comps,
        threshold,
        track_length_m=track_len,
        player_speed_ms=speed,
        car_length_m=5.0,
    )
    pf = resolve_player_forward_xz(
        float(tick.get("ori_fwd_x", 0)),
        float(tick.get("ori_fwd_z", 0)),
        float(tick.get("vel_x", 0)),
        float(tick.get("vel_z", 0)),
    )
    cart = detect_cartesian_overlap(
        (tick["pos_x"], tick["pos_y"], tick["pos_z"]),
        pf,
        comps,
        lateral_threshold_m=threshold,
        player_speed_ms=speed,
    )
    legacy = detect_lateral_proximity(
        (tick["pos_x"], tick["pos_y"], tick["pos_z"]),
        (tick["vel_x"], tick["vel_y"], tick["vel_z"]),
        comps,
        threshold,
    )
    print(f"path_hits={len(path_hits)} cart_hits={len(cart)} legacy_hits={len(legacy)}")
    if path_hits:
        print(" path sample:", path_hits[0])
    if cart:
        print(" cart sample:", cart[0])


if __name__ == "__main__":
    main()
