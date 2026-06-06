"""Tests splines de pista (Wave 5 — Task 19)."""

from src.intelligence.track_spline import get_track_manager


def test_spa_blanchimont_lookup():
    mgr = get_track_manager()
    corner = mgr.get_nearest_corner("Spa-Francorchamps", 4500)
    assert corner == "Blanchimont"


def test_get_by_distance():
    mgr = get_track_manager()
    pt = mgr.get_by_distance("monza", 5200)
    assert pt is not None
    assert pt.name == "Parabolica"


def test_unknown_track_returns_empty():
    mgr = get_track_manager()
    assert mgr.get_nearest_corner("Unknown Circuit", 1000) == ""
