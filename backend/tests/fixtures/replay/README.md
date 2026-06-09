# Replay fixtures

- `minimal_race.trace` — 3 frames, lap 1→2, position 8→6
- Formato: JSONL `{"t": seconds, "frame": {telemetry}}` (igual `TraceStore`)
- Generar en vivo: grabar con TraceStore API o copiar desde `backend/data/traces/` tras sesión LMU
