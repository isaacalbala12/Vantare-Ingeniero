from src.intelligence.crewchief_events.playback import map_message_to_alert
from src.intelligence.crewchief_events.types import (
    CrewChiefChannel,
    CrewChiefMessage,
    CrewChiefPriority,
)
from src.models.messages import AlertMessage


def test_map_critical_message_to_alert_payload():
    msg = CrewChiefMessage(
        event_id="damage_major",
        text="Daño grave.",
        priority=CrewChiefPriority.CRITICAL,
        channel=CrewChiefChannel.ENGINEER,
        ttl_ms=3000,
        play_even_when_silenced=True,
        validation_key="damage:major",
    )

    alert = map_message_to_alert(msg)

    assert isinstance(alert, AlertMessage)
    assert alert.event == "alert"
    assert alert.category == "engineer"
    assert alert.audio_priority == "4"
    assert alert.ttl == 3
    assert alert.payload["event_id"] == "damage_major"
    assert alert.payload["play_even_when_silenced"] is True
    assert alert.payload["validation_key"] == "damage:major"


def test_map_spotter_message_uses_spotter_category():
    msg = CrewChiefMessage(
        event_id="car_right",
        text="Coche a la derecha.",
        priority=CrewChiefPriority.CRITICAL,
        channel=CrewChiefChannel.SPOTTER,
        ttl_ms=1000,
    )

    alert = map_message_to_alert(msg)

    assert alert.category == "spotter"
    assert alert.payload["queue_class"] == "IMMEDIATE"


def test_emit_crewchief_respects_speak_only_mode():
    from src.intelligence.engine import IntelligenceEngine

    sent = []
    engine = IntelligenceEngine(broadcast_callback=sent.append)
    engine.verbosity.set_speak_only_when_spoken_to(True)

    blocked = CrewChiefMessage(
        event_id="position_loss",
        text="Bajaste a P4.",
        priority=CrewChiefPriority.NORMAL,
        channel=CrewChiefChannel.ENGINEER,
    )
    engine.emit_crewchief_messages([blocked])
    assert sent == []

    allowed = CrewChiefMessage(
        event_id="damage_are_you_ok",
        text="¿Estás bien?",
        priority=CrewChiefPriority.CRITICAL,
        channel=CrewChiefChannel.ENGINEER,
        play_even_when_silenced=True,
    )
    engine.emit_crewchief_messages([allowed])
    assert sent == []
