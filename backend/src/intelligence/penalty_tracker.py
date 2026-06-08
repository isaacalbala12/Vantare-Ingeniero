"""State machine de countdown de penalización estilo Crew Chief (LMU-13)."""

from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.immediate_alert import ImmediateAlert
from shared_telemetry.lmu_fields import lmu_sector_number


class PenaltyTracker:
    """Cuenta regresiva 3/2/1/pit-now desde mNumPenalties."""

    def __init__(self) -> None:
        self.reset_session()

    def reset_session(self) -> None:
        self._state = "CLEAR"
        self._penalty_lap = -1
        self._last_num = 0
        self._pit_now_played = False
        self._disqualified_played = False
        self._not_served_played = False
        self._announced_3 = False
        self._announced_2 = False
        self._announced_1 = False
        self._was_in_pits = False
        self._last_cut_track_steps = 0
        self._last_cut_track_at = 0.0

    def evaluate_cut_track(self, track_limits_steps: int, now: float) -> ImmediateAlert | None:
        """Avisos de límites de pista (mTrackLimitsSteps) con cooldown 30s estilo CC."""
        steps = int(track_limits_steps or 0)
        if steps <= 0:
            self._last_cut_track_steps = 0
            return None
        if steps <= self._last_cut_track_steps:
            return None
        if self._last_cut_track_at > 0 and (now - self._last_cut_track_at) < 30.0:
            self._last_cut_track_steps = steps
            return None

        level = min(4, steps)
        self._last_cut_track_steps = steps
        self._last_cut_track_at = now
        priority = "HIGH" if level >= 3 else "MEDIUM"
        return ImmediateAlert(
            "cut_track_warning",
            render_template("cut_track_warning", {"level": level}),
            priority,
            "penalty",
        )

    def evaluate(
        self,
        num_penalties: int,
        lap: int,
        m_sector: int,
        in_pits: bool,
    ) -> ImmediateAlert | None:
        sector = lmu_sector_number(m_sector)

        if num_penalties < self._last_num and self._last_num > 0:
            self.reset_session()
            self._last_num = num_penalties
            return ImmediateAlert(
                "penalty_served",
                render_template("penalty_served"),
                "MEDIUM",
                "penalty",
            )

        if num_penalties > self._last_num:
            was_active = self._state == "COUNTDOWN"
            self._state = "COUNTDOWN"
            self._penalty_lap = lap
            self._pit_now_played = False
            self._disqualified_played = False
            self._not_served_played = False
            self._announced_2 = False
            self._announced_1 = False
            self._announced_3 = False
            self._last_num = num_penalties
            msg = render_template("penalty_new", {"repeat": was_active})
            return ImmediateAlert("penalty_new", msg, "HIGH", "penalty")

        self._last_num = num_penalties

        if self._state != "COUNTDOWN" or num_penalties <= 0:
            if num_penalties == 0:
                self.reset_session()
            self._was_in_pits = in_pits
            return None

        if self._was_in_pits and not in_pits and not self._not_served_played:
            self._not_served_played = True
            self._was_in_pits = in_pits
            return ImmediateAlert(
                "penalty_not_served",
                render_template("penalty_not_served"),
                "HIGH",
                "penalty",
            )
        self._was_in_pits = in_pits

        laps_since = lap - self._penalty_lap

        if laps_since >= 3 and not self._disqualified_played and not in_pits:
            self._disqualified_played = True
            return ImmediateAlert(
                "penalty_disqualified",
                render_template("penalty_disqualified"),
                "CRITICAL",
                "penalty",
            )

        if laps_since >= 2 and sector == 3 and not self._pit_now_played and not in_pits:
            self._pit_now_played = True
            return ImmediateAlert(
                "penalty_pit_now",
                render_template("penalty_pit_now"),
                "CRITICAL",
                "penalty",
            )

        if laps_since == 2 and not in_pits and not self._announced_2:
            self._announced_2 = True
            return ImmediateAlert(
                "penalty_2_laps",
                render_template("penalty_2_laps"),
                "HIGH",
                "penalty",
            )

        if laps_since == 1 and not in_pits and not self._announced_1:
            self._announced_1 = True
            return ImmediateAlert(
                "penalty_1_lap",
                render_template("penalty_1_lap"),
                "CRITICAL",
                "penalty",
            )

        return None
