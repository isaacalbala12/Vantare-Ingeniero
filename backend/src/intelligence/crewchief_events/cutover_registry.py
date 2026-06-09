"""Event IDs owned by the Crew Chief suite (not legacy proactive/commentary)."""

from __future__ import annotations

CC_OWNED_EVENT_IDS = frozenset({
    "position_change",
    "overtake",
    "being_overtaken",
    "overtake_position_gain",
    "position_loss",
    "position_gain",
    "position_reminder",
    "race_start",
    "race_start_good",
    "race_start_bad",
    "race_start_quality",
    "lap_complete",
    "fast_lap",
    "gap_update",
    "cut_track_warning",
    "fuel_about_to_run_out",
    "gap_ahead_decreasing",
    "gap_ahead_increasing",
    "gap_ahead_holding",
    "gap_behind_increasing",
    "gap_behind_decreasing",
    "gap_behind_holding",
    "gap_being_pressured",
    "gap_holding_us_up",
    "lap_personal_best",
    "lap_invalid",
    "lap_consistency_improving",
    "lap_consistency_worsening",
    "lap_consistency_stable",
    "sector_personal_best",
    "sector_off_pace",
    "lap_counter_announce",
    "last_lap_race",
    "push_to_win",
    "push_to_hold",
    "session_victory",
    "session_podium",
    "session_finish",
    "session_bad_finish",
    "session_disqualified",
    "session_dnf",
    "fuel_laps_remaining",
    "fuel_box_this_lap",
    "pit_window_open",
    "pit_window_closing",
    "pit_entry",
    "pit_exit",
    "pit_stop_prediction",
    "opponent_pitting",
    "frozen_order",
    "frozen_order_instruction",
    "multiclass_faster_behind",
    "multiclass_slower_ahead",
    "multiclass_class_leader_behind",
    "tyre_hot",
    "tyre_cooking",
    "tyre_wear_high",
    "engine_overheat",
    "battery_low_soc",
    "drs_available",
    "drs_unavailable",
    "ptp_available",
    "frozen_order_cleared",
    "opponent_pit_exit",
    "opponent_position_change",
    "opponent_fast_lap",
    "watched_opponent_pitting",
    "watched_opponent_pit_exit",
    "watched_opponent_gap",
    "strategy_sector_advice",
    "pearl_overtake",
    "pearl_comeback",
    "pearl_fast_lap",
    "pearl_standard",
    "race_time_remaining",
    "race_laps_remaining",
    "race_start_grid_side",
    "driver_swap_detected",
    "driver_swap_15_min",
    "driver_swap_10_min",
    "driver_swap_5_min",
    "driver_swap_2_min",
    "driver_swap_pit_this_lap",
    "brake_wear_high",
    "damage_brake_wear",
    "damage_suspension_wear",
    "damage_summary",
    "tyre_monitor",
    "brake_wear",
    "fuel",
    "engine_monitor",
    "opponents",
    "pit_stops",
    "strategy",
    "push_now",
    "driver_swaps",
    "drs",
    "session_end",
    "race_start_announce",
})

LEGACY_COMMENTARY_EVENT_IDS = frozenset({
    "phase_changed",
    "weather_forecast",
})

CC_OWNED_PREFIXES = ("flags_", "penalty_", "rain_", "damage_", "multiclass_", "pearl_", "opponent_", "watched_", "drs_", "ptp_", "driver_swap_")


def is_cc_owned_event(event_id: str) -> bool:
    if event_id in CC_OWNED_EVENT_IDS:
        return True
    return any(event_id.startswith(prefix) for prefix in CC_OWNED_PREFIXES)


def is_legacy_commentary_allowed(event_id: str) -> bool:
    return event_id in LEGACY_COMMENTARY_EVENT_IDS


def is_ported(event_id: str) -> bool:
    return is_cc_owned_event(event_id)


def all_cc_owned_ids() -> frozenset[str]:
    return CC_OWNED_EVENT_IDS
