# Wave 6 PTT command inventory (LMU race session)

| Tool | Status | CC domain |
|------|--------|-----------|
| set_speak_only | PORTED | Radio silence |
| spotter_toggle | PORTED | Spotter |
| get_fuel_status | PORTED | Fuel |
| get_gap_status | PORTED | Timings |
| get_damage_report | PORTED | Damage |
| get_tire_wear | PORTED | TyreMonitor |
| set_verbosity | PORTED | Settings |
| set_braking_zones_mute | PORTED | Settings |
| set_pit_fuel | PORTED | PitMenu |
| set_pit_tyres | PORTED (Task 44) | PitMenu |
| monitor_competitor | PORTED | WatchedOpponents |
| query_competitor | PORTED | Opponents |
| get_flag_status | PORTED (Task 45) | Flags |
| get_race_time_remaining | PORTED (Task 45) | RaceTime |
| get_pit_window_status | PORTED (Task 45) | PitStops |
| watch_snip | PORTED (Task 45) | WatchedOpponents |

**NOT_PORTED (by design):** iRacing-only phrases, overlay/VR, MQTT, CoDriver, AlarmClock.

Target: ≥80% of LMU-applicable CC race-session voice commands covered via tools; remainder → LLM PTT fallback.
