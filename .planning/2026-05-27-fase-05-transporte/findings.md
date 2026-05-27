# Findings — Fase 0b+0+5 Transporte Eficiente (Reformulado)

## Análisis Corregido (27 mayo 2026)

### Error en análisis anterior (26 mayo)
El análisis del 26 de mayo afirmaba erróneamente que "no hay sidecar" y que "todos los datos son simulados". Esto era INCORRECTO.

### Estado real verificado
- **Sidecar**: Existe en `sidecar/src/sidecar/`. `main.py` (139 líneas), `strategy_runner.py` (257 líneas), `event_detector.py` (126 líneas). Totalmente funcional.
- **Flujo sidecar**: Lee shared memory REAL (offline=False), calcula estrategia cada 2s, envía `strategy_frame` a `/ws/sidecar`.
- **Flujo frontend**: Recibe telemetría SIMULADA del backend (`TelemetryReader(offline=True)`), hace eco en JSON.
- **Estrategia**: Usa datos REALES del sidecar (no simulados).
- **Telemetría frontend**: Sigue siendo simulada porque `telemetry_sender_loop` usa `reader.get_state()`.

### Conclusión
La Fase 5 (MessagePack + Delta) es viable y útil para el flujo backend↔frontend. No afecta al sidecar (que tiene su propio endpoint). Adicionalmente, corregir la fuente de telemetría del frontend (P5) para usar datos del sidecar en vez de simulados.

## Decisiones de Diseño (confirmadas/revisadas)

### Delta encoding: plano, no jerárquico
Comparación campo-a-campo del primer nivel del dict. Sin navegación de rutas anidadas. Es más simple y rápido.

### Separación sidecar / frontend
- Sidecar: `/ws/sidecar`, JSON, sin cambios (NO se migra a MessagePack)
- Frontend: `/ws`, binario MessagePack (telemetría solo), resto JSON texto

### Gap detection pasiva
No se pide resync activo (añadiría latencia). Se espera al próximo snapshot automático (cada 100 frames = 5s). Se loguea warning.

### _t como timestamp Unix
`time.time()` con precisión de microsegundos. Suficiente para detectar gaps > 500ms.

### No breaking changes
Todos los eventos existentes (strategy, advice_start, advice_token, advice_end, alert, llm_pending, pilot_question) siguen funcionando en JSON texto.
