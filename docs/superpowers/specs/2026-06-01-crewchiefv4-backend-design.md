# CrewChief V4 — Diseño de Implementación (Backend)

> **Estado:** Borrador inicial — en progreso durante brainstorming
> **Objetivo:** Documentar decisiones de diseño para la réplica de CrewChiefV4 en Vantare Ingeniero

---

## 1. ARQUITECTURA GENERAL

### 1.1 Dos cerebros coexistiendo

El sistema actual ya tiene un `IntelligenceEngine` que evalúa triggers con LLM a ~0.5Hz.
El nuevo sistema CrewChief añade un **segundo cerebro determinista** a 10Hz sin LLM.

Ambos:
- Leen la misma shared memory de LMU
- Envían mensajes al frontend por el mismo WebSocket (`broadcast_sync`)
- Son independientes: si uno falla, el otro sigue funcionando

### 1.2 Separación física

El nuevo bucle determinista vive en su propio archivo:
```
backend/src/crewchief_loop.py
```

`main.py` no se toca estructuralmente — solo se le añade:
```python
asyncio.create_task(crewchief_loop(reader, engine, ap))
```

---

## 2. SUb-PROYECTOS (orden de implementación)

| # | Sub-proyecto | Archivos nuevos | Depende de |
|---|-------------|-----------------|------------|
| 1 | Pipeline de datos | `lmu_reader.py`, `frame_cache.py`, `state_diff.py`, `delta_time.py`, `track_definition.py`, `car_class_data.py`, `game_state_builder.py`, `enums.py`, `game_state_data.py` | Nada |
| 2 | Audio system | `sound_cache.py`, `audio_player.py`, `number_reader.py`, `colloquial_time.py`, `utilities.py` | Pipeline (usa flat dict) |
| 3 | Spotter cartesiano | `noisy_cartesian_spotter.py` | Pipeline (necesita world_x/z de oponentes) |
| 4 | EventEngine + eventos base | `base_event.py`, `event_engine.py`, `event_flags.py`, `events/position.py`, `events/lap_counter.py`, `events/fuel.py`, `events/pit_stops.py` | Pipeline + Audio + Spotter |
| 5 | Eventos restantes | ~22 eventos más | Todo lo anterior |
| 6 | Integración frontend | Modificaciones en `useWebSocket.ts`, `appStore.ts`, `audioQueue.ts` | Todo lo anterior |

---

## 3. CONTRATO DE DATOS (FLAT DICT)

### 3.1 Formato

El contrato entre `lmu_reader.py`, `frame_cache.py` y el resto del sistema es un **diccionario plano** (dict).

Razones:
- Los eventos y el spotter necesitan acceso rápido a campos individuales
- El plan existente ya usa este formato
- Se puede serializar a JSON/MessagePack sin transformación

Ejemplo de estructura:
```python
{
    # Sesión
    "session_type": 3,           # 0=Unavail, 1=Practice, 2=Qual, 3=Race
    "session_phase": 5,          # 0=Unavail...5=Green...8=Finished
    "session_running_time": 1234.5,  # mCurrentET (CRITICAL para cooldowns)
    
    # Jugador
    "world_x": 1234.5,
    "world_y": 0.0,
    "world_z": 5678.9,
    "rotation_yaw": 1.23,       # Radianes (NaN-safe)
    "rotation_pitch": 0.01,
    "rotation_roll": 0.005,
    "speed_ms": 50.2,
    "gear": 5,
    "engine_rpm": 8500.0,
    "lap_number": 12,
    "lap_distance": 2345.6,
    "place": 3,
    "in_pits": False,
    "fuel_left": 45.2,
    "fuel_capacity": 100.0,
    "virtual_energy": 0.85,      # LMU Hypercars (mVirtualEnergy)
    "state_of_charge": 85.0,     # Batería en porcentaje
    "battery_percentage": 85.0,  # Normalizado (puede venir de REST API)
    
    # Neumáticos
    "tyre_temp_fl": 87.3, "tyre_temp_fr": 88.1,
    "tyre_temp_rl": 82.5, "tyre_temp_rr": 83.0,
    "tyre_wear_fl": 0.15, "tyre_wear_fr": 0.12,
    "tyre_wear_rl": 0.20, "tyre_wear_rr": 0.18,
    "brake_temp_fl": 350.0, "brake_temp_fr": 360.0,
    "brake_temp_rl": 310.0, "brake_temp_rr": 320.0,
    "tyre_pressure_fl": 180.0,  # kPa
    
    # Opciones
    "accel_long": 0.5, "accel_lat": -1.2, "accel_vert": 0.1,
    "water_temp": 95.0, "oil_temp": 110.0,
    "oil_pressure": 4.5,
    
    # Rivales (array de diccionarios)
    "rivals": [
        {
            "driver_raw_name": "Hamilton",
            "car_number": "44",
            "place": 1,
            "class_place": 1,
            "speed": 51.0,
            "world_x": 1300.0,
            "world_z": 5700.0,
            "distance_round_track": 2400.0,
            "laps_completed": 12,
            "last_lap_time": 92.5,
            "best_lap_time": 91.2,
            "current_sector": 2,
            "in_pits": False,
            "vehicle_class": "HYPER_CAR",
            "tyre_compound": "Soft",
            "gap_to_player": 3.5,
            "is_active": True
        },
        # ... más rivales
    ],
    
    # Datos de REST API (fusionados)
    "damage_aero": 0.1,
    "damage_suspension_fl": 0.0,
    "ambient_temp": 25.0,
    "track_temp": 35.0,
    "rain_intensity": 0.0,
    "cloud_coverage": 0.2,
}
```

### 3.2 Conversión opcional a objetos

Los eventos pueden convertir el flat dict a `GameStateData` (dataclasses) si necesitan:
- Validación de tipos
- Autocompletado en IDE
- Métodos auxiliares (ej: `speed_kmh`, `get_opponent_key_behind()`)

La conversión se hace en `game_state_builder.py`. No es obligatoria — un evento puede trabajar directamente con el dict si es más rápido.

---

## 4. LECTOR DE SHARED MEMORY

### 4.1 `lmu_reader.py` (nuevo)

- Reusa `MMapControl` de `shared_telemetry/pyLMUSharedMemory/lmu_mmap.py` para crear el mmap
- Reusa los structs ctypes de `shared_telemetry/pyLMUSharedMemory/lmu_data.py` (no redefinir)
- Añade `LMUOrientation` como wrapper local para el cálculo de rotación
- Devuelve flat dict directamente — sin pasar por modelos Pydantic
- Extrae campos de oponentes que el `TelemetryReader` actual no expone:
  - `orientation` (matriz 3x3) para yaw/pitch/roll
  - `world_x`, `world_z` de telemetría de cada vehículo
  - Compuesto de neumáticos
  - Energía virtual (Hypercars)
- Manejo NaN/Inf: devuelve 0.0 en rotaciones corruptas
- Manejo de leading null byte en nombres (bug conocido de LMU)

### 4.2 `frame_cache.py` (nuevo)

- Centraliza la lectura: llama a `lmu_reader.get_flat_dict()` UNA vez por tick
- Fusiona datos de REST API (`lmu_api.py`) en el mismo dict
- Deduplica frames: si `mCurrentET` no cambió, devuelve el mismo frame anterior
- Pre-extrae datos para el spotter (lista de rivales con posición)
- Sirve el mismo flat dict tanto al spotter como al EventEngine

### 4.3 `TelemetryReader` existente

NO se modifica. Sigue siendo usado por el `IntelligenceEngine` para triggers LLM.
Ambos lectores coexisten — leen la misma shared memory de forma independiente.

---

## 5. PRÓXIMAS DECISIONES (pendientes)

- [ ] **StateDiff:** ¿detección de cambios entre ticks? (leader change, new lap, retirements)
- [ ] **GameStateBuilder:** ¿aplanar el dict a dataclasses o mantenerlo como dict?
- [ ] **TrackDefinition:** ¿hardcodear circuitos conocidos o detectar automáticamente?
- [ ] **CarClassData:** ¿umbrales por defecto o configurables por usuario?
- [ ] **Audio system:** ¿usar Edge TTS existente o solo WAV pregrabados?
- [ ] **EventEngine:** ¿timeout por evento o timeout global?

---

## 6. BITÁCORA DE DECISIONES

| Fecha | Decisión | Opción elegida |
|-------|----------|----------------|
| 2026-06-01 | Descomposición del proyecto | Híbrida (Opción C): Pipeline → Audio → Spotter → Eventos base → Eventos restantes → Frontend |
| 2026-06-01 | Ubicación del loop determinista | Archivo propio: `crewchief_loop.py` (separado de `main.py`) |
| 2026-06-01 | Contrato de datos | Flat dict para lectura cruda, con conversión opcional a objetos (Opción C) |
| 2026-06-01 | Lector de shared memory | Nuevo `lmu_reader.py` (lectura directa, no wrapper de TelemetryReader) |
| 2026-06-01 | Reutilización de `shared_telemetry` | Reusar `MMapControl` y structs ctypes — no redefinir. No modificar `TelemetryReader` |
