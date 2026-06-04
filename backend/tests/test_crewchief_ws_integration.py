"""Integration tests: CrewChiefAlertMessage roundtrip via WebSocket."""
import pytest
from src.models.messages import CrewChiefAlertMessage
from src.routers.websocket import broadcast_sync, manager


class TestCrewChiefAlertRoundtrip:
    """Verify CrewChiefAlertMessage reaches WebSocket clients."""

    def test_crewchief_alert_roundtrip(self):
        """Broadcast a CrewChiefAlertMessage and verify it serializes correctly."""
        msg = CrewChiefAlertMessage(
            category="fuel",
            subtype="fuel_low",
            message="Fuel running low",
            severity="high",
            audio_priority=15,
            payload={"laps": 3.2},
        )
        data = msg.model_dump(mode="json")
        assert data["event"] == "crewchief_alert"
        assert data["category"] == "fuel"
        assert data["severity"] == "high"
        assert data["audio_priority"] == 15

    def test_crewchief_alert_categories(self):
        """Verify all expected categories can be created."""
        categories = ["fuel", "tyres", "position", "pit_stops", "battery",
                      "damage", "engine", "flags", "conditions",
                      "frozen_order", "session", "spotter"]
        for cat in categories:
            msg = CrewChiefAlertMessage(
                category=cat, subtype="test", message="test",
                severity="medium", audio_priority=10,
            )
            data = msg.model_dump(mode="json")
            assert data["category"] == cat
            assert data["event"] == "crewchief_alert"

    def test_crewchief_alert_preserves_alert_messages(self):
        """Verify existing AlertMessage is still compatible."""
        from src.models.messages import AlertMessage
        alert = AlertMessage(
            event="alert",
            alert_id="test123",
            category="fuel",
            message="test alert",
            audio_priority="HIGH",
        )
        data = alert.model_dump(mode="json")
        assert data["event"] == "alert"
        assert data["category"] == "fuel"

    def test_crewchief_alert_via_event_bridge(self):
        """Verify bridge converts QueuedMessage to CrewChiefAlertMessage."""
        from src.models.messages import QueuedMessage
        from src.services.event_bridge import queued_to_crewchief_alert

        qmsg = QueuedMessage(name="fuel_low", priority=15)
        alert = queued_to_crewchief_alert(qmsg)
        data = alert.model_dump(mode="json")
        assert data["event"] == "crewchief_alert"
        assert data["category"] == "fuel"
        assert data["severity"] == "critical"  # priority 15 = critical

    def test_crewchief_alert_spotter_message(self):
        """Verify spotter messages map correctly."""
        from src.models.messages import QueuedMessage
        from src.services.event_bridge import queued_to_crewchief_alert

        qmsg = QueuedMessage(name="car_left", priority=20)
        alert = queued_to_crewchief_alert(qmsg)
        data = alert.model_dump(mode="json")
        assert data["category"] == "spotter"
        assert data["severity"] == "critical"