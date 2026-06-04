# CrewChief-Style Rewrite — Plan de Implementación

> **For agentic workers:** This plan is sequential. Tasks MUST be executed in order. Each task depends on the previous.

**Goal:** Reestructurar el pipeline de datos para que funcione como CrewChief: un solo Flat Dict con todos los campos de LMU (shared memory + REST API) leído a 20Hz, spotter determinista puro, y LLM pipeline simple con rolling history.

**Architecture:**
```
LMU Shared Memory (20Hz) ──┐
                            ├──→ LMUReader → Flat Dict (cada 50ms) ~80 campos
LMU REST API (async 3s) ──┘         │
                                      ├──→ SPOTTER (determinista puro)
                                      │       ├── alertas urgentes → TTS directo 🗣️
                                      │       └── cond. estratégicas → ProactiveManager
                                      │
                                      ├──→ PROACTIVE MANAGER
                                      │       ├── 18 triggers con prioridad y cooldown
                                      │       ├── detecta transiciones (no estados absolutos)
                                      │       └── LLM → consejo → TTS 🗣️
                                      │
                                      ├──→ ROLLING HISTORY
                                      │       ├── lap snapshots (deque 30)
                                      │       └── event log (deque 50)
                                      │
                                      └──→ LLM REACTIVO (pregunta del piloto)
                                              prompt: system + Flat Dict JSON + snapshots + eventos
                                              ~2.5K tokens, sin RAG, sin ChromaDB
```

**Tech Stack:** Python 3.12, FastAPI, ctypes (shared memory), httpx (REST API), asyncio

**Correcciones post-revision (5 revisores):**
1. ❌ **Eliminar `gap_computer.py`** — LMU ya computa `mTimeGapCarAhead/Behind` en shared memory
2. ✅ **Leer gaps directo**: `time_gap_car_ahead`, `time_gap_car_behind`, `time_gap_place_ahead`, `time_gap_place_behind`, `time_behind_leader`
3. ✅ **Leer `mPitState`** (0=none, 1=request, 2=entering, 3=stopped, 4=exiting) y `mInGarageStall` — más granular que `in_pits`
4. ✅ **Leer `mFuelFraction`** — combustible como fracción directa
5. ✅ **Leer `mBatteryChargeFraction` / `mStateOfCharge`** — batería en ambos formatos
6. ✅ **Leer `mDRSState`, `mNumPenalties`, `mNumPitstops`, `mLastImpactMagnitude`** — estado completo
7. ✅ **REST API via `asyncio.create_task`** — no mezclar con thread de shared memory
8. ✅ **Mantener `pyLMUSharedMemory`** — el sidecar lo necesita. Solo limpiar modelos RaceState/etc.
9. ✅ **Modo proactivo**: Spotter detecta condiciones → ProactiveManager → LLM genera consejo
10. ✅ **Flat Dict COMPLETO al LLM**: no resumir, mandar el JSON plano (~600 tokens)

**Lo que se elimina:**
- `shared-telemetry/` completo (RaceState, VehicleData, etc.)
- `shared-strategy/` completo (TelemetryFrame, StrategyState, etc.)
- `backend/src/services/strategy_service.py`
- `backend/src/intelligence/live_context.py`
- `backend/src/intelligence/context_builder.py`
- `backend/src/intelligence/prompt_templates.py`
- `backend/src/intelligence/ticker.py`
- `backend/src/persistence/` (EventStore/ChromaDB)
- `backend/src/services/lmu_api.py` (reemplazado por LMUReader)
- `backend/src/routers/websocket.py` enrichment

**Lo que se crea:**
- `backend/src/services/lmu_reader.py` — FlatDictBuilder + LMUReader
- `backend/src/services/fuel_computer.py` — rolling average 5 laps
- `backend/src/services/gap_computer.py` — desde opponents
- `backend/src/services/ticker_builder.py` — FlatDict → ticker string
- `backend/src/services/rolling_history.py` — deque de snapshots + eventos
- `backend/src/intelligence/llm_pipeline.py` — prompt simple + streaming
- `backend/src/intelligence/profiles.py` — carga de perfiles desde JSON
- `backend/profiles/` — directorio con perfiles .json

**Lo que se modifica:**
- `backend/src/intelligence/spotter.py` — leer Flat Dict directamente
- `backend/src/routers/websocket.py` — eliminar enrichment
- `backend/src/main.py` — nuevo initialization
- `backend/src/routers/llm.py` — usar nuevo pipeline
- `frontend/src/store/config.ts` — selector de personalidad

---

### Task 1: LMUReader — Flat Dict desde shared memory + REST API

**Files:**
- Create: `backend/src/services/lmu_reader.py`
- Delete (eventually): `shared-telemetry/`, `backend/src/services/lmu_api.py`

**Problema:** Actualmente los datos viajan por 3 pipelines paralelos (RaceState, TelemetryFrame, REST API caches) y se pierden campos en cada transformación.

**Solución:** Un solo `LMUReader` que lee shared memory a 20Hz y REST API cada 3s, y produce un Flat Dict plano con TODOS los campos.

**Formato del Flat Dict:**

```python
flat_dict = {
    # Sesión
    "session_type": "race",           # practice/qualify/race
    "session_time_remaining": 3600.0, # segundos
    "session_laps_total": 30,         # vueltas totales
    "session_laps_left": 15.0,        # vueltas restantes
    "track_name": "Algarve International Circuit",
    "track_length": 7004.0,           # metros
    
    # Jugador
    "driver_name": "Isaac Albala",
    "vehicle_name": "Akkodis ASP Team 2025 #78:LM",
    "vehicle_class": "GT3",
    "place": 3,
    "total_laps": 15,
    "lap_number": 16,
    "lap_distance": 500.0,            # metros en la vuelta actual
    "track_progress": 0.07,
    "in_pits": False,
    "pit_limiter_active": False,
    "speed": 72.5,                    # m/s
    "rpm": 6500.0,
    "gear": 4,
    "throttle": 0.85,
    "brake_input": 0.0,
    "steering": 0.02,
    "pos_x": 100.0, "pos_y": 0.0, "pos_z": 50.0,
    
    # Neumáticos [FL, FR, RL, RR]
    "tyre_compound": ["Medium", "Medium", "Medium", "Medium"],
    "tyre_wear": [10.0, 12.0, 8.0, 9.0],      # 0-100%
    "tyre_temp": [85.0, 86.0, 84.0, 85.0],     # Celsius
    "tyre_pressure": [200.0, 201.0, 202.0, 203.0],
    
    # Frenos
    "brake_temp": [300.0, 305.0, 290.0, 295.0],
    "brake_pressure": [0.5, 0.5, 0.3, 0.3],
    "brake_wear": [15.0, 15.0, 12.0, 12.0],   # 0-100% desde REST API
    
    # Combustible
    "fuel_in_tank": 42.3,
    "fuel_capacity": 100.0,
    "fuel_used_lap": 3.2,
    
    # Híbrido
    "battery_charge": 72.0,
    "motor_state": 2,  # 1=idle, 2=drain, 3=regen
    
    # Banderas
    "safety_car_active": False,
    "full_course_yellow_active": False,
    "yellow_flag_active": False,
    
    # Daños (desde REST API)
    "aero_damage": 5.0,              # 0-100%
    "suspension_wear": [3.0, 3.0, 2.0, 2.0],
    
    # Clima (desde shared memory)
    "track_temp": 31.2,
    "ambient_temp": 22.5,
    "rain_intensity": 0.0,
    "wetness": 0.0,
    "cloud_coverage": 2,
    "track_grip": 1.0,
    
    # Gaps (computados)
    "gap_ahead": 1.2,                # segundos
    "gap_behind": 3.5,
    
    # Rivales (cercanos, 3+3)
    "rivals": [
        {"name": "RivalA", "place": 2, "gap": 1.2, "in_pits": False, "lap": 16, "speed": 72.0, "class": "GT3"},
        {"name": "RivalB", "place": 4, "gap": 3.5, "in_pits": False, "lap": 15, "speed": 70.0, "class": "GT3"},
    ],
    
    # Flags computados
    "is_last_lap": False,
    "estimated_laps_remaining": 13.5,
    
    # Timestamp
    "_t": 1234567890.0,  # monotonic
}
```

**Implementación del LMUReader:**

```python
# backend/src/services/lmu_reader.py
class LMUReader:
    """Lee shared memory de LMU a 20Hz + REST API cada 3s.
    
    Produce un Flat Dict plano con TODOS los campos disponibles.
    """
    
    def __init__(self, offline: bool = False):
        self.offline = offline
        self._shmm = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._latest: dict = {}
        
        # Caches para REST API
        self._garage_cache: dict = {}
        self._garage_updated: float = 0.0
        
        if not offline:
            from shared_telemetry.pyLMUSharedMemory.lmu_mmap import MMapControl
            from shared_telemetry.pyLMUSharedMemory.lmu_data import LMUObjectOut, LMUConstants
            self._shmm = MMapControl(LMUConstants.LMU_SHARED_MEMORY_FILE, LMUObjectOut)
        
        # Pre-poblar con defaults seguros
        self._latest = self._default_flat_dict()
    
    def _default_flat_dict(self) -> dict:
        return {
            "session_type": "race", "session_time_remaining": 0.0,
            "session_laps_total": 0, "session_laps_left": 0.0,
            "track_name": "", "track_length": 7004.0,
            "driver_name": "", "vehicle_name": "", "vehicle_class": "",
            "place": 1, "total_laps": 0, "lap_number": 0,
            "lap_distance": 0.0, "track_progress": 0.0,
            "in_pits": False, "pit_limiter_active": False,
            "speed": 0.0, "rpm": 0.0, "gear": 0,
            "throttle": 0.0, "brake_input": 0.0, "steering": 0.0,
            "pos_x": 0.0, "pos_y": 0.0, "pos_z": 0.0,
            "tyre_compound": ["","","",""],
            "tyre_wear": [0.0,0.0,0.0,0.0],
            "tyre_temp": [25.0,25.0,25.0,25.0],
            "tyre_pressure": [200.0,200.0,200.0,200.0],
            "brake_temp": [30.0,30.0,30.0,30.0],
            "brake_pressure": [0.0,0.0,0.0,0.0],
            "brake_wear": [0.0,0.0,0.0,0.0],
            "fuel_in_tank": 100.0, "fuel_capacity": 100.0,
            "fuel_used_lap": 0.0,
            "battery_charge": 100.0, "motor_state": 1,
            "safety_car_active": False, "full_course_yellow_active": False,
            "yellow_flag_active": False,
            "aero_damage": 0.0, "suspension_wear": [0.0,0.0,0.0,0.0],
            "track_temp": 25.0, "ambient_temp": 20.0,
            "rain_intensity": 0.0, "wetness": 0.0,
            "cloud_coverage": 0, "track_grip": 1.0,
            "gap_ahead": 99.0, "gap_behind": 99.0,
            "rivals": [],
            "is_last_lap": False, "estimated_laps_remaining": 99.0,
            "_t": 0.0
        }
    
    def _read_shared_memory(self) -> dict:
        """Lee shared memory y construye Flat Dict."""
        result = {}
        data = self._shmm.data
        if not data:
            return result
        
        scoring = data.scoring.scoringInfo
        # Sincronizar indices
        from shared_telemetry.sync import TelemetrySync
        sync = TelemetrySync()
        scor_idx, tele_idx, player_scor, player_tele = sync.sync_player_data(data)
        
        # Session info
        result["session_type"] = self._session_type_str(scoring.mSession)
        result["session_time_remaining"] = float(scoring.mSessionTimeRemaining)
        result["session_laps_total"] = int(scoring.mMaxLaps)
        result["session_laps_left"] = max(0.0, float(scoring.mMaxLaps - (player_scor.mTotalLaps if player_scor else 0)))
        result["track_name"] = self._bytes_str(scoring.mTrackName)
        result["track_length"] = float(scoring.mLapDist) if scoring.mLapDist > 10.0 else 7004.0
        
        if player_scor:
            result["place"] = int(player_scor.mPlace)
            result["total_laps"] = int(player_scor.mTotalLaps)
            result["lap_number"] = int(player_scor.mTotalLaps + 1)
            result["lap_distance"] = float(player_scor.mLapDist)
            result["track_progress"] = float(player_scor.mLapDist / scoring.mLapDist) if scoring.mLapDist > 0 else 0.0
            result["in_pits"] = bool(player_scor.mInPits)
            result["driver_name"] = self._bytes_str(player_scor.mDriverName)
            result["vehicle_name"] = self._bytes_str(player_scor.mVehicleName)
            result["vehicle_class"] = self._bytes_str(player_scor.mVehicleClass)
            result["pos_x"] = float(player_scor.mPos.x)
            result["pos_y"] = float(player_scor.mPos.y)
            result["pos_z"] = float(player_scor.mPos.z)
        
        if player_tele:
            result["pit_limiter_active"] = bool(player_tele.mSpeedLimiterActive)
            result["speed"] = math.sqrt(
                float(player_tele.mLocalVel.x)**2 + float(player_tele.mLocalVel.y)**2 + float(player_tele.mLocalVel.z)**2
            )
            result["rpm"] = float(player_tele.mEngineRPM)
            result["gear"] = int(player_tele.mGear)
            result["throttle"] = float(player_tele.mFilteredThrottle)
            result["brake_input"] = float(player_tele.mFilteredBrake)
            result["steering"] = float(player_tele.mFilteredSteering)
            result["fuel_in_tank"] = float(player_tele.mFuel)
            result["fuel_capacity"] = float(player_tele.mFuelCapacity)
            result["battery_charge"] = float(player_tele.mStateOfCharge)
            result["motor_state"] = int(player_tele.mElectricBoostMotorState)
            
            # Neumaticos
            for i in range(4):
                w = player_tele.mWheels[i]
                result["tyre_wear"][i] = float(w.mWear)
                result["tyre_temp"][i] = float(w.mTireCarcassTemperature - 273.15)
                result["tyre_pressure"][i] = float(w.mPressure)
                result["brake_temp"][i] = float(w.mBrakeTemp - 273.15)
                result["brake_pressure"][i] = float(w.mBrakePressure)
        
        # Banderas
        game_phase = int(scoring.mGamePhase)
        result["safety_car_active"] = (game_phase == 6)
        result["full_course_yellow_active"] = (game_phase == 6)
        result["yellow_flag_active"] = (game_phase == 6 or any(scoring.mSectorFlag[i] != 0 for i in range(3)))
        
        # Clima desde shared memory
        result["track_temp"] = float(scoring.mTrackTemp)
        result["ambient_temp"] = float(scoring.mAmbientTemp)
        result["rain_intensity"] = float(scoring.mRaining)
        result["wetness"] = float(scoring.mAvgPathWetness)
        
        # Rivales (todos, el gap computer filtrara 3+3)
        rivals = []
        veh_total = min(int(scoring.mNumVehicles), len(data.scoring.vehScoringInfo))
        for idx in range(veh_total):
            veh = data.scoring.vehScoringInfo[idx]
            if veh.mID > 0 and not veh.mIsPlayer:
                opp_tele_idx = sync._tele_indexes.get(veh.mID, -1)
                opp_speed = 0.0
                if opp_tele_idx != -1 and opp_tele_idx < len(data.telemetry.telemInfo):
                    opp_tele = data.telemetry.telemInfo[opp_tele_idx]
                    opp_speed = math.sqrt(
                        float(opp_tele.mLocalVel.x)**2 + float(opp_tele.mLocalVel.y)**2 + float(opp_tele.mLocalVel.z)**2
                    )
                rivals.append({
                    "name": self._bytes_str(veh.mDriverName),
                    "place": int(veh.mPlace),
                    "lap": int(veh.mTotalLaps + 1),
                    "lap_distance": float(veh.mLapDist),
                    "in_pits": bool(veh.mInPits),
                    "speed": opp_speed,
                    "class": self._bytes_str(veh.mVehicleClass),
                })
        result["rivals"] = rivals
        
        result["_t"] = time.monotonic()
        return result
    
    def _read_rest_api(self):
        """Lee REST API (async) y actualiza caches."""
        import httpx
        try:
            r = httpx.get("http://localhost:6397/rest/garage/UIScreen/RepairAndRefuel", timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                wearables = data.get("wearables", {})
                body = wearables.get("body", {})
                brakes = wearables.get("brakes", [])
                suspension = wearables.get("suspension", [])
                
                garage = {
                    "aero_damage": float(body.get("aero", 0.0)) * 100.0,
                    "brake_wear": [float(b) * 100.0 for b in brakes[:4]] if len(brakes) >= 4 else [0.0]*4,
                    "suspension_wear": [float(s) * 100.0 for s in suspension[:4]] if len(suspension) >= 4 else [0.0]*4,
                }
                with self._lock:
                    self._garage_cache = garage
                    self._garage_updated = time.monotonic()
        except Exception:
            pass
    
    def get_flat_dict(self) -> dict:
        """Devuelve el ultimo Flat Dict disponible (thread-safe)."""
        with self._lock:
            result = dict(self._latest)
            # Merge garage cache
            result.update(self._garage_cache)
            return result
    
    def _session_type_str(self, t: int) -> str:
        return {0: "test", 1: "practice", 2: "qualifying", 3: "warmup", 4: "race"}.get(t, "race")
    
    def _bytes_str(self, b) -> str:
        if isinstance(b, bytes):
            return b.decode("utf-8", errors="replace").rstrip("\0 ").rstrip()
        return str(b) if b else ""
```

**Tests:**
```python
class TestFlatDictDefaults:
    def test_all_fields_present(self):
        reader = LMUReader(offline=True)
        d = reader.get_flat_dict()
        required = ["session_type", "track_name", "driver_name", "place", "lap_number",
                    "in_pits", "speed", "throttle", "fuel_in_tank", "battery_charge",
                    "tyre_wear", "tyre_temp", "brake_temp", "brake_wear",
                    "safety_car_active", "gap_ahead", "gap_behind", "rivals",
                    "aero_damage", "suspension_wear", "is_last_lap",
                    "estimated_laps_remaining"]
        for field in required:
            assert field in d, f"Missing field: {field}"
    
    def test_tyre_wear_is_list_of_4(self):
        reader = LMUReader(offline=True)
        d = reader.get_flat_dict()
        assert len(d["tyre_wear"]) == 4
```

Commit: `feat(lmu_reader): add LMUReader with flat dict from shared memory + REST API`

---

### Task 2: GapComputer + FuelComputer — computar campos derivados

**Files:**
- Create: `backend/src/services/gap_computer.py`
- Create: `backend/src/services/fuel_computer.py`

**GapComputer:** Toma el Flat Dict (con `rivals[]`) y computa `gap_ahead`, `gap_behind`, y filtra rivals a 3+3.

```python
class GapComputer:
    def compute(self, d: dict) -> dict:
        result = {}
        player_place = d.get("place", 1)
        player_lap = d.get("lap_number", 1)
        player_dist = d.get("lap_distance", 0.0)
        player_speed = d.get("speed", 1.0)
        track_len = d.get("track_length", 7004.0)
        rivals = d.get("rivals", [])
        
        if player_speed < 0.1:
            player_speed = 1.0
        
        player_total = (player_lap - 1) * track_len + player_dist
        gaps = {"ahead": 99.0, "behind": 99.0}
        ahead = []  # Rivals con place < player_place
        behind = []  # Rivals con place > player_place
        
        for r in rivals:
            r_total = (r["lap"] - 1) * track_len + r["lap_distance"]
            diff = r_total - player_total
            time_gap = abs(diff) / player_speed if diff != 0 else 99.0
            
            r["gap"] = round(time_gap, 1)
            
            if r["place"] < player_place:
                ahead.append(r)
            elif r["place"] > player_place:
                behind.append(r)
        
        # Ordenar por posicion
        ahead.sort(key=lambda x: x["place"], reverse=True)  # Mas cercano primero
        behind.sort(key=lambda x: x["place"])
        
        if ahead:
            result["gap_ahead"] = ahead[0]["gap"]
        if behind:
            result["gap_behind"] = behind[0]["gap"]
        
        # Top 3 mas cercanos
        result["rivals"] = ahead[:3] + behind[:3]
        result["rivals"].sort(key=lambda x: x["place"])
        
        return result
```

**FuelComputer:** Rolling average de las últimas 5 vueltas.

```python
class FuelComputer:
    def __init__(self, window=5):
        self.window = window
        self._consumptions: list[float] = []
        self._last_lap = 0
    
    def compute(self, d: dict) -> dict:
        result = {}
        current_lap = d.get("lap_number", 0)
        fuel = d.get("fuel_in_tank", 0.0)
        
        # Detectar cruce de linea de meta
        lap_dist = d.get("lap_distance", 0.0)
        track_len = d.get("track_length", 7004.0)
        if self._last_lap > 0 and current_lap > self._last_lap and self._lap_fuel_start:
            used = self._lap_fuel_start - fuel
            if used > 0:
                self._consumptions.append(used)
                if len(self._consumptions) > self.window:
                    self._consumptions.pop(0)
        
        if d.get("lap_distance", 0) < 50 and current_lap != self._last_lap:
            self._lap_fuel_start = fuel
        
        self._last_lap = current_lap
        
        if self._consumptions:
            avg = sum(self._consumptions) / len(self._consumptions)
            result["estimated_laps_remaining"] = round(fuel / avg, 1) if avg > 0 else 99.0
        else:
            result["estimated_laps_remaining"] = 99.0
        
        return result
```

---

### Task 3: TickerBuilder — Flat Dict → ticker string

**Files:**
- Create: `backend/src/services/ticker_builder.py`

```python
class TickerBuilder:
    """Comprime Flat Dict a formato ticker (~120 bytes, ~40 tokens)."""
    
    def build(self, d: dict) -> str:
        # L{vuelta}|P{pos}|F{combustible}({vueltas})|T{desgastes}@{temps}
        # |G{+gap}/{rival}|B{-gap}|SC:{S/N}|DMG:{dano}|WTH:{temp}/{lluvia}
        # |RIV:{rival1}|{rival2}|{rival3}
        
        lap = d.get("lap_number", 0)
        place = d.get("place", 1)
        fuel = d.get("fuel_in_tank", 0)
        laps_left = d.get("estimated_laps_remaining", 99)
        wear = ",".join(str(int(w)) for w in d.get("tyre_wear", [0]*4))
        temps = ",".join(str(int(t)) for t in d.get("tyre_temp", [0]*4))
        gap_a = d.get("gap_ahead", 99)
        gap_b = d.get("gap_behind", 99)
        sc = "S" if d.get("safety_car_active") else "N"
        dmg = int(d.get("aero_damage", 0))
        temp = int(d.get("track_temp", 25))
        rain = int(d.get("rain_intensity", 0) * 100)
        
        # Rivales: 3 delante + 3 detras, formato "NOM:POS:GAP"
        rivals = d.get("rivals", [])
        riv_str = "|".join(
            f"{self._abbrev(r['name'])}:{r['place']}:{r.get('gap', 99)}"
            for r in rivals[:6]
        )
        
        parts = [
            f"L{lap}|P{place}",
            f"F{round(fuel,1)}({int(laps_left)})",
            f"T{wear}@{temps}",
            f"G+{gap_a}" if gap_a < 99 else "G+--",
            f"B-{gap_b}" if gap_b < 99 else "B---",
            f"SC:{sc}",
            f"DMG:{dmg}",
            f"WTH:{temp}C/{rain}%",
        ]
        if riv_str:
            parts.append(f"RIV:{riv_str}")
        
        return "|".join(parts)
    
    def _abbrev(self, name: str) -> str:
        """Abrevia nombre a 3 chars (ej: Isaac Albala -> ISA)."""
        parts = name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][:2]).upper()[:3]
        return name[:3].upper()
```

---

### Task 4: RollingHistory — snapshots + eventos

**Files:**
- Create: `backend/src/services/rolling_history.py`

```python
from collections import deque

class RollingHistory:
    """Buffer circular de snapshots por vuelta + eventos."""
    
    def __init__(self, max_snapshots=30, max_events=50):
        self._snapshots: deque[dict] = deque(maxlen=max_snapshots)
        self._events: deque[dict] = deque(maxlen=max_events)
        self._last_lap = 0
        self._ticker_builder = TickerBuilder()
    
    def update(self, d: dict):
        """Procesa un nuevo Flat Dict. Detecta cruce de meta y eventos."""
        current_lap = d.get("lap_number", 0)
        
        # Snapshot por vuelta (al cruzar linea de meta)
        if current_lap > self._last_lap and self._last_lap > 0:
            snapshot = self._ticker_builder.build(d)
            self._snapshots.append(snapshot)
        
        # Detectar eventos de cambio de posicion
        if current_lap > self._last_lap and self._last_lap > 0:
            self._events.append({"t": time.time(), "type": "lap_completed", "lap": current_lap})
        
        # Detectar safety car
        if d.get("safety_car_active") and not self._last_sc:
            self._events.append({"t": time.time(), "type": "safety_car", "lap": current_lap})
        self._last_sc = d.get("safety_car_active", False)
        
        # Detectar entrada/salida de pits
        if d.get("in_pits") and not self._last_in_pits:
            self._events.append({"t": time.time(), "type": "pit_entry", "lap": current_lap})
        elif not d.get("in_pits") and self._last_in_pits:
            self._events.append({"t": time.time(), "type": "pit_exit", "lap": current_lap})
        self._last_in_pits = d.get("in_pits", False)
        
        self._last_lap = current_lap
    
    def get_context(self, max_snapshots=5, max_events=10) -> dict:
        """Devuelve contexto para el prompt del LLM."""
        return {
            "snapshots": list(self._snapshots)[-max_snapshots:],
            "events": list(self._events)[-max_events:],
        }
```

---

### Task 5: SpotterService simplificado — lee Flat Dict directamente

**Files:**
- Modify: `backend/src/intelligence/spotter.py`

**Cambio:** El spotter ahora recibe el Flat Dict directamente (no necesita `_to_flat_dict` ni `evaluate_tick`). Se simplifica a solo `evaluate()`.

```python
class SpotterService:
    """Spotter determinista puro. Lee Flat Dict directamente.
    
    8 condiciones + audio test. Cooldown por categoria.
    """
    
    def __init__(self, broadcast_callback=None):
        self.broadcast_callback = broadcast_callback
        self._last_fired: dict[str, float] = {}
        self._was_in_garage = True
    
    def evaluate(self, d: dict) -> list[AlertMessage]:
        alerts = []
        in_pits = d.get("in_pits", False)
        throttle = d.get("throttle", 0.0)
        speed = d.get("speed", 0.0)
        
        # Garaje
        is_in_garage = in_pits and throttle < 0.05 and speed < 1.0
        was_garage = self._was_in_garage
        self._was_in_garage = is_in_garage
        if is_in_garage:
            return []
        
        # Audio test al salir del garaje
        if was_garage and not is_in_garage and in_pits:
            alerts.append(self._alert("Probando audio, radio del ingeniero verificada.", "audio_test", 60))
        
        # 1. Pit limiter
        if in_pits and not d.get("pit_limiter_active"):
            alerts.append(self._alert("Pit limiter no activado al entrar en boxes.", "limiter", 5, "CRITICAL"))
        if not in_pits and d.get("pit_limiter_active"):
            alerts.append(self._alert("Pit limiter no desactivado al salir de boxes.", "limiter", 5, "WARNING"))
        
        # 2. Gaps
        ga = d.get("gap_ahead", 99.0)
        gb = d.get("gap_behind", 99.0)
        if ga < 0.5:
            alerts.append(self._alert(f"Gap con coche de delante estrecho: {ga:.2f}s", "gaps", 3, "INFO"))
        if gb < 0.5:
            alerts.append(self._alert(f"Gap con coche de detrás estrecho: {gb:.2f}s", "gaps", 3, "INFO"))
        
        # 3. Daños
        if d.get("aero_damage", 0) > 0 or max(d.get("suspension_wear", [0])) > 0:
            alerts.append(self._alert("Daños detectados en el monoplaza.", "damage", 10, "WARNING"))
        
        # 4. Safety Car
        if d.get("safety_car_active") or d.get("full_course_yellow_active"):
            alerts.append(self._alert("Safety car desplegado / FCY activo.", "safety_car", 15, "CRITICAL"))
        
        # 5. Ultima vuelta
        if d.get("is_last_lap") or d.get("session_laps_left") == 1:
            alerts.append(self._alert("¡Última vuelta de la carrera!", "session", 10, "HIGH"))
        
        # 6. Combustible critico
        if d.get("estimated_laps_remaining", 99) < 1:
            alerts.append(self._alert(f"¡Combustible crítico! Menos de 1 vuelta.", "fuel", 10, "CRITICAL"))
        
        return alerts
    
    def _alert(self, msg, cat, ttl, severity="INFO"):
        return AlertMessage(
            event="alert", alert_id=str(uuid.uuid4()),
            category=cat, message=msg,
            audio_priority={"CRITICAL":4,"HIGH":3,"WARNING":2,"INFO":1}.get(severity, 1),
            severity=severity, ttl=ttl, dismissable=True,
            payload={"severity": severity, "ttl": ttl, "dismissable": True}
        )
    
    def try_broadcast(self, alert: AlertMessage) -> bool:
        # Cooldown por categoria
        cat = getattr(alert, 'category', 'unknown')
        ttl = alert.payload.get('ttl', 3) if alert.payload else 3
        now = time.monotonic()
        last = self._last_fired.get(cat, 0.0)
        if now - last >= ttl:
            self._last_fired[cat] = now
            if self.broadcast_callback:
                self.broadcast_callback(alert)
            return True
        return False
```

---

### Task 5b: ProactiveManager — 18 triggers estratégicos + LLM proactivo

**Files:**
- Create: `backend/src/services/proactive_manager.py`

**Problema:** El spotter solo genera alertas directas (frases fijas). No hay análisis estratégico contextual (ej: "Safety Car, los rivales de delante entraron a boxes, recomiendo parar").

**Solución:** `ProactiveManager` detecta transiciones en el Flat Dict y encola eventos estratégicos para que el LLM genere consejos contextualizados.

**Los 18 triggers:**

| # | Trigger | Prio | Cooldown | Condición |
|---|---------|:----:|:--------:|-----------|
| 1 | `safety_car_deployed` | 5 | 30s | SC pasa de False a True |
| 2 | `safety_car_ended` | 5 | 30s | SC pasa de True a False |
| 3 | `fuel_critical` | 4 | 60s | `est_laps < 3` y `in_pits == False` |
| 4 | `pit_window_open` | 4 | 30s | Ventana de pits se abre |
| 5 | `pit_window_closing` | 4 | 15s | Ventana se cierra en <= 2 vueltas |
| 6 | `gap_closed_ahead` | 3 | 15s | `gap_ahead` pasa de >2s a <1s |
| 7 | `tyre_degraded` | 3 | 30s | Desgaste medio > 60% |
| 8 | `tyre_overheating` | 3 | 30s | `tyre_temp > 100` en alguna rueda |
| 9 | `rival_pitted` | 2 | 120s | Rival en pos +/-2 entra a pits |
| 10 | `rival_overtake` | 2 | 15s | Cambio de posición |
| 11 | `weather_rain` | 2 | 120s | Empieza a llover |
| 12 | `weather_drying` | 2 | 120s | Deja de llover y `wetness < 0.3` |
| 13 | `damage_detected` | 2 | 30s | `aero_damage > 0` transición |
| 14 | `battery_critical` | 3 | 30s | `battery < 20%` y no regenerando |
| 15 | `drs_available` | 2 | 10s | `drs_active` y `gap_ahead < 1.0` |
| 16 | `blue_flag` | 1 | 10s | Coche más rápido se acerca |
| 17 | `last_laps` | 1 | 0s | Últimas 3 vueltas |
| 18 | `gap_opened_behind` | 3 | 20s | `gap_behind > 3.0` transición |

**Implementación del ProactiveManager:**

```python
class ProactiveManager:
    """Detecta transiciones en Flat Dict y encola eventos para LLM proactivo.
    
    - Evaluado a 20Hz junto al spotter
    - Solo detecta CAMBIOS (no estados absolutos)
    - Cola de prioridad: SC > fuel > neumaticos > gaps > clima > posicion
    - Cooldown por trigger (evita spam)
    """
    
    TRIGGER_CONFIG = {
        "safety_car_deployed": {"priority": 5, "cooldown": 30},
        "safety_car_ended": {"priority": 5, "cooldown": 30},
        "fuel_critical": {"priority": 4, "cooldown": 60},
        "gap_closed_ahead": {"priority": 3, "cooldown": 15},
        "tyre_degraded": {"priority": 3, "cooldown": 30},
        "tyre_overheating": {"priority": 3, "cooldown": 30},
        "rival_pitted": {"priority": 2, "cooldown": 120},
        "rival_overtake": {"priority": 2, "cooldown": 15},
        "weather_rain": {"priority": 2, "cooldown": 120},
        "weather_drying": {"priority": 2, "cooldown": 120},
        "damage_detected": {"priority": 2, "cooldown": 30},
        "battery_critical": {"priority": 3, "cooldown": 30},
        "drs_available": {"priority": 2, "cooldown": 10},
        "blue_flag": {"priority": 1, "cooldown": 10},
        "last_laps": {"priority": 1, "cooldown": 0},
        "gap_opened_behind": {"priority": 3, "cooldown": 20},
    }
    
    def __init__(self, llm_pipeline=None, broadcast_callback=None):
        self._llm = llm_pipeline
        self._broadcast = broadcast_callback
        self._prev = {}  # Estado anterior (para transiciones)
        self._last_fired: dict[str, float] = {}  # cooldowns
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._current_task: asyncio.Task | None = None
    
    def evaluate(self, d: dict, now: float):
        """Evalua condiciones estrategicas. Llamar desde telemetry_sender_loop."""
        events = []
        
        # Safety Car (flanco de subida/bajada)
        sc = d.get("safety_car_active", False)
        if sc and not self._prev.get("safety_car"):
            events.append("safety_car_deployed")
        if not sc and self._prev.get("safety_car"):
            events.append("safety_car_ended")
        
        # Gap cerrado: transicion >2s a <1s
        ga = d.get("gap_ahead", 99)
        if ga < 1.0 and self._prev.get("gap_ahead", 99) > 2.0 and not d.get("in_pits"):
            events.append("gap_closed_ahead")
        
        # Gap abierto detras: transicion <2s a >3s
        gb = d.get("gap_behind", 99)
        if gb > 3.0 and self._prev.get("gap_behind", 99) < 2.0:
            events.append("gap_opened_behind")
        
        # Fuel critico
        if d.get("estimated_laps_remaining", 99) < 3 and not self._prev.get("_fuel_low") and not d.get("in_pits"):
            events.append("fuel_critical")
        
        # Rival en pits (cercano)
        rivals = d.get("rivals", [])
        for r in rivals:
            if r.get("in_pits") and abs(r.get("place", 99) - d.get("place", 1)) <= 2:
                events.append("rival_pitted")
                break
        
        # Cambio de posicion
        if d.get("place") != self._prev.get("place"):
            events.append("rival_overtake")
        
        # Lluvia
        rain = d.get("rain_intensity", 0)
        if rain > 0.05 and self._prev.get("rain_intensity", 0) < 0.01:
            events.append("weather_rain")
        if rain < 0.01 and self._prev.get("rain_intensity", 0) > 0.05 and d.get("wetness", 1) < 0.3:
            events.append("weather_drying")
        
        # Ultimas vueltas
        ll = d.get("session_laps_left", 99)
        if 0 < ll <= 3 and self._prev.get("session_laps_left", 99) > 3:
            events.append("last_laps")
        
        # DRS disponible
        if d.get("drs_active") and ga < 1.0 and not self._prev.get("_drs"):
            events.append("drs_available")
        
        # Actualizar estado previo
        self._prev.update({
            "safety_car": sc, "gap_ahead": ga, "gap_behind": gb,
            "_fuel_low": d.get("estimated_laps_remaining", 99) < 3,
            "rain_intensity": rain, "session_laps_left": ll,
            "place": d.get("place", 1), "_drs": d.get("drs_active", False),
        })
        
        for evt in events:
            cfg = self.TRIGGER_CONFIG.get(evt)
            if cfg and now - self._last_fired.get(evt, 0) >= cfg["cooldown"]:
                self._last_fired[evt] = now
                self._queue.put_nowait((-cfg["priority"], evt, d))
    
    async def process(self):
        """Procesa la cola (llamar desde telemetry_sender_loop)."""
        if self._current_task and not self._current_task.done():
            return
        if self._queue.empty():
            return
        _, name, d = await self._queue.get()
        self._current_task = asyncio.create_task(
            self._llm.ask_proactive(name, d)
        )

**Integración en telemetry_sender_loop:**

```python
async def telemetry_sender_loop(websocket, app_state):
    while True:
        d = reader.get_flat_dict()
        now = time.monotonic()
        
        # Spotter: alertas directas
        for alert in spotter.evaluate(d):
            spotter.try_broadcast(alert)
        
        # Proactivo: detectar condiciones estrategicas
        proactive.evaluate(d, now)
        
        # Procesar cola proactiva (no bloquea)
        asyncio.create_task(proactive.process())
        
        # Enviar al frontend
        raw = mp_encode(d)
        await websocket.send_bytes(raw)
        await asyncio.sleep(0.05)
```

---

### Task 6: LLMPipeline — prompt simple + perfiles

**Files:**
- Create: `backend/src/intelligence/llm_pipeline.py`
- Create: `backend/src/intelligence/profiles.py`
- Create: `backend/profiles/crewchief.json`
- Create: `backend/profiles/deportivo.json`

**Perfiles:**

```json
// backend/profiles/crewchief.json
{
  "name": "CrewChief Style",
  "system_prompt": "Eres el ingeniero de carrera del piloto.\n\nHabla en español, con tono de radio.\nMáximo 2 frases por respuesta.\nSolo respondes cuando el piloto te pregunte.\nUsa datos concretos: posiciones, tiempos, gaps.\nNo des opiniones, solo hechos.",
  "tts_voice": "es-ES-AlvaroNeural",
  "verbosity": "low"
}
```

```json
// backend/profiles/deportivo.json
{
  "name": "Ingeniero Deportivo",
  "system_prompt": "Eres ingeniero de carrera profesional.\n\nHabla en español.\nExplica estrategia con detalle.\nMaximo 4 frases.\nPuedes ser proactivo si hay cambios importantes.",
  "tts_voice": "es-ES-AlvaroNeural",
  "verbosity": "high"
}
```

**LLMPipeline:**

```python
class LLMPipeline:
    """Pipeline minimo para preguntas del piloto + modo proactivo.
    
    Reactivo: system + Flat Dict JSON + snapshots + eventos + pregunta (~2.5K tokens)
    Proactivo: system + Flat Dict JSON + trigger name + contexto momentaneo (~1.5K tokens)
    Sin RAG, sin ChromaDB, sin live context.
    """
    
    PROACTIVE_PROMPTS = {
        "safety_car_deployed": "Acaba de desplegarse el Safety Car. Los datos actuales estan arriba. Da consejo estrategico: entrar a boxes, esperar, o cubrir algun rival.",
        "safety_car_ended": "El Safety Car acaba de retirarse. La carrera se reanuda. Da instrucciones para la relanzada.",
        "fuel_critical": "Quedan menos de 3 vueltas de combustible. Los datos actuales estan arriba. Di si entrar a boxes o ahorrar.",
        "gap_closed_ahead": "El coche de delante esta a menos de 1 segundo. Da instrucciones tacticas para adelantar.",
        "gap_opened_behind": "Has abierto distancia con el coche de detras a mas de 3 segundos. Gestiona el ritmo.",
        "rival_pitted": "Un rival directo ha entrado a boxes. Analiza undercut/overcut.",
        "rival_overtake": "Acabas de cambiar de posicion. Da instrucciones para la nueva situacion.",
        "weather_rain": "Esta empezando a llover. Los datos del radar y temperatura estan arriba. Recomienda cuando entrar a cambiar neumaticos.",
        "weather_drying": "La pista se esta secando. Evalua cuando cambiar a slicks.",
        "tyre_degraded": "Los neumaticos tienen desgaste avanzado. Los datos de temperatura y presion estan arriba. Di si aguantar o entrar.",
        "tyre_overheating": "Los neumaticos estan sobrecalentados (mas de 100C). Recomienda como enfriarlos.",
        "damage_detected": "Se ha detectado dano en el monoplaza. Evalua la gravedad y si requiere parada.",
        "battery_critical": "La bateria hibrida esta por debajo del 20%. Recomienda modo de regeneracion.",
        "drs_available": "Tienes DRS disponible y estas a menos de 1 segundo del coche de delante. Da instrucciones de ataque.",
        "last_laps": "Es la ultima vuelta o quedan muy pocas. Da instrucciones de ataque o defensa segun la posicion.",
    }
    
    def __init__(self, profile_name="crewchief"):
        self._profile = load_profile(profile_name)
        self._llm_client = VLLMClient()
    
    def _build_base(self, flat_dict: dict, history: dict = None) -> str:
        """Construye la parte base del prompt: system + datos actuales + historico."""
        system = self._profile["system_prompt"]
        import json
        flat_json = json.dumps(flat_dict, indent=2, default=str)
        
        parts = [system, "\nDATOS ACTUALES DE TELEMETRIA (JSON):\n", flat_json]
        
        if history:
            snapshots = history.get("snapshots", [])
            events = history.get("events", [])
            if snapshots:
                parts.append("\n\nHISTORICO DE VUELTAS:\n")
                parts.append("\n".join(snapshots[-5:]))
            if events:
                parts.append("\n\nEVENTOS RECIENTES:\n")
                parts.append("\n".join(f"- {e['type']} (V{e['lap']})" for e in events[-10:]))
        
        return "".join(parts)
    
    async def ask(self, question: str, flat_dict: dict, history: dict = None) -> str:
        """Reactivo: responde pregunta del piloto."""
        base = self._build_base(flat_dict, history)
        prompt = f"""{base}

PREGUNTA DEL PILOTO:
{question}

RESPUESTA (max 3 frases, tono radio, datos concretos):"""
        
        full_text = ""
        async for token in self._llm_client.ask_streaming_text(prompt, tier="FAST"):
            full_text += token
        return full_text
    
    async def ask_proactive(self, trigger_name: str, flat_dict: dict) -> str:
        """Proactivo: genera consejo estrategico sin pregunta del piloto."""
        base = self._build_base(flat_dict)
        instruction = self.PROACTIVE_PROMPTS.get(trigger_name, f"Ha ocurrido: {trigger_name}. Da consejo breve.")
        
        prompt = f"""{base}

INSTRUCCION:
{instruction}

RESPUESTA (max 2 frases, tono radio, datos concretos del JSON anterior):"""
        
        full_text = ""
        async for token in self._llm_client.ask_streaming_text(prompt, tier="FAST"):
            full_text += token
        
        # Enviar como TTS
        from src.models.messages import AdviceEndMessage
        from src.transport.broadcaster import send
        msg = AdviceEndMessage(
            advice_id=str(uuid.uuid4()),
            full_text=full_text, actions=[], event="advice_end"
        )
        send(msg)
        return full_text
```

---

### Task 7: Integración en main.py + WebSocket

**Files:**
- Modify: `backend/src/main.py`
- Modify: `backend/src/routers/websocket.py`

**main.py — nuevo initialization:**

```python
# Lifespan
reader = LMUReader(offline=False)
reader.start()
app.state.lmu_reader = reader

spotter = SpotterService(broadcast_callback=broadcast_sync)
app.state.spotter = spotter

llm = LLMPipeline(profile_name="crewchief")
app.state.llm_pipeline = llm

history = RollingHistory()
app.state.history = history

fuel = FuelComputer()
app.state.fuel_computer = fuel

proactive = ProactiveManager(llm_pipeline=llm, broadcast_callback=broadcast_sync)
app.state.proactive_manager = proactive
```

**websocket.py — telemetry_sender_loop simplificado:**

```python
async def telemetry_sender_loop(websocket, app_state):
    reader = app_state.lmu_reader
    spotter = app_state.spotter
    history = app_state.history
    fuel = app_state.fuel_computer
    proactive = app_state.proactive_manager
    
    while True:
        d = reader.get_flat_dict()
        now = time.monotonic()
        
        # Computar combustible (media movil 5 vueltas)
        d.update(fuel.compute(d))
        
        # Actualizar rolling history (snapshots + eventos)
        history.update(d, now)
        
        # Spotter: alertas directas urgentes
        for alert in spotter.evaluate(d):
            spotter.try_broadcast(alert)
        
        # Proactive: detectar condiciones estrategicas
        proactive.evaluate(d, now)
        
        # Procesar cola proactiva (no bloquea, 1 tarea a la vez)
        asyncio.create_task(proactive.process())
        
        # Enviar flat dict al frontend (MessagePack + delta)
        raw = mp_encode(d)
        await websocket.send_bytes(raw)
        
        await asyncio.sleep(0.05)
```

---

### Task 8: Limpiar archivos obsoletos y tests

**Eliminar:**
- `shared-telemetry/`
- `shared-strategy/`
- `backend/src/services/strategy_service.py`
- `backend/src/intelligence/live_context.py`
- `backend/src/intelligence/context_builder.py`
- `backend/src/intelligence/prompt_templates.py`
- `backend/src/intelligence/ticker.py`
- `backend/src/persistence/`
- `backend/src/services/lmu_api.py`
- `backend/tests/test_strategy_service.py`
- `backend/tests/test_context_builder.py`
- `backend/tests/test_live_context.py`
- `backend/tests/test_prompt_templates.py`
- `backend/tests/test_event_store.py`
- `backend/tests/test_rag_integration.py`
- `backend/tests/test_lmu_api.py`

**Actualizar tests existentes:**
- `backend/tests/test_spotter.py` — apuntar a Flat Dict
- `backend/tests/test_ws_integration.py` — simplificar

---

### Resumen de Tasks (orden de implementacion)

| Task | Archivos | Depende de |
|:----:|----------|:----------:|
| 1 | `lmu_reader.py` | — |
| 2 | `fuel_computer.py` | Task 1 (gap_computer eliminado, LMU computa gaps) |
| 3 | `ticker_builder.py` | Task 1 |
| 4 | `rolling_history.py` | Task 1 |
| 5 | `spotter.py` (simplificar) | Task 1 |
| 5b | `proactive_manager.py` | Task 1 + 6 |
| 6 | `llm_pipeline.py`, `profiles.py` | Task 1 |
| 7 | `main.py`, `websocket.py` | Tasks 1-6 |
| 8 | Limpiar archivos obsoletos | Task 7 |
