from __future__ import annotations


def compute_grid_side(
    competitors: list[dict],
    *,
    player_index: int,
    player_forward: tuple[float, float],
    adjacent_indices: list[int] | None = None,
) -> str | None:
    fwd_x, fwd_z = player_forward
    idx_set = set(adjacent_indices) if adjacent_indices is not None else None
    left_count = 0
    right_count = 0
    for comp in competitors:
        if not isinstance(comp, dict):
            continue
        comp_idx = comp.get("driver_index")
        if comp_idx is None:
            continue
        if idx_set is not None and int(comp_idx) not in idx_set:
            continue
        dx = float(comp.get("world_x") or comp.get("pos_x") or 0.0)
        dz = float(comp.get("world_z") or comp.get("pos_z") or 0.0)
        lateral = fwd_x * dz - fwd_z * dx
        if lateral < -0.5:
            left_count += 1
        elif lateral > 0.5:
            right_count += 1
    if left_count and right_count:
        return "both"
    if left_count:
        return "left"
    if right_count:
        return "right"
    return None


def adjacent_standing_indices(competitors: list[dict], player_standing: int) -> list[int]:
    indices: list[int] = []
    for comp in competitors:
        if not isinstance(comp, dict):
            continue
        pos = comp.get("position") or comp.get("standing_position")
        if pos is None:
            continue
        if abs(int(pos) - int(player_standing)) <= 1:
            idx = comp.get("driver_index")
            if idx is not None:
                indices.append(int(idx))
    return indices
