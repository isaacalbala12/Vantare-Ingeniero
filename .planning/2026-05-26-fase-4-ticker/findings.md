# Fase 4 — Research Findings

## LMU Shared Memory

- `LMUWheel` NO expone `mBrakeWear`. Solo `mBrakeTemp` (Kelvin) y `mBrakePressure` (0.0-1.0).
- `LMUVehicleScoring` NO expone número de dorsal/piloto. Solo `mDriverName`, `mSteamID`, `mPitGroup`.
- `LMUVehicleScoring.mPitGroup` es el nombre del equipo (24 chars). Útil como identificador extra en RIV.
- Todos los enums documentados en `lmu_enum.py`: GamePhase, SessionType, TrackGripLevel, CloudCoverage, PitState, etc.

## REST API (lmu_api.py)

- Brake wear real viene de `/rest/garage/UIScreen/RepairAndRefuel` cada 3s.
- Acceso vía `lmu_api.get_additional_data("brakes")` → `{"wear": [0.92, 0.88, 0.85, 0.90]}` (0.0-1.0).
- Cache thread-safe con `threading.Lock`. Primeros 3s el cache está vacío.
- Weather cache (120s) solo para predicción climática, no para ticker en tiempo real.

## Código existente relevante

- `formatter.py` ya tiene `format_event_text()` para embeddings. No tocar.
- `live_context.py` tiene snapshots FAST/STANDARD/DEEP con datos de telemetría + estrategia.
- `context_builder.py` ya tiene `_build_rag_context()` y `_snapshot_to_frame()`. Refactorizar con cuidado.
- `prompt_templates.py` usa `json.dumps()` para serializar el contexto. Es lo que vamos a reemplazar.
- `engine.py` ya tiene acceso a `telemetry_dict` y `strategy_dict` en `evaluate_cycle()`.

## Decisiones de diseño

| Aspecto | Decisión | Alternativa descartada |
|---------|----------|----------------------|
| RIV rivales lejanos | Conteo + gap máximo | No listar (pierde contexto) |
| Brake wear ausente | Omitir línea BRK | No enviar 0/0/0/0 |
| Identificador rival | Abrev. 3 chars + pit group | #ID (no existe en LMU) |
| Degradación prompt | 4 niveles según tokens | Threshold duro (mala UX) |
| Audio "déjame revisarlo" | Frontend reproduce en llm_pending | Backend envía WAV (más complejo) |
