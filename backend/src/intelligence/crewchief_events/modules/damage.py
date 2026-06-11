from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.phrase_picker import trigger_phrase_for_session
from src.intelligence.damage_report import (
    CRASH_LOW_SPEED_MS,
    CRASH_POST_IMPACT_WAIT_S,
    IMPACT_MAGNITUDE_MIN,
    IMPACT_SETTLE_S,
    PUNCTURE_DELAY_S,
    active_damage_items,
    aero_damage_level,
    count_flat_tyres,
    detect_crash_g,
    format_damage_status_message,
    player_speed_ms,
)

from ..base import CrewChiefEventModule
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class DamageEvent(CrewChiefEventModule):
    event_name = "damage"

    def __init__(self) -> None:
        self._last_impact_et = 0.0
        self._pending_impact_magnitude = 0.0
        self._impact_settle_at: float | None = None
        self._impact_settled = False
        self._puncture_batch_ready_at: float | None = None
        self._last_reported_fingerprint: tuple[str, ...] = ()
        self._last_reported_aero_level = 0
        self._crash_g_detected_at: float | None = None
        self._crash_active = False
        self._crash_started_at: float | None = None
        self._crash_retry_index = 0
        self._last_wear_poll_at = 0.0
        self._last_brake_wear_alert = 0.0
        self._last_suspension_wear_alert = 0.0

    def clear_state(self) -> None:
        self._last_impact_et = 0.0
        self._pending_impact_magnitude = 0.0
        self._impact_settle_at = None
        self._impact_settled = False
        self._puncture_batch_ready_at = None
        self._last_reported_fingerprint = ()
        self._last_reported_aero_level = 0
        self._reset_crash()
        self._last_wear_poll_at = 0.0
        self._last_brake_wear_alert = 0.0
        self._last_suspension_wear_alert = 0.0

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.session.get("damage_enabled", True):
            return []
        tick = ctx.current
        now = ctx.now_monotonic
        if bool(tick.get("in_pits") or tick.get("in_garage")):
            if self._crash_active or self._crash_g_detected_at is not None:
                self._reset_crash()
            return []

        messages: list[CrewChiefMessage] = []
        damage = self._eval_damage_status(tick, now)
        if damage:
            messages.append(damage)
        crash = self._eval_crash(tick, now)
        if crash:
            messages.append(crash)
        wear = self._eval_rest_wear(ctx, now)
        if wear:
            messages.append(wear)
        return messages

    def _eval_rest_wear(self, ctx: CrewChiefFrameContext, now: float) -> CrewChiefMessage | None:
        if now - self._last_wear_poll_at < 3.0:
            return None
        self._last_wear_poll_at = now

        strategy = ctx.strategy or {}
        brake = strategy.get("brake_wear") or {}
        if isinstance(brake, dict):
            max_brake = max(float(brake.get(k, 0) or 0) for k in ("fl", "fr", "rl", "rr"))
            if max_brake >= 80.0 and now - self._last_brake_wear_alert >= 120.0:
                self._last_brake_wear_alert = now
                fallback = render_template("brake_wear_high", {"wear": f"{max_brake:.0f}"})
                return self._message(
                    "damage_brake_wear",
                    trigger_phrase_for_session(ctx.session, "brake_wear_high", fallback),
                    CrewChiefPriority.NORMAL,
                )

        from src.services.lmu_api import get_additional_data

        garage = get_additional_data("garage_wear")
        suspension = garage.get("wearables", {}).get("suspension", [])
        if isinstance(suspension, list) and suspension:
            values = [float(x or 0) for x in suspension[:4]]
            if values:
                min_wear = min(values) * 100.0 if max(values) <= 1.0 else min(values)
                if min_wear <= 20.0 and now - self._last_suspension_wear_alert >= 120.0:
                    self._last_suspension_wear_alert = now
                    return self._message(
                        "damage_suspension_wear",
                        render_template("suspension_wear_high"),
                        CrewChiefPriority.NORMAL,
                    )
        return None

    def _track_puncture_batch(self, tick: dict, now: float) -> bool:
        if count_flat_tyres(tick) > 0:
            if self._puncture_batch_ready_at is None:
                self._puncture_batch_ready_at = now + PUNCTURE_DELAY_S
            return self._puncture_batch_ready_at is not None and now >= self._puncture_batch_ready_at
        self._puncture_batch_ready_at = None
        return False

    def _track_impact(self, tick: dict, now: float) -> bool:
        impact_et = float(tick.get("last_impact_et", 0) or 0)
        magnitude = float(tick.get("last_impact_magnitude", 0) or 0)
        if (
            impact_et > 0
            and impact_et != self._last_impact_et
            and magnitude >= IMPACT_MAGNITUDE_MIN
        ):
            self._last_impact_et = impact_et
            self._pending_impact_magnitude = magnitude
            self._impact_settle_at = now + IMPACT_SETTLE_S
            self._impact_settled = False
        if self._impact_settle_at is None or self._impact_settled:
            return False
        if now < self._impact_settle_at:
            return False
        self._impact_settled = True
        return True

    def _eval_damage_status(self, tick: dict, now: float) -> CrewChiefMessage | None:
        impact_ready = self._track_impact(tick, now)
        puncture_ready = self._track_puncture_batch(tick, now)
        aero_level = aero_damage_level(tick)
        aero_ready = (
            aero_level > self._last_reported_aero_level
            and (self._impact_settle_at is None or self._impact_settled)
        )

        if not impact_ready and not puncture_ready and not aero_ready:
            return None

        items = active_damage_items(
            tick,
            include_impact=impact_ready,
            impact_magnitude=self._pending_impact_magnitude,
        )
        if not puncture_ready:
            items = [item for item in items if item not in ("puncture", "multiple_punctures")]
        if not items:
            if aero_ready:
                self._last_reported_aero_level = aero_level
            return None

        fingerprint = tuple(sorted(items))
        if fingerprint == self._last_reported_fingerprint:
            if aero_ready:
                self._last_reported_aero_level = aero_level
            return None

        if puncture_ready and not impact_ready and items == ["puncture"]:
            text = format_damage_status_message(tick, items)
        else:
            text = format_damage_status_message(
                tick,
                items,
                impact_magnitude=self._pending_impact_magnitude,
            )
        if not text:
            return None

        self._last_reported_fingerprint = fingerprint
        self._last_reported_aero_level = max(self._last_reported_aero_level, aero_level)
        priority = (
            CrewChiefPriority.CRITICAL
            if "¿Estás bien?" in text or "grave" in text.lower()
            else CrewChiefPriority.IMPORTANT
        )
        return self._message("damage_status", text, priority)

    def _eval_crash(self, tick: dict, now: float) -> CrewChiefMessage | None:
        if detect_crash_g(tick) and self._crash_g_detected_at is None:
            self._crash_g_detected_at = now

        if self._crash_g_detected_at is not None and not self._crash_active:
            elapsed_since_g = now - self._crash_g_detected_at
            if (
                elapsed_since_g >= CRASH_POST_IMPACT_WAIT_S
                and player_speed_ms(tick) < CRASH_LOW_SPEED_MS
            ):
                self._crash_active = True
                self._crash_started_at = now
                self._crash_retry_index = 0
            elif elapsed_since_g > 15.0 and player_speed_ms(tick) >= CRASH_LOW_SPEED_MS:
                self._crash_g_detected_at = None

        if not self._crash_active or self._crash_started_at is None:
            return None

        elapsed = now - self._crash_started_at
        retry_delays = (0.0, 8.0, 16.0)
        max_retries = 3
        idx = self._crash_retry_index
        if idx >= max_retries or elapsed < retry_delays[idx]:
            return None

        self._crash_retry_index += 1
        if self._crash_retry_index >= max_retries:
            self._reset_crash()

        return self._message(
            f"damage_crash_ok_{idx}",
            render_template(f"damage_crash_ok_{idx}"),
            CrewChiefPriority.CRITICAL,
            play_even_when_silenced=True,
        )

    def _reset_crash(self) -> None:
        self._crash_g_detected_at = None
        self._crash_active = False
        self._crash_started_at = None
        self._crash_retry_index = 0

    @staticmethod
    def _message(
        event_id: str,
        text: str,
        priority: CrewChiefPriority,
        *,
        play_even_when_silenced: bool = False,
    ) -> CrewChiefMessage:
        return CrewChiefMessage(
            event_id=event_id,
            text=text,
            priority=priority,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=10000 if priority == CrewChiefPriority.CRITICAL else 6000,
            play_even_when_silenced=play_even_when_silenced or priority == CrewChiefPriority.CRITICAL,
        )
