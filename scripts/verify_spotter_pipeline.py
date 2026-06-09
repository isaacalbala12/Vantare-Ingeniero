#!/usr/bin/env python3
"""Verificación rápida del pipeline spotter proximidad (sin LMU).

Uso desde la raíz del repo:
  python scripts/verify_spotter_pipeline.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
sys.path.insert(0, str(BACKEND))

from tests.fixtures.spotter.helpers import load_frame, load_tick_sequence  # noqa: E402
from tests.test_spotter_proximity_pipeline import (  # noqa: E402
    make_side_by_side_race_frame,
    make_world_only_miss_frame,
)
from src.intelligence.spotter import SpotterService  # noqa: E402
from src.intelligence.spotter_adapter import frame_to_spotter_tick  # noqa: E402
from src.intelligence.cartesian_spotter import (  # noqa: E402
    detect_cartesian_overlap,
    resolve_player_forward_xz,
)
from src.intelligence.spotter_geometry import detect_path_lateral_proximity  # noqa: E402


def ok(label: str) -> None:
    print(f"  OK  {label}")


def fail(label: str, detail: str) -> None:
    print(f"  FAIL {label}: {detail}")
    sys.exit(1)


def main() -> None:
    print("Verificando pipeline spotter (sin LMU)...")
    frame = make_side_by_side_race_frame()
    comp = frame["competitors"][0]

    hits = detect_path_lateral_proximity(
        frame["lap_number"],
        frame["lap_distance"],
        frame["path_lateral"],
        [comp],
        4.0,
    )
    if not hits:
        fail("path_lateral", "no detectó rival al lado")
    ok("path_lateral detecta coche al lado")

    overlap = load_frame("world_overlap_no_path_delta")
    overlap_comp = overlap["competitors"][0]
    fwd = resolve_player_forward_xz(
        overlap["ori_fwd_x"],
        overlap["ori_fwd_z"],
        overlap["vel_x"],
        overlap["vel_z"],
    )
    cart_hits = detect_cartesian_overlap(
        (overlap["pos_x"], overlap["pos_y"], overlap["pos_z"]),
        fwd,
        [overlap_comp],
        lateral_threshold_m=3.0,
    )
    if not cart_hits:
        fail("cartesian", "no detectó rival con path_lateral ~0")
    ok("cartesian detecta overlap sin delta path_lateral")

    tick = frame_to_spotter_tick(frame, advice=None)
    if tick.get("path_lateral") is None and "path_lateral" not in tick:
        fail("adapter", "path_lateral no llega al tick del spotter")
    ok("spotter_adapter mapea path_lateral")

    messages: list = []

    def capture(msg) -> None:
        messages.append(msg)

    spotter = SpotterService(broadcast_callback=capture, proximity_threshold_m=3.0)
    spotter.evaluate_tick(tick)
    prox = [m for m in messages if getattr(m, "category", None) == "proximity"]
    if not prox:
        fail("spotter broadcast", "no se emitió alerta proximity")
    alert = prox[0]
    ok(f"spotter emite alerta: {alert.message!r}")

    if int(alert.audio_priority) < 2:
        fail("voice eligibility", f"audio_priority={alert.audio_priority}")
    ok("audio_priority >= 2 (elegible para TTS en frontend)")

    miss_messages: list = []

    def capture_miss(msg) -> None:
        miss_messages.append(msg)

    SpotterService(
        broadcast_callback=capture_miss,
        proximity_threshold_m=3.0,
    ).evaluate_tick(frame_to_spotter_tick(make_world_only_miss_frame(), advice=None))
    if any(getattr(m, "category", None) == "proximity" for m in miss_messages):
        fail("regression", "falso positivo con rival lejos en coords mundo")
    ok("sin falso positivo cuando rival está lejos en XZ")

    seq_messages: list = []

    def capture_seq(msg) -> None:
        seq_messages.append(msg)

    seq_spotter = SpotterService(broadcast_callback=capture_seq, proximity_threshold_m=3.0)
    for tick_frame in load_tick_sequence("tick_sequence_overtake"):
        seq_spotter.evaluate_tick(frame_to_spotter_tick(tick_frame, advice=None))
    seq_prox = [
        m for m in seq_messages
        if getattr(m, "category", None) == "proximity" and not m.payload.get("clear")
    ]
    if not seq_prox:
        fail("sequence", "secuencia temporal no emitió proximity")
    ok(f"secuencia temporal: {len(seq_prox)} alerta(s) proximity")

    quali_frame = make_side_by_side_race_frame()
    quali_frame["session_type"] = "qualifying"
    quali_tick = frame_to_spotter_tick(quali_frame, advice=None)
    quali_messages: list = []

    def capture_quali(msg) -> None:
        quali_messages.append(msg)

    SpotterService(
        broadcast_callback=capture_quali,
        proximity_threshold_m=3.0,
        spotter_off_qualifying=True,
    ).evaluate_tick(quali_tick)
    if any(getattr(m, "category", None) == "proximity" for m in quali_messages):
        fail("qualifying", "proximity no debe sonar en quali con spotterOffQualifying")
    ok("qualifying silent: sin proximity lateral")

    print("\nPipeline backend OK. Ejecutando pytest CC parity + spotter:")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_spotter_cc_parity.py",
            "tests/test_spotter_state.py",
            "tests/test_spotter_proximity_pipeline.py",
            "-q",
        ],
        cwd=str(BACKEND),
    )
    if result.returncode != 0:
        fail("pytest spotter", "tests spotter CC parity fallaron")
    ok("pytest spotter CC parity + state + pipeline")

    print("\nGate frontend (vitest):")
    print("  cd frontend && npm test -- alertVoice.test.ts priorityAudioQueue.test.ts ttsCache.test.ts useWebSocket.spotter.test.ts --run")


if __name__ == "__main__":
    main()
