import math

def linear_interp(x: float, x1: float, y1: float, x2: float, y2: float) -> float:
    if x2 == x1:
        return y1
    return y1 + (x - x1) * (y2 - y1) / (x2 - x1)

def binary_search_higher_column(arr: list, target: float) -> int:
    if not arr:
        return -1
    low = 0
    high = len(arr) - 1
    
    def get_dist(item) -> float:
        if hasattr(item, 'distance'):
            return item.distance
        return item[0]

    if get_dist(arr[high]) < target:
        return high
    
    ans = -1
    while low <= high:
        mid = (low + high) // 2
        if get_dist(arr[mid]) >= target:
            ans = mid
            high = mid - 1
        else:
            low = mid + 1
    return ans

def binary_search_lower_column(arr: list, target: float) -> int:
    if not arr:
        return -1
    low = 0
    high = len(arr) - 1
    
    def get_dist(item) -> float:
        if hasattr(item, 'distance'):
            return item.distance
        return item[0]

    if get_dist(arr[0]) > target:
        return 0
        
    ans = -1
    while low <= high:
        mid = (low + high) // 2
        if get_dist(arr[mid]) <= target:
            ans = mid
            low = mid + 1
        else:
            high = mid - 1
    return ans

def delta_telemetry(delta_arr: list, raw_arr: list, distance: float, track_length: float) -> float:
    if not delta_arr:
        return 0.0
        
    def get_dist(item) -> float:
        if hasattr(item, 'distance'):
            return item.distance
        return item[0]

    def get_val(item) -> float:
        if hasattr(item, 'value'):
            return item.value
        return item[1]

    idx_high = binary_search_higher_column(delta_arr, distance)
    if idx_high == -1:
        return get_val(delta_arr[-1])
        
    if idx_high == 0:
        return get_val(delta_arr[0])
        
    idx_low = idx_high - 1
    
    x1 = get_dist(delta_arr[idx_low])
    y1 = get_val(delta_arr[idx_low])
    x2 = get_dist(delta_arr[idx_high])
    y2 = get_val(delta_arr[idx_high])
    
    return linear_interp(distance, x1, y1, x2, y2)

def exp_mov_avg(prev_ema: float, current_val: float, factor: float) -> float:
    return prev_ema * (1.0 - factor) + current_val * factor

def ema_factor(laps: float) -> float:
    if laps <= 0.0:
        return 1.0
    return 2.0 / (laps + 1.0)

def lap_type_full_laps_remain(time_left: float, pace: float) -> int:
    if pace <= 0:
        return 0
    return math.ceil(time_left / pace)

def lap_type_laps_remain(time_left: float, pace: float, lap_progress: float) -> float:
    if pace <= 0:
        return 0.0
    return (time_left / pace) + lap_progress

def time_type_full_laps_remain(time_left: float, pace: float, lap_into: float) -> int:
    if pace <= 0:
        return 0
    time_remain_after_curr_lap = time_left - (pace - lap_into)
    if time_remain_after_curr_lap <= 0:
        return 1
    return 1 + math.ceil(time_remain_after_curr_lap / pace)

def time_type_laps_remain(time_left: float, pace: float, lap_into: float) -> float:
    if pace <= 0:
        return 0.0
    progress = lap_into / pace if pace > 0 else 0.0
    return progress + (time_left / pace)

def end_timer_laps_remain(time_left: float, pace: float, lap_into: float) -> float:
    if pace <= 0:
        return 0.0
    return (time_left + lap_into) / pace

def total_fuel_needed(laps_remain: float, avg_consumption: float, safety_margin: float = 1.0) -> float:
    return max(0.0, laps_remain * avg_consumption + safety_margin)

def end_lap_consumption(amount_curr: float, amount_start: float) -> float:
    return max(0.0, amount_start - amount_curr)

def end_stint_fuel(amount_curr: float, used_estimate: float) -> float:
    if used_estimate <= 0:
        return 0.0
    return amount_curr % used_estimate

def end_stint_laps(amount_curr: float, used_estimate: float) -> float:
    if used_estimate <= 0:
        return 0.0
    return amount_curr / used_estimate

def end_stint_minutes(amount_curr: float, used_estimate: float, pace: float) -> float:
    return end_stint_laps(amount_curr, used_estimate) * pace / 60.0

def pit_in_countdown_laps(end_stint_laps_val: float) -> int:
    return max(0, math.floor(end_stint_laps_val))

def end_lap_empty_capacity(capacity: float, amount_curr: float, used_estimate: float) -> float:
    return max(0.0, capacity - end_stint_fuel(amount_curr, used_estimate))

def end_stint_pit_counts(needed_relative: float, capacity: float, amount_end: float = 0.0) -> float:
    usable_capacity = capacity - amount_end
    if usable_capacity <= 0:
        return 0.0
    return max(0.0, needed_relative / usable_capacity)

def end_lap_pit_counts(needed_relative: float, capacity: float, amount_end: float = 0.0) -> float:
    return end_stint_pit_counts(needed_relative, capacity, amount_end)

def one_less_pit_stop_consumption(laps_remain: float, capacity: float, amount_curr: float, est_pits: float) -> float:
    if laps_remain <= 0:
        return 0.0
    target_pits = max(0, math.ceil(est_pits) - 1)
    target_fuel = target_pits * capacity + amount_curr
    return max(0.0, target_fuel / laps_remain)

def fuel_to_energy_ratio(used_fuel: float, used_energy: float) -> float:
    if used_energy <= 0:
        return 0.0
    return used_fuel / used_energy

def pitlane_length(entry: float, exit: float, track_length: float) -> float:
    if entry is None or exit is None:
        return 0.0
    if exit >= entry:
        return exit - entry
    return (track_length - entry) + exit
