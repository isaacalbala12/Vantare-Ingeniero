"""Tests de la máquina de estados del spotter."""

from __future__ import annotations

import time

from src.intelligence.spotter_geometry import LateralProximity
from src.intelligence.spotter_state import SideState, SpotterStateMachine


def _hit(side: str, lateral: float = 2.0, idx: int = 1) -> LateralProximity:
    return LateralProximity(
        driver_index=idx,
        driver_class="GT3",
        driver_name="Rival",
        lateral_m=lateral,
        side=side,
        distance_m=3.0,
    )


class TestSpotterStateMachine:
    def test_enter_emits_once(self):
        sm = SpotterStateMachine(clear_delay_s=0.1)
        t0 = 1000.0
        first = sm.update([_hit("derecha")], player_class="GT3", threshold_m=3.0, now=t0)
        assert len(first) == 1
        assert "derecha" in first[0].message.lower()

        for i in range(10):
            later = sm.update([_hit("derecha")], player_class="GT3", threshold_m=3.0, now=t0 + i * 0.05)
            assert later == []

    def test_clear_after_delay(self):
        sm = SpotterStateMachine(clear_delay_s=0.2)
        t0 = 2000.0
        sm.update([_hit("izquierda")], player_class="GT3", threshold_m=3.0, now=t0)
        sm.update([], player_class="GT3", threshold_m=3.0, now=t0 + 0.05)
        cleared = sm.update([], player_class="GT3", threshold_m=3.0, now=t0 + 0.3)
        assert any(tr.is_clear for tr in cleared)
        assert any("despejado" in tr.message.lower() for tr in cleared)

    def test_hysteresis_avoids_flicker(self):
        sm = SpotterStateMachine(clear_delay_s=1.0, exit_hysteresis=1.25)
        t0 = 3000.0
        sm.update([_hit("derecha", lateral=2.5)], player_class="GT3", threshold_m=3.0, now=t0)
        border = _hit("derecha", lateral=3.2)
        flicker = sm.update([border], player_class="GT3", threshold_m=3.0, now=t0 + 0.05)
        assert flicker == []
        assert sm._right_state != SideState.CLEAR

    def test_three_wide_single_alert(self):
        sm = SpotterStateMachine(clear_delay_s=0.1)
        t0 = 4000.0
        hits = [_hit("izquierda", idx=1), _hit("derecha", idx=2)]
        first = sm.update(hits, player_class="GT3", threshold_m=3.0, now=t0)
        assert len(first) == 1
        assert first[0].is_three_wide
        assert "medio" in first[0].message.lower() or "tres" in first[0].message.lower()

        repeat = sm.update(hits, player_class="GT3", threshold_m=3.0, now=t0 + 0.05)
        assert repeat == []

    def test_clear_all_when_both_sides_clear_together(self):
        sm = SpotterStateMachine(clear_delay_s=0.15)
        t0 = 5000.0
        hits = [_hit("izquierda", idx=1), _hit("derecha", idx=2)]
        sm.update(hits, player_class="GT3", threshold_m=3.0, now=t0)
        sm.update([], player_class="GT3", threshold_m=3.0, now=t0 + 0.05)
        cleared = sm.update([], player_class="GT3", threshold_m=3.0, now=t0 + 0.25)
        clear_msgs = [tr for tr in cleared if tr.is_clear]
        assert len(clear_msgs) == 1
        assert clear_msgs[0].is_clear_all
        assert "alrededor" in clear_msgs[0].message.lower() or "lados" in clear_msgs[0].message.lower()

    def test_three_wide_exit_immediate_clear_and_reannounce(self):
        sm = SpotterStateMachine(clear_delay_s=0.15, hold_repeat_s=3.0)
        t0 = 6000.0
        both = [_hit("izquierda", idx=1), _hit("derecha", idx=2)]
        sm.update(both, player_class="GT3", threshold_m=3.0, now=t0)
        exit_tw = sm.update([_hit("izquierda", idx=1)], player_class="GT3", threshold_m=3.0, now=t0 + 0.1)
        clears = [tr for tr in exit_tw if tr.is_clear]
        assert len(clears) == 1
        assert clears[0].side == "derecha"
        assert sm.update([_hit("izquierda", idx=1)], player_class="GT3", threshold_m=3.0, now=t0 + 2.9) == []
        reenter = sm.update([_hit("izquierda", idx=1)], player_class="GT3", threshold_m=3.0, now=t0 + 3.1)
        assert any("izquierda" in tr.message.lower() for tr in reenter)
        assert not any(tr.is_clear for tr in reenter)

    def test_clear_uses_personality_phrase(self):
        sm = SpotterStateMachine(clear_delay_s=0.15)
        t0 = 7000.0
        sm.update([_hit("derecha")], player_class="GT3", threshold_m=3.0, now=t0)
        sm.update([], player_class="GT3", threshold_m=3.0, now=t0 + 0.05)
        cleared = sm.update([], player_class="GT3", threshold_m=3.0, now=t0 + 0.25)
        assert any(tr.is_clear and tr.audio_priority == 2 for tr in cleared)
        assert any("despejado" in tr.message.lower() for tr in cleared)

    def test_multiclass_message_on_enter(self):
        sm = SpotterStateMachine(clear_delay_s=0.1)
        hit = LateralProximity(
            driver_index=42,
            driver_class="Hypercar",
            driver_name="V",
            lateral_m=2.0,
            side="derecha",
            distance_m=2.0,
        )
        out = sm.update([hit], player_class="GT3", threshold_m=3.0, now=5000.0)
        assert len(out) == 1
        assert "hypercar" in out[0].message.lower() or "coche" in out[0].message.lower()

    def test_still_there_repeats_every_hold_repeat(self):
        sm = SpotterStateMachine(
            clear_delay_s=0.15,
            hold_repeat_s=3.0,
            still_there_enabled=True,
        )
        t0 = 1000.0
        sm.update([_hit("derecha")], player_class="GT3", threshold_m=3.0, now=t0)
        assert sm.update([_hit("derecha")], player_class="GT3", threshold_m=3.0, now=t0 + 2.9) == []
        first_still = sm.update([_hit("derecha")], player_class="GT3", threshold_m=3.0, now=t0 + 3.01)
        assert any("sigue" in tr.message.lower() for tr in first_still)
        second_still = sm.update([_hit("derecha")], player_class="GT3", threshold_m=3.0, now=t0 + 6.01)
        assert any("sigue" in tr.message.lower() for tr in second_still)
