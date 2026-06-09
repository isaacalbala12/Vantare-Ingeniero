# Sidecar freeze policy — SUPERSEDED (Task 49-S9, 2026-06-08)

> **Status:** The strategy sidecar package has been **removed**. Native in-process telemetry is the only production path on Windows.

Historical policy (pre-S9):

- `sidecar/` was LEGACY. No new CC fields, no parity fixes.
- All LMU telemetry fields → `shared-strategy/src/shared_strategy/telemetry_frame_builder.py`
- Dev default: `VANTARE_NATIVE_TELEMETRY=1`, backend + Tauri only (2 processes)

See: [native-telemetry-smoke.md](./native-telemetry-smoke.md) · [Task 49 completion plan](../../docs/superpowers/plans/2026-06-08-task49-sidecar-removal-completion.md)
