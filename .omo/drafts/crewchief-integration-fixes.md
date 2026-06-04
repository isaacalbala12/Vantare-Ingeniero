# Draft: CrewChief Integration Fixes & Architectural Alignment

## Context
The user has implemented Phases 0-4 of the CrewChiefV4 implementation (pipeline, spotter, event engine, audio system) plus 4 events from Phase 5. The code is solid at unit-test level (533 tests) but has integration gaps and architectural divergences from the master plan at `docs/superpowers/plans/2026-06-01-crewchiefv4-full-implementation.md`.

## Key Decision (Confirmed)
- **Follow the plan's architecture**: Refactor AudioPlayer to use inline `process()` instead of threaded `_player_loop`. This aligns with the plan's main loop which calls `ap.process()` per tick.

## Bugs Found
1. `calculate_rotation` roll formula uses `rx.x` twice (lmu_reader.py:48)
2. `game_state_builder.py` normalizes battery with `fuel_capacity` (line 87)
3. `AudioPlayer` lacks `play_spotter_message()` — spotter calls it but only FakeAudioPlayer has it
4. Spotter fallback `ap.play(audio_path, priority=20)` type mismatch (str vs QueuedMessage)
5. `FrameCache.get_spotter_frame()` recalculates entire frame unnecessarily

## Architecture Divergences
- Plan: AudioPlayer inline with `process(now, gsd)` called from main loop
- Real: AudioPlayer threaded with `start()`/`stop()`/`_player_loop`
- Plan: SoundCache uses classmethod-based API
- Real: SoundCache uses instance-based API
- Plan: Main loop in `main.py` adds `asyncio.create_task(crewchief_loop(...))`
- Real: No crewchief_loop exists

## Missing Pieces
- `crewchief_loop.py` — main integration loop
- `AudioPlayer.play_spotter_message()` method
- Integration test for full pipeline
- 25 remaining events (fuel, tyres, engine, damage, battery, pit, etc.)

## Open Questions
1. AudioPlayer refactor: full rewrite to inline, or keep thread + add `process()` facade?
2. crewchief_loop: separate file or inline in main.py?
3. Should we fix old spotter or migrate to new one?
4. Scope: just bug fixes + crewchief_loop, or also some Phase 5 events?
