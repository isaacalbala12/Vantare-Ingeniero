# LMU REST API — Especificación Completa

> Fuente: `backend/src/services/lmu_api.py`
> Endpoints HTTP de LMU, accesibles vía `http://localhost:6397` (puerto por defecto del juego).

## Visión General

El backend mantiene 3 caches asíncronos que se actualizan mediante polling a la REST API local de LMU. Todos los datos viajan como JSON.

```
lmu_api.poll_api()  (tarea asyncio background)
├── /rest/sessions/weather          cada 120s
├── /rest/strategy/usage            cada 3s
└── /rest/garage/UIScreen/RepairAndRefuel  cada 3s
```

---

## 1. `/rest/sessions/weather` — Clima

**Frecuencia:** Cada 120 segundos.
**Timeout:** 2 segundos.
**Cache:** `_weather_cache` (dict thread-safe).

### Estructura esperada del JSON:

```json
{
  "PRACTICE": {
    "START": { "WNV_SKY": 2, "WNV_TEMPERATURE": 22.5, "WNV_RAIN_CHANCE": 10, "WNV_HUMIDITY": 45, "WNV_WINDDIRECTION": 180, "WNV_WINDSPEED": 3.2 },
    "NODE_25": { ... },
    "NODE_50": { ... },
    "NODE_75": { ... },
    "FINISH": { ... }
  },
  "QUALIFY": { ... },
  "RACE": { ... }
}
```

### Campos por nodo climático:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| WNV_SKY | int | 0=clear, 1=light clouds, 2=partially cloudy, 3=mostly cloudy, 4=overcast |
| WNV_TEMPERATURE | float | Temperatura ambiente (°C) |
| WNV_RAIN_CHANCE | float | Probabilidad de lluvia (%) |
| WNV_HUMIDITY | float | Humedad (%) |
| WNV_WINDDIRECTION | float | Dirección del viento (grados) |
| WNV_WINDSPEED | float | Velocidad del viento |

### API pública:

```python
from src.services import lmu_api

weather = lmu_api.get_weather()
# → dict con PRACTICE/QUALIFY/RACE, cada uno con START/NODE_25/NODE_50/NODE_75/FINISH
```

### Uso en Fase 4 (ticker):

La línea WTH usa `mCloudCoverage`, `mRaining`, `mAmbientTemp`, `mTrackGripLevel` de shared memory (20Hz), no del cache de weather (120s). El cache de weather es para predicción futura (RAG y tiers DEEP).

---

## 2. `/rest/strategy/usage` — Uso de Energía Virtual

**Frecuencia:** Cada 3 segundos.
**Timeout:** 2 segundos.
**Cache:** `_strategy_usage_cache` (dict thread-safe).

### Estructura esperada del JSON:

```json
{
  "Isaac Albala": [
    { "ve": 1.0 },
    { "ve": 0.95 },
    { "ve": 0.92 }
  ],
  "Otro Piloto": [ ... ]
}
```

- Key: nombre del piloto (string)
- Value: lista de valores `ve` (virtual energy, fracción 0.0-1.0) por vuelta

### API pública:

```python
usage = lmu_api.get_strategy_usage()
# → dict[str, list[dict]]  — piloto → historial de VE
```

### Uso en ticker:

No se usa directamente en el ticker. Es información para el tier DEEP del prompt (estrategia híbrida a largo plazo).

---

## 3. `/rest/garage/UIScreen/RepairAndRefuel` — Desgastes de Garaje

**Frecuencia:** Cada 3 segundos.
**Timeout:** 2 segundos.
**Cache:** `_garage_wear_cache` (dict thread-safe).

**⚠️ FUENTE ÚNICA de brake wear.** La shared memory NO expone desgaste de pastillas de freno (solo temperatura y presión).

### Estructura esperada del JSON:

```json
{
  "wearables": {
    "body": {
      "aero": 0.05
    },
    "brakes": [0.92, 0.88, 0.85, 0.90],
    "suspension": [0.95, 0.93, 0.90, 0.92]
  }
}
```

| Campo | Tipo | Rango | Descripción |
|-------|------|-------|-------------|
| wearables.body.aero | float | 0.0-1.0 | Desgaste aerodinámico (0=nuevo, 1=total) |
| **wearables.brakes** | **float[4]** | **0.0-1.0** | **Desgaste frenos FL/FR/RL/RR (0=nuevo, 1=gastado)** |
| wearables.suspension | float[4] | 0.0-1.0 | Desgaste suspensión FL/FR/RL/RR |

### API pública:

```python
# Obtener cache completo
garage = lmu_api.get_garage_wear()
# → {"wearables": {"body": {"aero": 0.05}, "brakes": [...], "suspension": [...]}}

# Obtener solo frenos (formato simplificado)
brakes = lmu_api.get_additional_data("brakes")
# → {"wear": [0.92, 0.88, 0.85, 0.90]}

# Obtener solo daño aerodinámico
damage = lmu_api.get_additional_data("damage")
# → {"aero": 0.05}
```

### Uso en Fase 4 (ticker):

La línea BRK del ticker se construye desde `lmu_api.get_additional_data("brakes")`:
- Si el cache está vacío (primera llamada antes de 3s): **omitir línea BRK**
- Si hay datos: `BRK:{wear[0]*100:.0f}/{wear[1]*100:.0f}/{wear[2]*100:.0f}/{wear[3]*100:.0f}`
- El valor en REST API es 0.0-1.0, se multiplica por 100 para representar porcentaje (0=nuevo, 100=gastado)

### Conversión de escalas:

| Dato | Shared memory | REST API | Ticker |
|------|:-------------:|:--------:|:------:|
| Tyre wear | 0.0-1.0 (mWear) | — | 0-100% |
| Brake wear | ❌ no existe | 0.0-1.0 (brakes[]) | 0-100% |
| Brake temp | °C (mBrakeTemp - 273.15) | — | — |
| Aero damage | — | 0.0-1.0 (body.aero) | 0-100% |

---

## 4. Health Check (diagnóstico)

```python
cache_info = lmu_api.get_cache_sizes()
# → {
#     "weather": 3,
#     "strategy_usage": 6,
#     "garage_wear": 1,
#     "weather_age_s": 45.2,
#     "strategy_age_s": 1.8,
#     "garage_age_s": 2.1,
#     "drivers": 6,
#     "brakes": 1
#   }
```

---

## Notas de Implementación

### Thread safety
Todos los caches usan `threading.Lock` para acceso seguro desde múltiples corrutinas. El poller es `asyncio` puro y escribe bajo lock; las lecturas (`get_*`) también adquieren el lock.

### Fallos de red
Si un endpoint falla (timeout, conexión rechazada, status != 200), se loguea como `debug` y se mantiene el cache anterior. No hay degradación del servicio.

### Cache inicial
Al arrancar el backend, los caches están vacíos. El primer ciclo de polling ocurre inmediatamente (last_*_poll = 0.0), por lo que los datos llegan en ~3 segundos.
