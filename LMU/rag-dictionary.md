# RAG Dictionary — Ticker y Embeddings

> Diccionario de referencia para el formato de comunicación entre la telemetría de LMU y el LLM.
> Usado en: system prompt del LLM, generación de ticker, formato de embeddings para ChromaDB.

---

## 1. Ticker — Formato Compacto para LLM

El ticker es el formato de entrada principal para el LLM. Reemplaza el JSON verboso de telemetría por un texto compacto de ~400 tokens.

### Línea 1: DRV — Datos del piloto

```
DRV:P{pos}|L{vuelta}|F:{fuel}L/{consumo}({laps_rest})|TYR:{wFL}/{wFR}/{wRL}/{wRR}·{tFL}/{tFR}/{tRL}/{tRR}
```

| Código | Significado | Fuente LMU | Rango | Ejemplo |
|--------|-------------|:----------:|:-----:|:-------:|
| P{pos} | Posición en pista | `LMUVehicleScoring.mPlace` | 1-104 (1-based) | `P3` |
| L{vuelta} | Vuelta actual | `LMUVehicleTelemetry.mLapNumber` | 1-N | `L26` |
| F:{fuel}L | Combustible en tanque (litros) | `LMUVehicleTelemetry.mFuel` | 0-capacidad | `F:42.3L` |
| {consumo} | Consumo promedio (L/vuelta) | StrategyService (fuel_rate_trend) | 0.0-10.0 | `3.2` |
| ({laps_rest}) | Vueltas restantes estimadas | StrategyService (estimated_laps_remaining) | 0-N | `(13L)` |
| TYR:{w}/... | Desgaste neumáticos (0-100%) | `LMUWheel.mWear * 100` | 0-100 | `72/68/65/63` |
| ·{t}/... | Temperatura neumáticos (°C) | `LMUWheel.mTemperature - 273.15` | 0-130 | `·92/94/98/96` |

**Regla especial:** Si `lap ≤ 3`, se omite la sección `TYR:` completa (desgaste no representativo).

### Línea 2: BRK — Desgaste de frenos

```
BRK:{wFL}/{wFR}/{wRL}/{wRR}
```

| Código | Significado | Fuente LMU | Rango | Ejemplo |
|--------|-------------|:----------:|:-----:|:-------:|
| {wFL} | Desgaste freno delantero izquierdo | `REST API /rest/garage/UIScreen/RepairAndRefuel → wearables.brakes[0] * 100` | 0-100 | `38` |

**⚠️ Importante:** La shared memory NO expone brake wear. Solo la REST API (cada 3s) proporciona estos datos. Si el cache REST está vacío, la línea BRK se omite completamente.

### Línea 3: GAP — Diferencias con rivales

```
GAP>{ahead_name}:+{ahead_sec}·{ahead_best}|<{behind_name}:{behind_sec}·{behind_best}·d{delta}
```

| Código | Significado | Fuente LMU | Rango | Ejemplo |
|--------|-------------|:----------:|:-----:|:-------:|
| {ahead_name} | Nombre piloto adelante (abrev. 3 chars) | `LMUVehicleScoring.mDriverName` | — | `VST` |
| +{ahead_sec} | Gap con el de adelante (segundos) | `LMUVehicleTelemetry.mTimeGapPlaceAhead` | 0.0-N | `+2.1` |
| {ahead_best} | Mejor tiempo de vuelta del de adelante | `LMUVehicleScoring.mBestLapTime` | segundos | `1:48.2` |
| {behind_name} | Nombre piloto detrás (abrev. 3 chars) | `LMUVehicleScoring.mDriverName` | — | `ALO` |
| -{behind_sec} | Gap con el de detrás (segundos) | `LMUVehicleTelemetry.mTimeGapPlaceBehind` | 0.0-N | `-1.2` |
| {behind_best} | Mejor tiempo del de detrás | `LMUVehicleScoring.mBestLapTime` | segundos | `1:47.9` |
| d{delta} | Diferencia de ritmo (tu best - su best) | Calculado | -99.0-99.0 | `d-0.3` |

**Omisión:** Si no hay rival adelante (líder), se omite la sección `>`.
**Omisión:** Si no hay rival detrás (último), se omite la sección `<`.

### Línea 4: SES — Información de sesión

```
SES:{clase}|{tipo}|{total}L|{tiempo_restante}
```

| Código | Significado | Fuente LMU | Rango | Ejemplo |
|--------|-------------|:----------:|:-----:|:-------:|
| {clase} | Clase del vehículo (abrev.) | `LMUVehicleScoring.mVehicleClass` | HY, GT3, LMP2, etc. | `HY` |
| {tipo} | Tipo de sesión (abrev.) | `LMUScoringInfo.mSession` | RACE, QUALI, PRACTICE | `RACE` |
| {total}L | Vueltas totales de carrera | `LMUScoringInfo.mMaxLaps` | 0-N (0=por tiempo) | `38L` |
| {tiempo_restante} | Tiempo restante formateado | `LMUScoringInfo.mSessionTimeRemaining` | MM:SS o H:MM:SS | `45:22` |

**Abreviaturas de clase:**
- `HY` → Hypercar / LMH / LMDh
- `LMP2` → LMP2
- `LMP3` → LMP3
- `GT3` → GT3
- `GTE` → GTE

**Abreviaturas de sesión:**
| Código | mSession |
|:------:|:--------:|
| TEST | 0 |
| PRA1-4 | 1-4 |
| Q1-4 | 5-8 |
| WUP | 9 |
| RACE | 10-13 |

### Línea 5: WTH — Clima y condiciones

```
WTH:{grip}|{temp}°|{rain}%+{min}|SC:{S/N}
```

| Código | Significado | Fuente LMU | Rango | Ejemplo |
|--------|-------------|:----------:|:-----:|:-------:|
| {grip} | Nivel de agarre pista | `LMUScoringInfo.mTrackGripLevel` | GRN/LOW/MED/HIG/SAT | `MED` |
| {temp}° | Temperatura ambiente | `LMUScoringInfo.mAmbientTemp` | 0-50 °C | `22°` |
| {rain}% | Probabilidad de lluvia | `Weather REST API → WNV_RAIN_CHANCE` | 0-100% | `30%` |
| +{min} | Minutos hasta lluvia | Weather REST API (estimado) | 0-120 | `+15m` |
| SC:{S/N} | Safety Car activo | `LMUScoringInfo.mGamePhase == 6` | S/N | `SC:N` |

**Agarres de pista:**
| Código | mTrackGripLevel | Descripción |
|:------:|:---------------:|-------------|
| GRN | 0 | Green (nuevo) |
| LOW | 1 | Low |
| MED | 2 | Medium |
| HIG | 3 | High |
| SAT | 4 | Saturated |

**Omisión:** Si el cache de weather REST no tiene datos de lluvia, se omite `{rain}%+{min}`.

### Línea 6: RIV — Rivales

```
RIV:{total} cars
CLS1({n}):{detalle}·{detalle}·...
CLS2({n}):{detalle}·{detalle}·...
FAR({n}):{gap_del_mas_lejano}s·{clase}:{n}...
LAP({n}):{detalle}·...
```

| Código | Significado | Fuente LMU | Ejemplo |
|--------|-------------|:----------:|:-------:|
| {total} | Total de coches en pista | `LMUScoringInfo.mNumVehicles` | `85 cars` |
| CLS1 | Rivales con gap < 5s | Scoring + Telemetry combinado | `CLS1(3):VST|HY|+2.1|V22·ALO|HY|-1.2|V22` |
| CLS2 | Rivales con gap 5-30s | Scoring + Telemetry combinado | `CLS2(5):BOR|GT3|+12.3|V21` |
| FAR | Rivales con gap > 30s | Scoring | `FAR(25):+31s behind` |
| LAP | Rivales doblados (≥1 vuelta) | Scoring | `LAP(2):VAN(-1L)` |

**Formato de detalle por rival:**

| Zona | Formato | Ejemplo | Coste |
|:----:|---------|---------|:-----:|
| CLS1 | `{name}\|{class}\|{gap}\|V{laps}` | `VST|HY|+2.1|V22` | ~18 chars |
| CLS2 | `{name}\|{class}\|{gap}\|V{laps}` | `BOR|GT3|+12.3|V21` | ~18 chars |
| FAR | `{gap_del_mas_lejano}s behind` | `+31s behind` | fijo |
| LAP | `{name}(-{n}L)` | `VAN(-1L)` | ~10 chars |

**Límite:** Si hay >40 rivales en CLS1+CLS2 combinados, se muestran solo los 20 más cercanos por gap absoluto + rivales en ventana de pits (gap < 15s y pit_window_open).

---

## 2. Embeddings — Formato para ChromaDB (RAG)

El formato de embeddings se usa para indexar eventos históricos en ChromaDB y para consultar eventos similares. Es diferente del ticker del LLM: está optimizado para similitud semántica, no para legibilidad.

> Implementado en: `backend/src/intelligence/formatter.py` → `format_event_text()`

### Formato

```
L{vuelta}|P{pos}|F{combustible}|T{wFL}/{wFR}/{wRL}/{wRR}|SC{S/N}|YF{S/N}|G{+ahead/-behind}|S{velocidad}|CLD{0-10}|RAIN{0.0-1.0}|WET{0.0-1.0}|A{°C}|TEMP{°C}|DRS{S/N}|PIT{0-4}|BAT{%}|D{%}|E{tipo_evento}
```

### Tabla de prefijos

| Prefijo | Campo LMU | Rango | Ejemplo | Notas |
|---------|-----------|:-----:|---------|-------|
| **L** | `mLapNumber` | 1-N | `L26` | Vuelta actual |
| **P** | `mPlace` | 1-based | `P3` | Posición |
| **F** | `mFuel` | 0.0-100.0 | `F42.3` | Combustible en litros (1 decimal) |
| **T** | `mWheels[i].mWear * 100` | 0-100 | `T72/68/65/63` | Desgaste FL/FR/RL/RR (%). **Omitir si lap ≤ 3** |
| **SC** | `mGamePhase == 6` | S/N | `SCS` | Safety Car activo |
| **YF** | `mSectorFlag` + `mYellowFlagState` | S/N | `YFS` | Bandera amarilla activa |
| **G** | `mTimeGapPlaceAhead/Behind` | -99.9-99.9 | `G+2.1` o `G-1.2` | Gap con siguiente/anterior. Signo + = por delante |
| **S** | `mLocalVel` (magnitud) | 0-350 | `S180` | Velocidad en m/s (entero) |
| **CLD** | `mCloudCoverage` | 0-10 | `CLD4` | Cobertura nubes |
| **RAIN** | `mRaining` | 0.0-1.0 | `RAIN0.3` | Lluvia |
| **WET** | `mAvgPathWetness` | 0.0-1.0 | `WET0.4` | Mojado pista |
| **A** | `mAmbientTemp` | 0-50 | `A22` | Temperatura ambiente °C |
| **TEMP** | `mTrackTemp` | 0-70 | `TEMP30` | Temperatura pista °C |
| **DRS** | `mDRSState` / `mRearFlapActivated` | S/N | `DRSS` o `DRSN` | DRS activo |
| **PIT** | `mPitState` | 0-4 | `PIT0` | 0=none, 1=request, 2=entering, 3=stopped, 4=exiting |
| **BAT** | `mStateOfCharge` | 0-100 | `BAT85` | Batería híbrida % |
| **D** | `mDentSeverity` (promedio 8 ubicaciones, 0-2) | 0-100 | `D12` | Daños acumulados % (proxy: promedio * 50) |
| **E** | Tipo de evento | — | `Egap_change` | Tipo de evento que disparó este embedding |

### Tipos de evento (E)

| Código | Descripción |
|--------|-------------|
| `lap_completed` | Vuelta completada |
| `pit_entry` | Entrada a boxes |
| `pit_exit` | Salida de boxes |
| `safety_car` | Safety Car desplegado |
| `yellow_flag` | Bandera amarilla |
| `position_change` | Cambio de posición |
| `gap_change` | Cambio de gap significativo (>1s) |
| `weather_change` | Cambio climático |
| `fuel_critical` | Combustible crítico (<30L) |
| `tyre_critical` | Desgaste neumáticos crítico (>80%) |
| `hybrid_change` | Cambio de modo híbrido |

### Ejemplos

**Safety Car, V26, P3, lluvia ligera:**
```
L26|P3|F42.3|T72/68/65/63|SCS|YFS|G+2.1|S180|CLD6|RAIN0.3|WET0.4|A22|TEMP30|DRSN|PIT0|BAT85|D12|Esafety_car
```

**Vuelta 3 (sin neumáticos, regla especial):**
```
L3|P5|F91.2|SCN|YFN|G-1.2|S175|CLD2|RAIN0.0|WET0.0|A20|TEMP32|DRSS|PIT0|BAT90|D2|Egap_change
```

---

## 3. Mapeo Completo: Shared Memory → Ticker → Embedding

| Concepto | Shared Memory (raw) | Pydantic Model | Ticker | Embedding |
|----------|:-------------------:|:--------------:|:------:|:---------:|
| Posición | `mPlace` | `standing_position` | `DRV.P` | `P` |
| Vuelta | `mLapNumber` | `lap_number` | `DRV.L` | `L` |
| Combustible | `mFuel` | `fuel_in_tank` | `DRV.F` | `F` |
| Consumo | — (calculado) | `fuel_rate_trend` | tasa en F | — |
| Desgaste neum. | `mWear * 100` | `tyre_wear_*` | `DRV.TYR` | `T` |
| Temp. neum. | `mTemperature - 273.15` | `tyre_temp_*` | `DRV.TYR` (·) | — |
| Desgaste frenos | ❌ REST API | `brake_wear_*` | `BRK` | — |
| Gap adelante | `mTimeGapPlaceAhead` | `time_gap_place_ahead` | `GAP>` | `G+` |
| Gap detrás | `mTimeGapPlaceBehind` | `time_gap_place_behind` | `GAP<` | `G-` |
| Tipo sesión | `mSession` | `session_type` | `SES` | — |
| Tiempo restante | `mSessionTimeRemaining` | `session_time_left` | `SES` | — |
| Velocidad | `mLocalVel` (magnitud) | `speed` | — | `S` |
| Temperatura amb. | `mAmbientTemp` | `ambient_temp` | `WTH` | `A` |
| Temperatura pista | `mTrackTemp` | `track_temp` | — | `TEMP` |
| Lluvia | `mRaining` | `raining` | — | `RAIN` |
| Mojado | `mAvgPathWetness` | `avg_path_wetness` | — | `WET` |
| Nubes | `mCloudCoverage` | `cloud_coverage` | — | `CLD` |
| Agarrepista | `mTrackGripLevel` | `track_grip_level` | `WTH` | — |
| SC activo | `mGamePhase == 6` | `safety_car_active` | `WTH.SC` | `SC` |
| DRS | `mRearFlapActivated` | `drs_state` | — | `DRS` |
| Estado pits | `mPitState` | `pit_state` | — | `PIT` |
| Batería | `mStateOfCharge` | `battery_charge` | — | `BAT` |
| Daños | `mDentSeverity` (promedio) | — | — | `D` |
| Tipo evento | — (detectado) | — | — | `E` |
| Rival | `mDriverName`, `mPlace`, etc. | `competitors[]` | `RIV` | — |

---

## 4. Reglas de Prompt Builder

### Para construcción del prompt del LLM:

```python
def build_prompt(ticker_data, trigger_reason, pilot_question, templates, event_store):
    # 1. Generar ticker
    ticker_text = generate_ticker(ticker_data)  # ~400 tokens
    
    # 2. RAG opcional
    rag_text = query_event_store(ticker_data) if event_store else None  # ~100 tokens
    
    # 3. Construir prompt
    prompt = f"""
    {SYSTEM_PROMPT_TICKER}
    
    ### TELEMETRÍA ###
    {ticker_text}
    
    ### CONTEXTO HISTÓRICO ###
    {rag_text or ""}
    
    ### PREGUNTA ###
    {pilot_question or trigger_reason}
    """
    
    # 4. Validar tamaño (seguridad, no bloqueo)
    token_count = tiktoken.count(prompt)
    if token_count > 3000:
        # Degradar tier: eliminar RIV lejanos y RAG
        prompt = degrade_prompt(prompt)
    
    return prompt
```

### Límites de tokens:

| Componente | Tokens estimados |
|-----------|:----------------:|
| System prompt | ~200 |
| DRV + BRK + GAP | ~80 |
| SES + WTH | ~40 |
| RIV (85 rivales) | ~280 |
| RAG (top-5 eventos) | ~100 |
| Trigger/pregunta | ~30 |
| **Total** | **~730** |

### Regla de degradación por exceso de tokens:

| Si supera | Acción |
|:---------:|--------|
| > 1000 tokens | Eliminar RAG |
| > 1500 tokens | Eliminar FAR y LAP de RIV, mantener solo CLS1+CLS2 |
| > 2000 tokens | Eliminar RIV completo, mantener solo DRV+BRK+GAP+SES+WTH |
| > 3000 tokens | Degradar a FAST tier (solo DRV básico sin detalles) |

---

## 5. Ejemplo de Prompt Completo

```
Eres un ingeniero de carrera. Recibes datos en formato ticker compacto.

FORMATO TICKER:
DRV:P{pos}|L{vuelta}|F:{fuel}L/{consumo}({laps_rest})|TYR:{desgaste}·{temperatura}
BRK:{desgaste_frenos}
GAP>{rival}+{gap}<{rival}-{gap}
SES:{clase}|{tipo}|{total}L|{tiempo}
WTH:{grip}|{temp}°|{rain}%+{min}|SC:{S/N}
RIV:{total} cars|CLS1:{detalle}·...|CLS2:{detalle}·...|FAR:{n}|LAP:{n}

Máximo 2-3 frases. Estilo radio. Técnico y conciso.

### TELEMETRÍA ###
DRV:P3|L26|F:42.3L/3.2(13L)|TYR:72/68/65/63·92/94/98/96
BRK:38/35/22/20
GAP>VST:+2.1·1:48.2|<ALO:-1.2·1:47.9·d-0.3
SES:HY|RACE|38L|45:22
WTH:MED|22°|30%+15m|SC:N
RIV:85 cars
CLS1(3):VST|HY|+2.1|V22·ALO|HY|-1.2|V22·LEC|HY|-5.4|V22
CLS2(5):BOR|GT3|+12.3|V21·AND|GT3|+14.1|V20·VAN|GT3|+18.7|V22·SET|GT3|+22.1|V21·MOL|GT3|+25.3|V20
FAR(72):+31s behind
LAP(0):—

### CONTEXTO HISTÓRICO ###
- V10: Safety Car desplegado (P5, Comb.58.1L)
- V15: Entrada a boxes (P4, Comb.22.3L)
- V18: Cambio de posición ganado a ALO (P3)

### PREGUNTA ###
¿Cuándo debería parar?
```
