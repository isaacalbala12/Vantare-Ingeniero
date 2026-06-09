from src.intelligence.crewchief_events.modules.strategy import StrategyEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext
from src.intelligence.sector_analysis import SectorInsight


def test_strategy_sector_message_throttled(monkeypatch):
    module = StrategyEvent()

    def fake_analyze(fuel_raw, fuel_last, track, track_len, threshold=0.05):
        return [SectorInsight(1000.0, "Les Combes", 0.1, "defender")]

    monkeypatch.setattr("src.intelligence.crewchief_events.modules.strategy.analyze_sectors", fake_analyze)

    curr = {
        "track_name": "Spa",
        "session_type_int": 10,
        "fuel_per_lap_raw": [1.0],
        "fuel_per_lap_last": [0.9],
        "track_length": 7000,
    }
    strategy = {"track_length": 7000}
    session = {"phase": "race", "session_type_int": 10, "verbosity_level": "detailed", "enable_strategy_messages": True}
    ctx = CrewChiefFrameContext(
        previous=curr,
        current=curr,
        strategy=strategy,
        session=session,
        now_monotonic=100.0,
    )
    m1 = module.evaluate(ctx)
    m2 = module.evaluate(CrewChiefFrameContext(curr, curr, strategy, session, 110.0))
    assert m1
    assert not m2
