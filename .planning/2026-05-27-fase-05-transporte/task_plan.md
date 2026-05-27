# Fase 0b+0+5 Unificada: Telemetría Eficiente con MessagePack + Delta

**Estado**: Reformulado (27 mayo 2026, post-análisis exhaustivo)
**Dependencias**: Fase 2 (sidecar) ✅ completada. Fase 3 (RAG) ✅. Fase 4 (Ticker) ✅.

## Análisis del Estado Real

### Lo que SÍ funciona (no tocar)
- Sidecar envía `strategy_frame` real vía `/ws/sidecar` cada 2s ✅
- Backend almacena en `latest_strategy_frame` y lo usa en `strategy_sender_loop` ✅
- `strategy_sender_loop` alimenta el engine con frame REAL del sidecar ✅
- Health endpoint reporta `frontend_telemetry.received` ✅
- `latest_client_frame` inicializado en `main.py` ✅
- WebSocket handler recibe `telemetry` y `pilot_question` ✅

### Lo que NO funciona (target de esta fase)
- `usePTT.ts` tiene 3 errores TS reales + 12 TS6133 → PTT roto
- Frontend recibe telemetría SIMULADA (`TelemetryReader(offline=True)`) a 20Hz
- Frontend hace eco de datos simulados en JSON texto (~4 KB/s)
- No hay binario, no hay delta, no hay ahorro de ancho de banda

### Corrección: no romper el flujo sidecar
El sidecar usa su propio endpoint `/ws/sidecar` en JSON. No se migra a MessagePack. Solo se migra el flujo `telemetry_sender_loop` (backend→frontend) y el eco (frontend→backend).

## Plan Reformulado

### P0: Corregir TypeScript — PREREQUISITO BLOQUEANTE

**Archivo**: `frontend/src/hooks/usePTT.ts`
**Errores reales**:
1. Línea ~78: `await sendBinary()` fuera de `async function` — reestructurar lógica
2. Línea ~89: `Uint8Array` no es `ArrayBuffer|Blob` — alinear tipos con `sendBinary`
3. Línea ~99: `Expected 0 arguments, got 1` — corregir firma de llamada
4. 12 errores TS6133 (unused vars) — eliminar declaraciones no usadas

**Tests**: snapshot test del hook con React Testing Library
**Verificación**: `npx tsc --noEmit` → 0 errores

### P1: Backend — `msgpack_codec.py` (módulo de codec)

Archivo NUEVO: `backend/src/services/msgpack_codec.py`

```python
def encode(data: dict) -> bytes:
    """Codifica dict a MessagePack binario."""

def decode(raw: bytes) -> dict:
    """Decodifica MessagePack binario a dict."""

def apply_delta(base: dict, delta: dict) -> dict:
    """Mergea delta sobre frame base. Retorna nuevo dict."""

def is_full_frame(frame: dict) -> bool:
    """True si el frame tiene _full=true."""

def compute_delta(prev: dict, curr: dict) -> dict:
    """Calcula delta: solo campos que cambiaron + _t + _full opcional."""
```

**Tests**: `backend/tests/test_msgpack_codec.py`
- `test_encode_decode_roundtrip`: encode→decode produce dict idéntico
- `test_encode_binary_output`: encode produce bytes, no str
- `test_decode_invalid`: bytes corruptos → ValueError
- `test_apply_delta_merge`: mergea campos nuevos sobre base
- `test_apply_delta_nested`: mergea campos anidados
- `test_apply_delta_preserves_unrelated`: campos no en delta se mantienen
- `test_compute_delta_empty`: frames idénticos → delta solo con _t
- `test_compute_delta_changes`: solo campos cambiados
- `test_compute_delta_with_full`: cada 100 frames incluye _full=true
- `test_is_full_frame_detection`: detecta _full=true

### P2: Frontend — `msgpack.ts` (módulo de codec)

Archivo NUEVO: `frontend/src/services/msgpack.ts`

```typescript
export const SNAPSHOT_INTERVAL = 100;

export function encodeMsgpack(data: object): Uint8Array;
export function decodeMsgpack(data: Uint8Array): object;
export function computeDelta(current: object, previous: object | null): object;
```

**Tests**: `frontend/src/__tests__/test_msgpack.ts`
- `encode/decode roundtrip`: datos idénticos
- `encode produces Uint8Array`, no string
- `decode invalid throws`
- `computeDelta null previous`: retorna frame completo con _full=true
- `computeDelta identical frames`: solo _t
- `computeDelta changes`: solo campos cambiados
- `computeDelta every 100th`: incluye _full=true

### P3: Backend — `websocket.py` (binario + delta)

Archivo: `backend/src/routers/websocket.py`

**Cambio A**: `telemetry_sender_loop` envía binario MessagePack
- Antes: `await websocket.send_json({"event": "telemetry", "data": state_dict})`
- Después: `await websocket.send_bytes(encode(state_dict))`
- La decodificación la hará el frontend en `ws.onmessage`

**Cambio B**: `websocket_endpoint` recibe binario MessagePack
- Detectar `"bytes" in raw`
- Si binario: `decode(raw["bytes"])` → detectar `_full` → `apply_delta` si es delta
- Si texto: mantener comportamiento actual (pilot_question, etc.)
- Guardar `app.state.latest_client_frame` y `app.state._last_telemetry_t`
- Gap detection: si `_t` salta > 0.5s, log warning, esperar snapshot

**Cambio C**: Manejo de `_full` y snapshots
- Frame con `_full=true`: reemplaza `latest_client_frame` completo
- Frame sin `_full=true` (delta): aplica `apply_delta()` sobre `latest_client_frame`
- Si `latest_client_frame` es None y llega delta: ignorar, esperar snapshot

**NO CAMBIAR**: `/ws/sidecar` endpoint (sigue en JSON)

### P4: Frontend — `useWebSocket.ts` (binario + delta)

Archivo: `frontend/src/hooks/useWebSocket.ts`

**Cambio A**: `ws.onmessage` detecta binario
```typescript
ws.onmessage = (event) => {
  if (event.data instanceof ArrayBuffer || event.data instanceof Blob) {
    // Binario: MessagePack
    const arrayBuffer = event.data instanceof Blob
      ? await event.data.arrayBuffer()
      : event.data;
    const parsed = decodeMsgpack(new Uint8Array(arrayBuffer));
    // Procesar igual que JSON
  } else {
    // Texto: JSON (compatibilidad hacia atrás)
    const parsed = JSON.parse(event.data);
  }
  // ... mismo switch(eventType)
};
```

**Cambio B**: Envío 20Hz usa MessagePack + delta
```typescript
let frameCount = 0;
const previousFrameRef = useRef<object | null>(null);

useEffect(() => {
  if (!lastTelemetry) return;
  const interval = setInterval(() => {
    const isFull = frameCount % SNAPSHOT_INTERVAL === 0;
    const delta = computeDelta(lastTelemetry, previousFrameRef.current);
    if (isFull) delta._full = true;
    const binary = encodeMsgpack(delta);
    socketRef.current?.send(binary);
    previousFrameRef.current = lastTelemetry;
    frameCount++;
  }, 50);
  return () => clearInterval(interval);
}, [lastTelemetry]);
```

**Cambio C**: Resetear `frameCount` y `previousFrameRef` al reconectar

### P5: Fix telemetry source (bonus — opcional pero recomendado)

La telemetría que el backend envía al frontend viene de `reader.get_state()` (simulado). Debería usar el frame del sidecar cuando esté disponible.

```python
# En telemetry_sender_loop, en vez de:
state = reader.get_state()

# Usar:
sidecar_frame = getattr(app_state, "latest_strategy_frame", None)
if sidecar_frame and sidecar_frame.get("frame"):
    state = sidecar_frame["frame"]  # TelemetryFrame real del sidecar
else:
    state = reader.get_state()  # Fallback simulado
```

### P6: Tests de integración

Archivo NUEVO: `backend/tests/test_ws_integration.py`

Tests:
- `test_msgpack_telemetry_roundtrip`: backend envía binario, cliente decodifica
- `test_frontend_delta_received`: backend recibe delta, mergea en latest_client_frame
- `test_frontend_full_frame_received`: backend recibe _full, reemplaza
- `test_delta_ignored_when_no_base`: delta sin base previa → ignorado
- `test_gap_detection`: _t salta > 0.5s → warning log
- `test_snapshot_recovery_after_gap`: tras gap, snapshot completo corrige
- `test_health_reflects_real_data`: health endpoint muestra datos del sidecar

## Archivos Afectados (final)

| # | Archivo | Tipo | Acción | Líneas est. |
|---|---------|------|--------|:-----------:|
| 0 | `frontend/src/hooks/usePTT.ts` | existente | corregir TS | ~15 cambios |
| 1 | `backend/src/services/msgpack_codec.py` | **nuevo** | crear | ~80 |
| 2 | `frontend/src/services/msgpack.ts` | **nuevo** | crear | ~60 |
| 3 | `backend/src/routers/websocket.py` | existente | 3 cambios | ~40 |
| 4 | `frontend/src/hooks/useWebSocket.ts` | existente | ~5 cambios | ~80 |
| 5 | `backend/tests/test_msgpack_codec.py` | **nuevo** | crear | ~120 |
| 6 | `frontend/src/__tests__/test_msgpack.ts` | **nuevo** | crear | ~100 |
| 7 | `backend/tests/test_ws_integration.py` | **nuevo** | crear | ~150 |

## Engineering Best Practices (checklist)

- [ ] Type hints en TODAS las funciones Python (PEP 484)
- [ ] `mypy --strict` sin errores en archivos nuevos
- [ ] TypeScript strict: sin `any`, tipos explícitos de retorno
- [ ] Sin `assert` para lógica de negocio (solo tests)
- [ ] Docstrings en todas las funciones públicas (Google style)
- [ ] Validación de input en frontend y backend (Pydantic/Zod)
- [ ] Sin secrets/hardcodes en código
- [ ] Tests antes de implementación (TDD ciclo RED-GREEN-REFACTOR)
- [ ] `try/except` específicos, no `except Exception` genérico
- [ ] Logging estructurado: nivel apropiado (debug vs info vs warning)

## Criterios de Aceptación

1. `npx tsc --noEmit` → 0 errores TypeScript
2. `pytest tests/test_msgpack_codec.py tests/test_ws_integration.py -v` → todos pasan
3. `npx vitest run src/__tests__/test_msgpack.ts` → todos pasan
4. `pytest` (204 tests existentes) → sin regresiones
5. `npx vitest run` (42 tests existentes) → sin regresiones
6. `mypy backend/src/services/msgpack_codec.py --strict` → 0 errores
7. Delta encoding: 100 frames → ~99 delta + ~1 snapshot
8. Sidecar `/ws/sidecar` sin cambios (JSON sigue funcionando)
9. Compatibilidad hacia atrás: eventos strategy/advice/alert/pilot_question intactos
