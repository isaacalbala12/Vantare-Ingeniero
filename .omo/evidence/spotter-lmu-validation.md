# Validación spotter en LMU (manual)

Ejecutar **después** de que el gate CI local pase en verde.

## Gate CI local (sin LMU)

```powershell
cd backend
python -m pytest tests/test_spotter*.py tests/test_cartesian_spotter.py tests/test_spotter_state.py tests/test_spotter_e2e.py -v
python ../scripts/verify_spotter_pipeline.py

cd ../frontend
npm test -- alertVoice.test.ts priorityAudioQueue.test.ts ttsCache.test.ts useWebSocket.spotter.test.ts spotterPipeline.integration.test.ts --run
```

## Checklist en pista

1. Arrancar backend (`python run_dev.py`), sidecar (`python -m sidecar.main`) y Tauri dev.
2. LMU en **borderless/windowed**, carrera AI multiclase.
3. Forzar side-by-side en recta o curva lenta.
4. Verificar en logs backend:
   - `cartesian_hits > 0` en `proximity_scan`
   - `proximity_alert_created` con `source: cartesian`
5. Verificar frontend:
   - `alert_received` con `category: proximity`, `voiceOk: true`
   - `play_started` en priorityAudioQueue
6. Confirmar audio audible (limiter + lateral).
7. Confirmar UI RadioOverlay muestra alerta sin borrado cíclico.

## Captura de traza (opcional)

```powershell
python scripts/capture_spotter_trace.py --output backend/tests/fixtures/spotter/captured_session.json
```

Convertir frames representativos en fixtures de regresión.

## Criterios de éxito

| Criterio | Evidencia |
|----------|-----------|
| Detección cartesian | `test_cartesian_spotter` + fixture `world_overlap_no_path_delta` |
| Pipeline backend | `verify_spotter_pipeline.py` OK |
| Anti-spam | `test_spotter_state` + secuencia temporal ≤3 alertas |
| Audio priority | vitest `priorityAudioQueue` + `useWebSocket.spotter` |
| Sesión LMU | logs + audio audible |
