import time
from src.services.lmu_reader import LMUReader
from src.intelligence.spotter_v2 import SpotterV2

r = LMUReader(offline=False)
r.start()
time.sleep(2)

s = SpotterV2()

for tick in range(20):
    d = r.get_flat_dict()
    alerts, triggers = s.evaluate(d)
    
    has_shown_header = False
    for a in alerts:
        if not has_shown_header:
            print(f'Tick {tick}: place={d["place"]} speed={d["speed"]:.1f} in_pits={d["in_pits"]}')
            has_shown_header = True
        print(f'  ALERT [{a.category}] {a.message[:60]}')
    for t in triggers:
        if not has_shown_header:
            print(f'Tick {tick}: place={d["place"]} speed={d["speed"]:.1f}')
            has_shown_header = True
        print(f'  TRIGGER {t}')
    if not has_shown_header and tick == 0:
        print(f'Tick 0: place={d["place"]} speed={d["speed"]:.1f} in_pits={d["in_pits"]}')
        print(f'  gap_ahead={d["time_gap_car_ahead"]:.2f} gap_behind={d["time_gap_car_behind"]:.2f}')
        print(f'  NO ALERTS (datos actuales no generan condiciones)')
    
    time.sleep(0.1)

r.stop()
print(f'Done - {tick+1} ticks evaluados')
