# Fix Bucle de Alertas + Audio Test — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar el bucle de alertas de audio del spotter y añadir un mensaje "Probando audio" al salir del garaje.

**Root Cause:** Hay DOS caminos independientes que generan `AlertMessage` hacia el frontend:
1. **Spotter** (via `evaluate_tick()` → `broadcast_callback`) — tiene cooldown ✅
2. **Engine** (via `evaluate_cycle()` → ALERT_ONLY → `self.broadcaster.send()`) — **NO** tiene cooldown ❌

Además, el engine se ejecuta a 0.5Hz (cada 2s) y por cada trigger que cumpla condición, envía un `AlertMessage` nuevo. Si el trigger `BrakeWearCriticalTrigger` o cualquier otro `ALERT_ONLY` tiene condición verdadera, enviará la misma alerta cada 2 segundos sin límite.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, React/TypeScript, Tauri

---

### Task 1: Centralizar cooldown en SpotterService y usarlo desde el Engine

**Files:**
- Modify: `backend/src/intelligence/spotter.py` — exponer método `should_broadcast(category, ttl)`
- Modify: `backend/src/intelligence/engine.py` — usar SpotterService.cooldown en ALERT_ONLY
- Test: `backend/tests/test_spotter.py` — test de cooldown compartido

**Problema:** El engine crea `AlertMessage` en `evaluate_cycle()` línea 274-288 y lo envía por `self.broadcaster.send(alert_msg)`. No hay cooldown. A 0.5Hz, la misma alerta se envía cada 2 segundos.

**Solución:** Hacer que el SpotterService pueda recibir alertas externas (desde el engine) y aplicarles el mismo cooldown. Añadir método `try_broadcast(alert: AlertMessage) -> bool` que retorna True si pasó el cooldown y envía, False si lo suprimió.

- [ ] **Step 1: Escribir tests del cooldown compartido**

Añadir en `backend/tests/test_spotter.py`:

```python
class TestSpotterSharedCooldown:
    """El cooldown del Spotter debe funcionar para alertas externas (engine)."""

    def test_external_alert_respected_cooldown(self, spotter, broadcast_messages):
        """Alertas externas deben respetar el cooldown del spotter."""
        from src.models.messages import AlertMessage
        
        # Enviar alerta externa (simula engine ALERT_ONLY)
        alert = AlertMessage(
            event="alert",
            alert_id="test-1",
            category="strategy",
            message="Test alert",
            audio_priority="HIGH",
            payload={"severity": "HIGH", "ttl": 10, "dismissable": True}
        )
        
        # Primera vez: debe enviar
        sent1 = spotter.try_broadcast(alert)
        assert sent1, "Primera alerta externa debe enviarse"
        assert len(broadcast_messages) == 1
        
        # Segunda vez inmediata: cooldown debe suprimir
        sent2 = spotter.try_broadcast(alert)
        assert not sent2, "Cooldown debe suprimir alerta duplicada"
        assert len(broadcast_messages) == 1  # No incrementó

    def test_external_alert_expires_after_ttl(self, spotter, broadcast_messages):
        """Alerta externa debe poder reenviarse tras el TTL."""
        import time
        from src.models.messages import AlertMessage
        
        alert = AlertMessage(
            event="alert",
            alert_id="test-2",
            category="strategy",
            message="Test alert",
            audio_priority="HIGH",
            payload={"severity": "HIGH", "ttl": 5, "dismissable": True}
        )
        
        spotter.try_broadcast(alert)
        first_count = len(broadcast_messages)
        
        # Simular paso del tiempo
        spotter._last_fired["strategy"] = time.monotonic() - 6.0
        
        spotter.try_broadcast(alert)
        assert len(broadcast_messages) > first_count, "TTL expirado debe re-enviar"

    def test_different_categories_independent(self, spotter, broadcast_messages):
        """Categorías diferentes deben tener cooldown independiente."""
        from src.models.messages import AlertMessage
        
        alert_a = AlertMessage(event="alert", alert_id="a", category="limiter",
            message="Limiter", audio_priority="CRITICAL",
            payload={"severity": "CRITICAL", "ttl": 10, "dismissable": True})
        alert_b = AlertMessage(event="alert", alert_id="b", category="fuel",
            message="Fuel", audio_priority="CRITICAL",
            payload={"severity": "CRITICAL", "ttl": 10, "dismissable": True})
        
        spotter.try_broadcast(alert_a)
        spotter.try_broadcast(alert_b)
        
        assert len(broadcast_messages) == 2, "Distintas categorías deben pasar ambas"
```

- [ ] **Step 2: Ejecutar tests para verificar fallo**

Run:
```bash
cd backend && python -m pytest tests/test_spotter.py::TestSpotterSharedCooldown -v
```

Expected: 3 tests FAILED (try_broadcast no existe).

- [ ] **Step 3: Añadir método try_broadcast a SpotterService**

En `backend/src/intelligence/spotter.py`, añadir después de `evaluate_tick()`:

```python
def try_broadcast(self, alert: AlertMessage) -> bool:
    """Intenta broadcast de una alerta respetando el cooldown por categoría.
    
    Útil para que el IntelligenceEngine use el mismo cooldown del Spotter.
    
    Returns:
        True si la alerta fue enviada, False si fue suprimida por cooldown.
    """
    category = getattr(alert, 'category', 'unknown')
    ttl = alert.payload.get('ttl', 3) if alert.payload else 3
    now = time.monotonic()
    last = self._last_fired.get(category, 0.0)
    if now - last >= ttl:
        self._last_fired[category] = now
        if self.broadcast_callback:
            self.broadcast_callback(alert)
        return True
    return False
```

- [ ] **Step 4: Modificar engine.py para usar spotter cooldown**

En `backend/src/intelligence/engine.py`, reemplazar el bloque ALERT_ONLY (líneas 274-288):

PRIMERO, añadir un helper `_get_spotter_service()` (usando el mismo patrón que `_get_strategy_service()` y `_get_event_store()` ya existentes en engine.py):

```python
    def _get_spotter_service(self):
        """Obtiene el SpotterService desde app.state (similar a _get_strategy_service)."""
        main_mod = sys.modules.get("src.main")
        if main_mod and hasattr(main_mod, "app"):
            return getattr(main_mod.app.state, "spotter_service", None)
        return None
```

LUEGO, reemplazar el bloque ALERT_ONLY:

```python
                elif trigger.action == TriggerAction.ALERT_ONLY:
                    alert_msg = AlertMessage(
                        event="alert",
                        alert_id=str(uuid.uuid4()),
                        category="strategy",
                        message=trigger.alert_text,
                        audio_priority=trigger.priority.name,
                        payload={
                            "severity": trigger.priority.name,
                            "ttl": 10,
                            "dismissable": True
                        }
                    )
                    # Intentar enviar via Spotter (respeta cooldown por categoria)
                    spotter_service = self._get_spotter_service()
                    
                    if spotter_service and hasattr(spotter_service, 'try_broadcast'):
                        spotter_service.try_broadcast(alert_msg)
                    else:
                        # Fallback: cooldown inline minimo para evitar bucle
                        import time as _time
                        _now = _time.monotonic()
                        _last = getattr(self, '_engine_last_alert', 0.0)
                        if _now - _last >= 10.0:
                            setattr(self, '_engine_last_alert', _now)
                            self.broadcaster.send(alert_msg)
                    break
```

- [ ] **Step 5: Verificar que try_broadcast se usa correctamente**

Añadir también un test de integración que verifique que el engine usa el spotter:

```python
@pytest.mark.asyncio
async def test_engine_uses_spotter_cooldown(self):
    """El engine debe llamar a spotter.try_broadcast() en ALERT_ONLY."""
    from src.intelligence.engine import IntelligenceEngine
    from shared_strategy.models import TelemetryFrame
    
    messages = []
    engine = IntelligenceEngine(broadcast_callback=lambda m: messages.append(m))
    
    # Spy sobre el spotter
    from src.intelligence.spotter import SpotterService
    original_try = SpotterService.try_broadcast
    called = []
    def spy_try(self, alert):
        called.append(alert)
        return original_try(self, alert)
    SpotterService.try_broadcast = spy_try
    
    try:
        frame = TelemetryFrame(
            session_type="race", session_time_left=3600.0, session_laps_left=10.0,
            lap_number=20, lap_distance=1000.0, lap_time_best=90.0, lap_time_previous=91.0,
            is_invalid_lap=False, in_garage=False, in_pits=False, pit_limiter_active=False,
            yellow_flag_active=False, safety_car_active=False, full_course_yellow_active=False,
            fuel_in_tank=50.0, fuel_capacity=100.0, fuel_used_lap_raw=3.2,
            battery_charge=85.0, battery_drain=2.0, battery_regen=0.5, motor_state=2,
            tyre_wear_fl=50.0, tyre_wear_fr=50.0, tyre_wear_rl=45.0, tyre_wear_rr=45.0,
            tyre_temp_fl=78.0, tyre_temp_fr=80.0, tyre_temp_rl=85.0, tyre_temp_rr=86.0,
            brake_wear_fl=95.0,  # > 80% → BrakeWearCriticalTrigger (ALERT_ONLY)
            brake_wear_fr=92.0, brake_wear_rl=40.0, brake_wear_rr=35.0,
            speed=50.0, throttle=0.0, brake=0.5,
            pos_x=0.0, pos_y=0.0, pos_z=0.0, competitors=[]
        )
        await engine.evaluate_cycle(
            telemetry_state=frame, strategy_state={},
            session_state={"phase": "RACE", "weather_forecast": []}
        )
    finally:
        SpotterService.try_broadcast = original_try
    
    assert len(called) >= 1, f"Engine no llamó try_broadcast. Llamadas: {len(called)}"
```

- [ ] **Step 6: Ejecutar todos los tests**

Run:
```bash
cd backend && python -m pytest tests/test_spotter.py tests/test_engine.py tests/test_ws_integration.py -v
```

Expected: Todos pasando (excepto los 2 pre-existentes en test_engine.py).

- [ ] **Step 7: Commit**

```bash
git add backend/src/intelligence/spotter.py backend/src/intelligence/engine.py backend/tests/test_spotter.py
git commit -m "fix(engine): use spotter cooldown for ALERT_ONLY triggers

El engine generaba AlertMessage para triggers ALERT_ONLY sin ningun
cooldown, enviando la misma alerta cada 2s (0.5Hz). Se anade metodo
SpotterService.try_broadcast() que aplica el mismo cooldown por
categoria, y el engine ahora lo usa para todas las alertas ALERT_ONLY."
```

---

### Task 2: Añadir trigger "Probando audio" al salir del garaje

**Files:**
- Modify: `backend/src/intelligence/spotter.py` — nueva condición en evaluate()
- Test: `backend/tests/test_spotter.py`

**Problema:** Cuando el piloto se monta en el coche y empieza a circular por el pit lane, no hay confirmación de que el sistema de audio funcione.

**Solución:** Detectar transición garaje → pit lane (in_pits=True + throttle pasó de 0 a >0) y emitir alerta "Probando audio, radio del ingeniero verificada". Usar cooldown largo (60s) para que no se repita.

- [ ] **Step 1: Escribir tests**

Añadir en `backend/tests/test_spotter.py`:

```python
class TestSpotterAudioTestTrigger:
    """Trigger 'Probando audio' al salir del garaje."""

    def test_audio_test_on_garage_exit(self, spotter, broadcast_messages):
        """Transición throttle=0→0.3 con in_pits=True debe generar 'Probando audio'."""
        tick = {
            "in_pits": True, "pit_limiter_active": False,
            "throttle": 0.3, "speed": 12.0, "lap_distance": 800.0,
            "gap_ahead": 5.0, "gap_behind": 5.0,
        }
        spotter.evaluate_tick(tick)
        
        audio_test = [m for m in broadcast_messages if getattr(m, 'category', '') == 'audio_test']
        assert len(audio_test) >= 1, "Debe generar 'Probando audio' al salir del garaje"
        assert "Probando audio" in audio_test[0].message or "probando" in audio_test[0].message.lower()

    def test_audio_test_not_in_garage(self, spotter, broadcast_messages):
        """En garaje (throttle=0) no debe generar 'Probando audio'."""
        tick = {
            "in_pits": True, "pit_limiter_active": False,
            "throttle": 0.0, "speed": 0.0, "lap_distance": -24.0,
        }
        spotter.evaluate_tick(tick)
        audio_test = [m for m in broadcast_messages if getattr(m, 'category', '') == 'audio_test']
        assert len(audio_test) == 0, "Garaje no debe generar audio test"

    def test_audio_test_not_on_track(self, spotter, broadcast_messages):
        """En pista (in_pits=False) no debe generar 'Probando audio'."""
        tick = {
            "in_pits": False, "pit_limiter_active": False,
            "throttle": 0.8, "speed": 70.0, "lap_distance": 2000.0,
        }
        spotter.evaluate_tick(tick)
        audio_test = [m for m in broadcast_messages if getattr(m, 'category', '') == 'audio_test']
        assert len(audio_test) == 0, "En pista no debe generar audio test"
```

- [ ] **Step 2: Ejecutar tests para verificar fallo**

Run:
```bash
cd backend && python -m pytest tests/test_spotter.py::TestSpotterAudioTestTrigger -v
```

Expected: 3 tests FAILED (trigger no implementado).

- [ ] **Step 3: Implementar trigger en SpotterService.evaluate()**

Añadir en `backend/src/intelligence/spotter.py` dentro de `evaluate()`, ANTES del chequeo de garaje (para que funcione incluso al salir del garaje, donde throttle > 0 pero in_pits=True):

```python
    def evaluate(self, tick: dict) -> List[AlertMessage]:
        """Evalúa condiciones deterministas en el tick de telemetría (50ms).
        
        NOTA: _was_in_garage se inicializa en __init__ como True.
        Si en el primer tick el coche YA está en pit lane en movimiento
        (ej: conexión tardía), se ajusta inmediatamente para evitar
        que el audio test se dispare falsamente.
        """
        in_pits = tick.get("in_pits", False)
        throttle = tick.get("throttle", 0.0)
        speed = tick.get("speed", 0.0)
        lap_distance = tick.get("lap_distance", 0.0)
        
        is_moving_in_pits = (
            in_pits
            and throttle > 0.05
            and (speed > 1.0 or lap_distance > 5.0)
        )
        is_in_garage_now = (
            in_pits
            and throttle < 0.05
            and (speed < 1.0 or lap_distance < 5.0)
        )
        
        # Primer tick: si el coche YA está en movimiento en pits, no es transición
        # _was_in_garage arranca como True en __init__; lo corregimos aquí
        if self._was_in_garage and is_moving_in_pits and not is_in_garage_now:
            if hasattr(self, '_first_tick_done'):
                # NO es el primer tick: transición real garaje → pit lane
                # El audio test se generará abajo
                pass
            else:
                # Es el primer tick y el coche ya está en movimiento:
                # ajustar _was_in_garage sin disparar audio test
                self._was_in_garage = False
                self._first_tick_done = True
        
        if not hasattr(self, '_first_tick_done'):
            self._first_tick_done = True
        
        # Actualizar estado: el _was_in_garage del PRÓXIMO tick
        was_in_garage = self._was_in_garage
        self._was_in_garage = is_in_garage_now
        
        # Silenciar si está en garaje
        if is_in_garage_now:
            return []
        
        alerts = []
        
        # Trigger "Probando audio": transición garaje → pit lane
        if was_in_garage and is_moving_in_pits and not is_in_garage_now:
            alerts.append(self._create_alert(
                message="Probando audio, radio del ingeniero verificada.",
                severity="INFO",
                audio_priority=1,
                ttl=60,  # Largo cooldown: no repetir por 60s
                dismissable=True,
                category="audio_test",
                payload={"throttle": throttle, "speed": speed}
            ))
        
        # 1. Pit limiter no activado al entrar en boxes
        ...
```

MUY IMPORTANTE: Asegurarse de que el trigger de audio test USA el cooldown (ttl=60). Cuando el piloto sale del garaje y acelera en el pit lane, se dispara una vez. No se repite hasta 60s después.

- [ ] **Step 4: Ejecutar tests de audio test**

Run:
```bash
cd backend && python -m pytest tests/test_spotter.py::TestSpotterAudioTestTrigger -v
```

Expected: 3 tests PASSING.

- [ ] **Step 5: Verificar cooldown de audio test**

```bash
cd backend && python -m pytest tests/test_spotter.py::TestSpotterCooldown -v
```

Expected: Tests de cooldown existentes y nuevos pasando.

- [ ] **Step 6: Commit**

```bash
git add backend/src/intelligence/spotter.py backend/tests/test_spotter.py
git commit -m "feat(spotter): add 'Probando audio' trigger when exiting garage

Detecta transicion garaje (in_pits + throttle=0 + speed=0) a pit lane
en movimiento (in_pits + throttle>0 + speed>0). Genera alerta con
categoria audio_test y TTL de 60s para evitar repeticion.

Cooldown largo asegura que solo suene una vez al inicio de sesion."
```

---

### Task 3: Script de limpieza de procesos zombies + reinicio limpio

**Files:**
- Create: `backend/kill_and_restart.py`

**Problema:** Múltiples reinicios del backend dejan procesos zombies que siguen escuchando en el puerto 8008. Cuando el frontend conecta, puede recibir respuestas de un backend viejo sin las correcciones.

**Solución:** Script que mata TODOS los procesos python que tengan `run_dev.py` en su línea de comandos, espera a que el puerto se libere, y reinicia.

- [ ] **Step 1: Crear script de reinicio limpio**

Crear `backend/kill_and_restart.py`:

```python
"""
Kill all running backend instances and restart cleanly.
Use this when zombie backends are causing issues.

Usage:
    python kill_and_restart.py
"""
import os
import subprocess
import sys
import time

PORT = 8008
SCRIPT = "run_dev.py"

def find_backend_pids():
    """Find all PIDs running our backend script."""
    pids = set()
    
    # Method 1: Find by port (most reliable on Windows)
    try:
        result = subprocess.run(
            ['netstat', '-ano'], capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split('\n'):
            if f':{PORT}' in line and 'LISTENING' in line:
                parts = line.strip().split()
                try:
                    pid = int(parts[-1])
                    if pid > 0:
                        pids.add(pid)
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    
    # Method 2: Find by script name via tasklist
    try:
        result = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq python.exe', '/NH'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split('\n'):
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    pid = int(parts[1])
                    pids.add(pid)
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    
    return pids

def kill_pids(pids):
    """Kill processes by PID using taskkill (Windows-compatible)."""
    for pid in pids:
        try:
            result = subprocess.run(
                ['taskkill', '/F', '/PID', str(pid)],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                print(f"  Killed PID {pid}")
            else:
                print(f"  Could not kill PID {pid}: {result.stderr.strip()}")
        except Exception as e:
            print(f"  Could not kill PID {pid}: {e}")

def wait_for_port_free(port, timeout=10):
    """Wait until the port is free."""
    for i in range(timeout):
        try:
            result = subprocess.run(
                ['netstat', '-ano'], capture_output=True, text=True, timeout=5
            )
            if f':{port}' not in result.stdout or 'LISTENING' not in result.stdout:
                return True
        except Exception:
            pass
        print(f"  Waiting for port {port} to be free... ({i+1}s)")
        time.sleep(1)
    return False

def restart_backend():
    """Start the backend fresh (Windows-compatible)."""
    backend_dir = os.path.join(os.path.dirname(__file__))
    python = sys.executable
    script = os.path.join(backend_dir, SCRIPT)
    # DETACHED_PROCESS = 0x00000008, CREATE_NEW_PROCESS_GROUP = 0x00000200
    flags = 0x00000008 | 0x00000200 if sys.platform == 'win32' else 0
    subprocess.Popen(
        [python, script],
        cwd=backend_dir,
        creationflags=flags
    )
    print("  Backend restarted")

if __name__ == "__main__":
    print("=" * 50)
    print("  BACKEND KILL & RESTART")
    print("=" * 50)
    
    print("\n[1] Finding backend processes...")
    pids = find_backend_pids()
    if pids:
        print(f"  Found {len(pids)} backend PID(s): {pids}")
        kill_pids(pids)
    else:
        print("  No backend processes found")
    
    print("\n[2] Waiting for port to be free...")
    if wait_for_port_free(PORT):
        print(f"  Port {PORT} is free")
    else:
        print(f"  WARNING: Port {PORT} still in use after timeout")
    
    print("\n[3] Restarting backend...")
    restart_backend()
    
    print("\n[4] Waiting for backend to be ready...")
    time.sleep(5)
    try:
        import requests
        r = requests.get(f"http://127.0.0.1:{PORT}/health", timeout=5)
        if r.status_code == 200:
            d = r.json()
            print(f"  Backend ready! Status: {d['status']}, Offline: {d['shared_memory']['offline_mode']}")
        else:
            print(f"  Backend responded with status {r.status_code}")
    except Exception as e:
        print(f"  Backend not ready yet: {e}")
    
    print("\n" + "=" * 50)
    print("  DONE - Backend reiniciado")
    print(f"  Frontend: npm run tauri dev (en frontend/)")
    print("=" * 50)
```

- [ ] **Step 2: Probar que mata los procesos zombies**

Ejecutar estando el backend corriendo:
```bash
cd backend && python kill_and_restart.py
```

Verificar:
- Old PIDs are killed
- Port is freed
- New backend starts
- Health endpoint responds

- [ ] **Step 3: Commit**

```bash
git add backend/kill_and_restart.py
git commit -m "chore: add kill_and_restart.py for clean backend restarts

Mata todos los procesos zombies del backend, espera a que el puerto
8008 se libere, y reinicia limpiamente. Soluciona el problema de
multiples backends escuchando en el mismo puerto tras reinicios."
```

---

### Task 4: Ejecutar plan completo y verificar

**Files:** Ninguno (solo ejecución)

- [ ] **Step 1: Matar backends zombies**

```bash
cd backend && python kill_and_restart.py
```

- [ ] **Step 2: Verificar que solo hay 1 backend**

```bash
netstat -ano | findstr ":8008" | findstr "LISTENING"
```
Expected: Solo 1 PID.

- [ ] **Step 3: Ejecutar todos los tests**

```bash
cd backend && python -m pytest tests/test_spotter.py tests/test_ws_integration.py tests/test_spotter_to_tts_flow.py -v
```
Expected: Todos pasando.

- [ ] **Step 4: Abrir frontend**

```bash
cd frontend && npm run tauri dev
```

- [ ] **Step 5: Verificar en vivo**
- Con LMU abierto, entrar al coche en el garaje
- Acelerar en el pit lane → debe sonar "Probando audio, radio del ingeniero verificada"
- Esperar 10s → no debe repetirse el audio test
- Salir a pista → spotter debe generar alertas de gaps, SC, etc. con cooldown

---

### Resumen de Archivos Modificados/Creados

| Archivo | Acción | Propósito |
|---------|--------|-----------|
| `backend/src/intelligence/spotter.py` | Modificar | Añadir `try_broadcast()`, trigger "Probando audio", estado `_was_in_garage` |
| `backend/src/intelligence/engine.py` | Modificar | ALERT_ONLY usa `spotter.try_broadcast()` en vez de `broadcaster.send()` directo |
| `backend/tests/test_spotter.py` | Modificar | Tests de cooldown compartido y trigger audio test |
| `backend/kill_and_restart.py` | Crear | Script de limpieza de zombies + reinicio |
