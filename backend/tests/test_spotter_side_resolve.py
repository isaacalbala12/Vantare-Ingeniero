from src.intelligence.spotter_geometry import LateralProximity, resolve_proximity_side


def _hit(side: str, lateral: float, idx: int = 1) -> LateralProximity:
    return LateralProximity(
        driver_index=idx,
        driver_class="GT3",
        driver_name="Rival",
        lateral_m=lateral,
        side=side,
        distance_m=2.0,
    )


def test_resolve_side_prefers_confident_path():
    path = _hit("derecha", 2.6)
    cart = _hit("izquierda", 2.0)
    assert resolve_proximity_side(path, cart, None, cart.side) == "derecha"


def test_resolve_side_uses_cart_vel_consensus_when_path_weak():
    path = _hit("derecha", 0.4)
    cart = _hit("izquierda", 2.0)
    vel = _hit("izquierda", 2.1)
    assert resolve_proximity_side(path, cart, vel, path.side) == "izquierda"
