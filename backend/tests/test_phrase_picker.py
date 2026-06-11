import pytest

from src.intelligence.phrase_picker import PhrasePicker, pick_variant


def test_pick_variant_splits_pipe():
    assert pick_variant("A|B|C", seed=0) in {"A", "B", "C"}


def test_pick_variant_single_string():
    assert pick_variant("solo", seed=0) == "solo"


def test_picker_loads_trigger_phrases():
    picker = PhrasePicker.load_bundle_defaults()
    msg = picker.trigger_phrase("fuel_critical", profile_id="standard", seed=1)
    assert msg
    assert "combustible" in msg.lower() or "gasolina" in msg.lower() or "fuel" in msg.lower()


def test_banned_robotic_prefixes_not_in_p0_keys():
    picker = PhrasePicker.load_bundle_defaults()
    banned = ("atención:", "alerta:", "mensaje:", "warning:")
    for key in ("fuel_critical", "fcy_active", "rain_increasing"):
        for profile in ("standard", "formal", "aggressive"):
            text = picker.trigger_phrase(key, profile_id=profile, seed=0).lower()
            assert text
            assert not any(text.lstrip().startswith(b) for b in banned), f"{key}/{profile}: {text}"


def test_spotter_phrase_tolerates_malformed_format_string():
    picker = PhrasePicker(
        spotter={"standard": {"hold_line": "Mantén {side"}},
        triggers={},
    )
    assert picker.spotter_phrase("hold_line", profile_id="standard") == "Mantén {side"
