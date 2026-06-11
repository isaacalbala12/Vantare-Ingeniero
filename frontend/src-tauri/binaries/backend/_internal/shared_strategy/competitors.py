from shared_strategy.models import TelemetryFrame, CompetitorTrackerState, CompetitorHistoryState, CompetitorPace

def track_competitor_pace(
    telemetry: TelemetryFrame,
    state: CompetitorTrackerState,
    player_index: int = 0
) -> tuple[list[CompetitorPace], CompetitorTrackerState]:
    new_state = state.model_copy(deep=True)
    
    # 1. Obtener ritmo del jugador como referencia de gap
    player_pace = telemetry.lap_time_previous if telemetry.lap_time_previous > 0 else 90.0
    player_lap = telemetry.lap_number
    player_time_into = (telemetry.lap_distance / telemetry.speed) if telemetry.speed > 1.0 else 0.0
    
    paces_list = []
    
    for comp in telemetry.competitors:
        idx = comp.driver_index
        
        # Recuperar o inicializar historial del rival
        if idx not in new_state.competitors:
            new_state.competitors[idx] = CompetitorHistoryState(
                stint_laps_done=comp.lap_number,
                last_in_pits=comp.in_pits
            )
            
        state_comp = new_state.competitors[idx]
        
        # 2. Detección de nueva vuelta del rival
        last_lap = state_comp.stint_laps_done
        current_lap = comp.lap_number
        
        if current_lap > last_lap and last_lap > 0:
            # Registrar tiempo de la vuelta completada
            lap_time = comp.lap_time_previous if comp.lap_time_previous > 0 else player_pace
            state_comp.lap_time_history = state_comp.lap_time_history[-4:] + [lap_time]
            
            # Solo actualizar promedio si no fue vuelta de boxes
            if not comp.in_pits and not state_comp.last_in_pits:
                state_comp.average_lap = sum(state_comp.lap_time_history) / len(state_comp.lap_time_history)
                state_comp.best_lap = min(state_comp.lap_time_history)
                
            # Registrar historial de combustible
            state_comp.fuel_history.append((last_lap, comp.fuel_capacity_fraction))
            state_comp.fuel_history = state_comp.fuel_history[-10:]
            
            state_comp.stint_laps_done = current_lap
            
        elif last_lap == 0:
            state_comp.stint_laps_done = current_lap
            
        # 3. Detección de entrada a pits
        if comp.in_pits and not state_comp.last_in_pits:
            state_comp.num_pit_stops += 1
            
        state_comp.last_in_pits = comp.in_pits
        
        # 4. Estimar consumo y stint del rival en base a su combustible
        est_stint = 30  # Fallback estándar
        if len(state_comp.fuel_history) >= 2:
            # Calcular diferencia de fracción de la última vuelta
            _, f_prev = state_comp.fuel_history[-2]
            _, f_curr = state_comp.fuel_history[-1]
            used_frac = f_prev - f_curr
            if used_frac > 0.005:
                # stint total teórico
                est_stint = int(1.0 / used_frac)
                
        # 5. Calcular gap de tiempo en pista respecto al jugador
        lap_diff = current_lap - player_lap
        comp_time_into = comp.estimated_time_into_lap if comp.estimated_time_into_lap > 0.1 else (comp.lap_distance / comp.speed if comp.speed > 1.0 else 0.0)
        
        # Fórmula estándar de motorsport para gap espacial acumulado
        gap = (comp_time_into - player_time_into) + (lap_diff * player_pace)
        
        # Ensamblar consejo de ritmo
        pace_advice = CompetitorPace(
            driver_index=idx,
            driver_name=comp.driver_name,
            driver_class=comp.driver_class,
            standing_position=comp.standing_position,
            class_position=comp.class_position,
            lap_number=current_lap,
            lap_distance=comp.lap_distance,
            gap_to_player=gap,
            best_lap=state_comp.best_lap if state_comp.best_lap > 0.1 else comp.lap_time_best,
            average_lap=state_comp.average_lap if state_comp.average_lap > 0.1 else pace_advice_best_fallback(comp.lap_time_best),
            estimated_stint_length=est_stint,
            num_pit_stops=state_comp.num_pit_stops,
            in_pits=comp.in_pits
        )
        paces_list.append(pace_advice)
        
    return paces_list, new_state

def pace_advice_best_fallback(best_lap: float) -> float:
    return best_lap if best_lap > 0.1 else 90.0


MAX_MONITORED = 3


def _normalize_class(name: str) -> str:
    n = (name or "").upper().replace(" ", "")
    if n in ("HY", "HYPERCAR", "LMH"):
        return "HYPERCAR"
    return n


def filter_by_class(paces: list[CompetitorPace], driver_class: str) -> list[CompetitorPace]:
    target = _normalize_class(driver_class)
    return [p for p in paces if _normalize_class(p.driver_class) == target or target in _normalize_class(p.driver_class)]


def classify_gap(gap_seconds: float) -> str:
    """Clasifica gap: close (<5s), mid (5-30s), far (>30s)."""
    abs_gap = abs(gap_seconds)
    if abs_gap < 5.0:
        return "close"
    if abs_gap < 30.0:
        return "mid"
    return "far"


def get_nearest_in_class(paces: list[CompetitorPace], driver_class: str) -> CompetitorPace | None:
    filtered = filter_by_class(paces, driver_class)
    if not filtered:
        return None
    return min(filtered, key=lambda p: abs(p.gap_to_player))


def _track_sort_key(p: CompetitorPace) -> tuple[int, float]:
    return (p.lap_number, p.lap_distance)


def order_on_track(paces: list[CompetitorPace]) -> list[CompetitorPace]:
    """Orden en pista: más vueltas y mayor distancia en vuelta = más adelante."""
    ordered = sorted(paces, key=_track_sort_key, reverse=True)
    for i, p in enumerate(ordered, start=1):
        p.track_position = i
    return ordered


def order_in_classification(paces: list[CompetitorPace]) -> list[CompetitorPace]:
    """Orden por clasificación oficial (standing_position)."""
    return sorted(paces, key=lambda p: p.standing_position if p.standing_position > 0 else 9999)


def start_monitoring(state: CompetitorTrackerState, driver_index: int) -> CompetitorTrackerState:
    new_state = state.model_copy(deep=True)
    if driver_index in new_state.monitored:
        return new_state
    if len(new_state.monitored) >= MAX_MONITORED:
        new_state.monitored = new_state.monitored[1:] + [driver_index]
    else:
        new_state.monitored.append(driver_index)
    return new_state


def stop_monitoring(state: CompetitorTrackerState, driver_index: int) -> CompetitorTrackerState:
    new_state = state.model_copy(deep=True)
    new_state.monitored = [i for i in new_state.monitored if i != driver_index]
    return new_state


def get_monitored(state: CompetitorTrackerState) -> list[int]:
    return list(state.monitored)


def _pace_snapshot(p: CompetitorPace) -> dict:
    return {
        "in_pits": p.in_pits,
        "standing_position": p.standing_position,
        "gap_to_player": round(p.gap_to_player, 2),
    }


def evaluate_monitored_events(
    paces: list[CompetitorPace],
    state: CompetitorTrackerState,
) -> tuple[list[dict], CompetitorTrackerState]:
    """Detecta cambios en rivales monitorizados: boxes, posición, gap."""
    new_state = state.model_copy(deep=True)
    events: list[dict] = []
    pace_by_idx = {p.driver_index: p for p in paces}

    for idx in list(new_state.monitored):
        pace = pace_by_idx.get(idx)
        if pace is None:
            continue
        snap = _pace_snapshot(pace)
        prev = new_state.monitor_snapshots.get(idx)
        if prev:
            if pace.in_pits and not prev.get("in_pits"):
                events.append({"type": "pit_entry", "driver_index": idx, "driver_name": pace.driver_name})
            elif not pace.in_pits and prev.get("in_pits"):
                events.append({"type": "pit_exit", "driver_index": idx, "driver_name": pace.driver_name})
            if pace.standing_position != prev.get("standing_position"):
                events.append({
                    "type": "position_change",
                    "driver_index": idx,
                    "driver_name": pace.driver_name,
                    "from": prev.get("standing_position"),
                    "to": pace.standing_position,
                })
            gap_delta = pace.gap_to_player - float(prev.get("gap_to_player", 0))
            if abs(gap_delta) >= 0.5:
                events.append({
                    "type": "gap_change",
                    "driver_index": idx,
                    "driver_name": pace.driver_name,
                    "delta": round(gap_delta, 2),
                })
        new_state.monitor_snapshots[idx] = snap

    return events, new_state
