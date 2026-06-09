from src.intelligence.crewchief_events.game_state import _enrich_cc_frame


def test_enrich_maps_legacy_frozen_order_flag():
    enriched = _enrich_cc_frame({"frozen_order": True, "session_type": "race"}, {})
    assert enriched["frozen_order_active"] is True
    assert enriched["frozen_order_message"]


def test_enrich_merges_strategy_competitors_for_multiclass():
    enriched = _enrich_cc_frame(
        {"player_class": "GT3", "session_type": "race"},
        {
            "competitors": [
                {
                    "driver_index": 8,
                    "driver_class": "Hypercar",
                    "gap_to_player": -1.0,
                }
            ]
        },
    )
    assert enriched["competitors"][0]["class_name"] == "Hypercar"
    assert enriched["competitors"][0]["relative_speed_ms"] == 8.0
