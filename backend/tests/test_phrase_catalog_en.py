from src.intelligence.phrase_catalog import PhraseCatalog
from src.intelligence.phrase_picker import PhrasePicker


def test_loads_english_spotter_left():
    catalog = PhraseCatalog.load(locale="en")
    text = str(catalog.spotter["standard"]["hold_line"]).lower()
    assert "left" in text or "side" in text


def test_english_spotter_has_same_keys_as_spanish():
    es = PhraseCatalog.load(locale="es")
    en = PhraseCatalog.load(locale="en")
    assert set(en.spotter.keys()) == set(es.spotter.keys())
    for profile in es.spotter:
        assert set(en.spotter[profile].keys()) == set(es.spotter[profile].keys())


def test_english_triggers_have_existing_spanish_keys():
    es = PhraseCatalog.load(locale="es")
    en = PhraseCatalog.load(locale="en")
    missing = set(es.triggers.keys()) - set(en.triggers.keys())
    assert missing == set()
    for key in es.triggers:
        assert set(en.triggers[key].keys()) == set(es.triggers[key].keys())


def test_phrase_picker_loads_english_catalog():
    picker = PhrasePicker.load_defaults(locale="en")
    assert "car" in picker.spotter_phrase("hold_line", profile_id="standard", side="left").lower()
    assert "fuel" in picker.trigger_phrase("fuel_critical", profile_id="standard").lower()
