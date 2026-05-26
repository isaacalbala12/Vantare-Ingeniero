# Reparar WebSocket — Telemetría Frontend → Backend (Fase 0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reparar el flujo WebSocket para que el frontend (Windows, donde está LMU) envíe telemetría al backend (Linux, donde está el LLM). Esto es el paso previo crítico para todo el desarrollo posterior.

**Architecture:** El frontend ya recibe telemetría del backend vía WebSocket. El backend en Linux no tiene acceso a shared memory y necesita telemetría real para los cálculos de estrategia. Implementamos un flujo bidireccional: frontend retransmite la telemetría que recibe hacia el backend, el backend la almacena en `app.state.latest_client_frame` y la usa en `strategy_sender_loop` en vez del reader offline.

**Tech Stack:** Python 3.12 (FastAPI, WebSocket, Pydantic), TypeScript (React, Zustand)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/routers/websocket.py` | Modify | Añadir handler `"telemetry"` entrante, usar `latest_client_frame` en strategy loop |
| `backend/src/main.py` | Modify | Inicializar `latest_client_frame`, cambiar `TelemetryReader(offline=True)` en Linux |
| `backend/src/models/messages.py` | Modify | Añadir `TelemetryIncomingMessage` para validar telemetría entrante |
| `frontend/src/hooks/useWebSocket.ts` | Modify | Añadir loop que reenvía `sendJson("telemetry", lastTelemetry)` al backend |
| `frontend/src/store/config.ts` | Read-only | Referencia: `TelemetryState` interface para asegurar compatibilidad |

---

### Task 1: Modelo de mensaje para telemetría entrante

**Files:**
- Modify: `backend/src/models/messages.py` (append)

- [ ] **Step 1: Añadir TelemetryIncomingMessage**

Al final de `backend/src/models/messages.py`, añadir:

```python
class TelemetryIncomingMessage(BaseModel):
    """Mensaje de telemetría entrante desde el frontend (Windows) hacia el backend (Linux)."""
    event: str = "telemetry"
    data: Dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 2: Verificar que no rompe nada**

```bash
cd backend && python -c "from src.models.messages import TelemetryIncomingMessage; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/models/messages.py
git commit -m "feat: add TelemetryIncomingMessage for frontend → backend telemetry"
```

---

### Task 2: Handler de telemetría entrante en el WebSocket

**Files:**
- Modify: `backend/src/routers/websocket.py:183-198`

- [ ] **Step 1: Añadir handler `"telemetry"` en el switch de eventos**

En `backend/src/routers/websocket.py`, dentro del bloque `if event == "pilot_question":` (línea ~186), añadir un nuevo `elif` ANTES del `pilot_question`:

```python
if event == "telemetry":
    # Almacenar la telemetría entrante del frontend para que strategy_sender_loop la use
    telemetry_data = msg.get("data", {})
    if telemetry_data:
        app_state.latest_client_frame = telemetry_data
        # Solo loggear cada ~2s (cada 100 ticks a 20Hz) para no saturar
elif event == "pilot_question":
```

- [ ] **Step 2: Verificar sintaxis**

```bash
cd backend && python -c "import ast; ast.parse(open('src/routers/websocket.py').read()); print('Syntax OK')"
```
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/routers/websocket.py
git commit -m "feat: add telemetry handler in websocket to store frontend telemetry"
```

---

### Task 3: Strategy loop usando telemetría del frontend

**Files:**
- Modify: `backend/src/routers/websocket.py:105-151`

- [ ] **Step 1: Modificar strategy_sender_loop para usar latest_client_frame**

Reemplazar en `strategy_sender_loop` (líneas 128-136):

Antes:
```python
engine = getattr(app_state, "intelligence_engine", None)
if engine:
    reader = getattr(app_state, "telemetry_reader", None)
    if reader:
        frame = reader.get_state()
        if frame:
            task = asyncio.create_task(_safe_evaluate_cycle(engine, frame, advice))
```

Después:
```python
engine = getattr(app_state, "intelligence_engine", None)
if engine:
    # 1. Intentar usar telemetría del frontend (Windows → Linux)
    frame = getattr(app_state, "latest_client_frame", None)
    
    # 2. Fallback: telemetry_reader (offline en Linux, real en Windows)
    if not frame:
        reader = getattr(app_state, "telemetry_reader", None)
        if reader:
            frame = reader.get_state()
    
    if frame:
        task = asyncio.create_task(_safe_evaluate_cycle(engine, frame, advice))
```

- [ ] **Step 2: Verificar sintaxis**

```bash
cd backend && python -c "import ast; ast.parse(open('src/routers/websocket.py').read()); print('Syntax OK')"
```
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/routers/websocket.py
git commit -m "feat: strategy_sender_loop uses latest_client_frame from frontend with reader fallback"
```

---

### Task 4: Inicializar latest_client_frame en main.py

**Files:**
- Modify: `backend/src/main.py:59-63`

- [ ] **Step 1: Inicializar latest_client_frame y cambiar a offline=True**

Reemplazar el bloque de TelemetryReader (líneas 59-63):

Antes:
```python
reader = TelemetryReader(offline=False, poll_rate=settings.TELEMETRY_POLL_RATE)
reader.start()
app.state.telemetry_reader = reader
logger.info(f"TelemetryReader started (offline_mode={reader.offline})")
```

Después:
```python
# En Linux, no hay shared memory de LMU. Usamos TelemetryReader en modo offline como fallback.
# La telemetría real vendrá del frontend Windows vía WebSocket → app.state.latest_client_frame.
reader = TelemetryReader(offline=True, poll_rate=settings.TELEMETRY_POLL_RATE)
reader.start()
app.state.telemetry_reader = reader
app.state.latest_client_frame = None  # Se poblará desde el frontend vía WebSocket
logger.info(f"TelemetryReader started (offline_mode={reader.offline}). Waiting for frontend telemetry.")
```

- [ ] **Step 2: Verificar que el backend arranca**

```bash
cd backend && timeout 5 python -c "
import asyncio
from src.main import app
print('App created OK')
" 2>&1 || true
```
Expected: `App created OK` (puede haber warnings de dependencias pero no errores)

- [ ] **Step 3: Commit**

```bash
git add backend/src/main.py
git commit -m "feat: initialize latest_client_frame and set TelemetryReader(offline=True) for Linux"
```

---

### Task 5: Frontend — Enviar telemetría al backend cada 50ms

**Files:**
- Modify: `frontend/src/hooks/useWebSocket.ts` (add useEffect)

- [ ] **Step 1: Añadir loop de envío de telemetría al backend**

En `frontend/src/hooks/useWebSocket.ts`, después de la definición de `lastTelemetry` (línea 23), añadir:

```typescript
// Enviar telemetría al backend a 20Hz (50ms) para que el backend Linux tenga datos reales
useEffect(() => {
  if (!lastTelemetry) return;
  
  const interval = setInterval(() => {
    sendJson("telemetry", lastTelemetry);
  }, 50);
  
  return () => clearInterval(interval);
}, [lastTelemetry, sendJson]);
```

**Importante**: Colocar este `useEffect` DESPUÉS de la función `sendJson` (línea 346) y ANTES del `return` final. Como `useEffect` requiere estar dentro del componente y `sendJson` ya está definido, mover este efecto justo antes del `return` final.

Posición exacta: después de la línea 353 (cierre de `sendJson`) y antes del `return { connect, disconnect, ... }`.

- [ ] **Step 2: Verificar TypeScript compilación**

```bash
cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20
```
Expected: No errors relacionados con `useWebSocket.ts`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useWebSocket.ts
git commit -m "feat: send telemetry to backend at 20Hz from frontend WebSocket"
```

---

### Task 6: Health endpoint — reportar latest_client_frame

**Files:**
- Modify: `backend/src/routers/health.py` (read first)

- [ ] **Step 1: Leer health.py actual**

```bash
cat backend/src/routers/health.py
```

- [ ] **Step 2: Añadir latest_client_frame al health status**

Añadir al diccionario de respuesta en el endpoint `/health`:

```python
"frontend_telemetry": {
    "received": getattr(app.state, "latest_client_frame", None) is not None,
}
```

- [ ] **Step 3: Verificar health endpoint**

```bash
curl -s http://localhost:8008/health | python -m json.tool | grep frontend
```
Expected: `"frontend_telemetry": {"received": false}` cuando no hay frontend conectado

- [ ] **Step 4: Commit**

```bash
git add backend/src/routers/health.py
git commit -m "feat: health endpoint reports frontend telemetry reception status"
```

---

### Task 7: Test de integración — flujo completo

- [ ] **Step 1: Arrancar backend en Linux**

```bash
cd backend && python -m uvicorn src.main:app --host 0.0.0.0 --port 8008 &
sleep 3
```

- [ ] **Step 2: Verificar que el backend acepta telemetría por WebSocket**

```bash
python3 -c "
import asyncio
import json
import websockets

async def test():
    async with websockets.connect('ws://localhost:8008/ws') as ws:
        # Enviar telemetría simulada
        await ws.send(json.dumps({
            'event': 'telemetry',
            'data': {
                'lap_number': 5,
                'fuel_in_tank': 85.2,
                'speed': 55.0,
                'gear': 4,
                'rpm': 6500
            }
        }))
        await asyncio.sleep(0.5)
        print('[TEST] Telemetry sent OK')
        
        # Verificar que health reporta telemetría recibida
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get('http://localhost:8008/health')
            data = resp.json()
            received = data.get('frontend_telemetry', {}).get('received', False)
            print(f'[TEST] Frontend telemetry received: {received}')
            assert received == True, 'Telemetry not received by backend!'
            print('[TEST] ✅ Integration test passed')

asyncio.run(test())
" 2>&1
```
Expected: `[TEST] ✅ Integration test passed`

- [ ] **Step 3: Parar backend y commit**

```bash
kill %1 2>/dev/null
git add backend/src/routers/health.py
git commit -m "test: integration test for frontend → backend telemetry flow"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `backend/src/routers/websocket.py` tiene handler `"telemetry"` entrante ✅
- [ ] `strategy_sender_loop` usa `latest_client_frame` con fallback a `reader.get_state()` ✅
- [ ] `backend/src/main.py` inicializa `latest_client_frame = None` y `offline=True` ✅
- [ ] `frontend/src/hooks/useWebSocket.ts` envía `sendJson("telemetry", lastTelemetry)` cada 50ms ✅
- [ ] Health endpoint reporta `frontend_telemetry.received` ✅
- [ ] Test de integración pasa ✅
- [ ] Backend no crashea si no hay frontend conectado ✅
- [ ] Backend no crashea si la telemetría entrante tiene formato inesperado ✅

---

## Next Phase (Fase 1 — Sidecar)

Una vez completada Fase 0, el siguiente paso es mover `StrategyService` a un sidecar Python en Windows:

1. Crear `sidecar/` con `shared-telemetry` + `shared-strategy`
2. Implementar `StateChangeDetector` (`event_detector.py`)
3. Sidecar envía eventos + estrategia al backend Linux vía WebSocket
4. Eliminar `StrategyService(reader)` del backend Linux
