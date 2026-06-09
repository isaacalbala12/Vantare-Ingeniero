"""Tests VerbosityController."""

from src.intelligence.verbosity_controller import VerbosityController, VerbosityLevel


def test_set_level_normalizes():
    vc = VerbosityController("detailed")
    ok, msg = vc.set_level("silent")
    assert ok is True
    assert vc.level == VerbosityLevel.SILENT
    assert "silencioso" in msg


def test_silent_blocks_medium_events():
    vc = VerbosityController("silent")
    assert vc.should_emit_priority("CRITICAL") is True
    assert vc.should_emit_priority("HIGH") is False
    assert vc.should_emit_priority("MEDIUM") is False


def test_normal_allows_medium_plus():
    vc = VerbosityController("normal")
    assert vc.should_emit_priority("MEDIUM") is True
    assert vc.should_emit_priority("LOW") is False


def test_detailed_allows_low():
    vc = VerbosityController("detailed")
    assert vc.should_emit_priority("LOW") is True


def test_max_pearls_silent_zero():
    vc = VerbosityController("silent")
    assert vc.max_pearls_per_race == 0


def test_auto_verbosity_drops_low_priority_in_close_traffic():
    controller = VerbosityController(level="detailed")
    controller.update_auto_context(
        {
            "speed_ms": 55.0,
            "session_type": "race",
            "time_gap_car_ahead": 0.8,
            "time_gap_car_behind": 1.1,
        },
        {"phase": "RACE"},
    )

    assert controller.should_emit_priority("LOW") is False
    assert controller.should_emit_priority("HIGH") is True


def test_speak_only_when_spoken_to_blocks_regular_engineer_messages():
    controller = VerbosityController(level="detailed")
    controller.set_speak_only_when_spoken_to(True)

    assert controller.should_emit_crewchief_category("engineer", "NORMAL", False) is False
    assert controller.should_emit_crewchief_category("voice_response", "LOW", False) is True
    assert controller.should_emit_crewchief_category("spotter", "LOW", False) is False
    assert controller.should_emit_crewchief_category("proximity", "CRITICAL", False) is False
    assert controller.should_emit_crewchief_category("engineer", "CRITICAL", True) is False
