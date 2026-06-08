# Crew Chief — permanent ceilings (LMU alpha)

Limitaciones conocidas que **no** se cierran en Task 48. Los módulos CC @ 20 Hz son la fuente única de mensajes deterministas; esta lista documenta gaps de datos o comportamiento vs Crew Chief de referencia.

| Área | Estado | Notas |
|------|--------|-------|
| Driver swap stint timer | PARTIAL | LMU no expone `driver_stint_seconds_remaining`; solo detección por cambio de nombre |
| Weather forecast LLM | LEGACY | `WeatherChangeTrigger` hasta módulo forecast CC |
| Phase change LLM | LEGACY | `PhaseChangedTrigger` en allowlist `LEGACY_COMMENTARY_EVENT_IDS` |
| Commentary batch (ruta B) | OPT-IN | `enableCommentaryBatch=false` por defecto post Task 48 |
| Spotter fuel/last-lap | CC-adjacent | Algunos avisos spotter siguen en pipeline proximidad |
| PTT pit tyre write | CONFIRM | Requiere `PIT_MENU_CONFIRM_WRITES` + LMU pit menu API |
| Native telemetry | **DONE** | Sidecar removed Task 49-S9; backend reads LMU shared memory in-process @ 20 Hz |

Validación: `pytest -k crewchief`, `test_crewchief_no_legacy_emitters`, `scripts/replay_trace.py`, checklist `.omo/evidence/cc-parity-validation-checklist.md`.
