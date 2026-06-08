# Crew Chief Port — Decisiones congeladas (Jun 2026)

Documento de **decisiones de producto y ejecución**. Complementa el plan maestro:
[`2026-06-07-crewchief-complete-port.md`](./2026-06-07-crewchief-complete-port.md).

---

## 1. Objetivo de lanzamiento (testers cerrados)

| Campo | Decisión |
|-------|----------|
| **Cuándo mostrar** | Solo tras big-bang cutover; testers cerrados |
| **Plazo** | **14 días máximo** |
| **Capacity** | ~10 h/día, 1 persona + varios agentes en paralelo |
| **Barra de éxito** | **Suena a Crew Chief** en carrera LMU (urgencias + core); alcance completo del plan es **objetivo optimista** |
| **PARTIAL aceptable** | Sí — penalty type, daño engine/tranny, stint countdown, latencia TTS → `cc-permanent-ceilings.md` |
| **Validación MATCH** | **CI primero** (unit + fixture); LMU smoke P0 manual (~30 min), no 48 filas una a una |

---

## 2. Producto / voz

| Tema | Decisión |
|------|----------|
| **Ingeniero proactivo** | Determinista (`crewchief_events` + plantillas). **Cero** batch LLM proactivo |
| **LLM** | Solo **PTT** del piloto, con **personality packs** |
| **Plantillas** | Radio breve estilo CC (1–2 frases, ≤120 chars urgencias) |
| **Personality packs día 1** | **`Neutral`** (producción) + **1 pack prueba** (incompleto) |
| **Pit menu voz (LMU-48)** | **NOT_PORTED** — sin REST write, sin “add X litres” / cambio neumáticos por voz |
| **Comandos pit** | Solo **lectura** (fuel status, ventana, “cuántas vueltas”) |
| **TTS** | **Edge TTS** (fijo todo el sprint) |
| **Commentary batch** | **Eliminar** del path ingeniero en big-bang; `commentary_end` solo si queda feature opt-in futura (fuera de scope 14 d) |
| **Hypercar / endurance** | **In scope** (Battery, VE context en fuel/strategy, DriverSwaps parcial, WatchedOpponents P1) |

---

## 3. Técnica

| Tema | Decisión |
|------|----------|
| **Task 0 telemetría** | **Más eficiente:** `telemetry_sender_loop` @ 20 Hz con frames nativos in-process — ver [**Task 49**](./2026-06-07-native-windows-no-sidecar.md). Sidecar legacy hasta 49-S9. |
| **Plataforma** | **Windows + LMU only** (Task 49). StepFun LLM en backend sin cambios. |
| **Cutover** | **Big-bang** día ~13–14: apagar emisores legacy; `test_crewchief_no_legacy_emitters` en CI |
| **Rama git** | **`crewchief-parity`** — solo trabajo parity 14 d |
| **LMU validation** | Sí — sesiones regulares; checklist smoke §6 |
| **Arranque app** | **Siempre Tauri** (build/desktop habitual) |
| **LMU + telemetría** | **Mismo PC Windows** — shared memory **in-process** (Task 49). Sidecar opcional hasta cutover 49-S9. |
| **Beeps / ambiance / rants** | NOT_PORTED o toggle off (LMU-39, 43–44 cosmetic) |

---

## 4. Normas operativas (obligatorias para agentes)

Estas normas sustituyen review de código por el piloto.

### 4.1 Entorno

| Norma | Detalle |
|-------|---------|
| **N1 — Tauri** | Probar y documentar siempre arranque desde **Tauri**, no backend suelto salvo debug agente |
| **N2 — Mismo PC** | LMU + Vantare en el **mismo Windows**; **no** levantar sidecar si `VANTARE_NATIVE_TELEMETRY=1` (Task 49) |
| **N3 — Rama** | Todo commit en **`crewchief-parity`** |
| **N4 — Pack voz** | Producción = **`Neutral`**; Edge TTS fijo |

### 4.2 Ciclo por task (después de cada Task N)

| Paso | Agente | Piloto |
|------|--------|--------|
| 1 | Implementar + tests L1–L3 ([plantilla pipeline](./2026-06-07-crewchief-pipeline-test-template.md)) | — |
| 2 | `pytest` / vitest / `verify_audio_pipeline.py` **verde** | — |
| 3 | Commit en `crewchief-parity` | — |
| 4 | Enviar **informe piloto** (plantilla §13 plantilla tests) | — |
| 5 | — | Solo si el informe pide validación LMU: probar en Tauri **sí/no** |
| 6 | Si “no suena bien”: corregir; **no** abrir Task N+1 en ese módulo | Describe qué esperabas oír |

**Prohibido:** marcar task done sin tests verdes. **Prohibido:** pedir al piloto que ejecute pytest o lea logs.

### 4.3 Comunicación

- Preguntas al piloto: **comportamiento**, no código.
- Entregables: *“Cuando pase X, dirá Y”*.
- Fallos LMU: nota en `.omo/evidence/` opcional; frase corta basta.

---

## 5. Anti-fork (día 14)

No mostrar a testers si sigue verdadero:

1. `ProactiveMonitorSuite` emite `event_id` ya portado en `modules/*`
2. Ingeniero proactivo pasa por `CommentaryOrchestrator` debounce
3. Parity events solo en `evaluate_cycle` @ 0.5 Hz (sin Task 0)
4. LLM formatea flags / gaps / posición / fuel proactivos

---

## 6. LMU smoke (30 min, pre-show)

| # | Escenario | Esperado |
|---|-----------|----------|
| 1 | Practice — silencio race-only | Sin position/push/gap proactivo |
| 2 | Race start + formation | Spotter mute formation; race_start once |
| 3 | FCY | Fases pits closed/open/green; ingeniero, no batch |
| 4 | Penalty | new → 2 → 1 → pit now (genérico) |
| 5 | Overtake / being overtaken | Un alert determinista cada uno |
| 6 | Rain level change | Alert inmediato sin forecast LLM |
| 7 | Spotter lateral + clear | 20 Hz, expiry en cola |
| 8 | PTT “¿cómo va el fuel?” | Respuesta LLM pack **Neutral**, no commentary batch |

Evidencia: notas en `.omo/evidence/cc-parity-validation-checklist.md`.

---

## 7. Decisiones técnicas cerradas

| # | Tema | Respuesta |
|---|------|-----------|
| Q1 | Pack producción día 1 | **`Neutral`** (+ 1 pack prueba incompleto) |
| Q2 | TTS | **Edge TTS** (fijo todo el sprint) |
| Q3 | Rama | **`crewchief-parity`** (14 d) |
| Q4 | Piloto sin código | Agentes implementan + verifican; tú juezas en LMU |

---

## 8. Ejecución sin conocimientos de código (piloto = producto + LMU)

**¿Cambia el plan técnico (Tasks 0–48, archivos, módulos CC)?** **No.** El mismo software hay que escribir.

**¿Cambia cómo se ejecuta?** **Sí.** Tú no revisas diffs ni pytest; agentes + CI son la red de seguridad. Tu rol es **decidir comportamiento** y **validar en LMU**.

### Tu rol (lo único que necesitas hacer bien)

| Rol | Qué haces | Cuándo |
|-----|-----------|--------|
| **Juez CC** | En pista: “¿suena como Crew Chief?” sí/no + nota breve | Días 7, 10, 13 |
| **LMU smoke** | Checklist §6 (30 min); no hace falta leer logs técnicos | Día 13–14 |
| **Decisor binario** | Aprobar preguntas tipo: “¿fuel crítico en spotter o ingeniero?” → una palabra | Cuando el agente pregunte |
| **Testers cerrados** | Coordinar 2–3 pilotos si quieres feedback extra | Día 14 |

### Rol de agentes (todo lo demás)

| Rol | Responsabilidad |
|-----|-----------------|
| Implementar | 1 task = 1 agente; TDD; sin “te lo explico, tú lo pegas” |
| Verificar | `pytest`, vitest, scripts — **nunca** “listo” sin output verde |
| Git | Rama `crewchief-parity`; commits por task; **tú no haces git** salvo que pidas |
| Cutover big-bang | Día 13; agente ejecuta, tú validas en juego |

### Gates automáticos (sustituyen review humana de código)

1. Tests verdes en cada task antes de la siguiente  
2. Día 4: `test_crewchief_tick_rate`  
3. Día 13: `test_crewchief_no_legacy_emitters`  
4. LMU smoke §6 (tú)  
5. Checklist §10 “suena a CC” (tú)

### Qué **no** debes hacer (y no pasa nada)

- Leer Python/TypeScript  
- Entender `triggerInternal` vs `evaluate_cycle`  
- Arreglar CI tú solo — pides al agente: “falló X, arréglalo”  
- Elegir entre subagent vs inline — **default: subagent por task**

### Comunicación contigo (regla para agentes)

- Preguntas **solo** de comportamiento o prioridad (“¿aceptamos PARTIAL en penalties?”), no de implementación  
- Entregables en lenguaje piloto: “Ahora el ingeniero dirá X cuando pase Y”  
- Si algo falla en LMU: grabación/nota (“no habló en FCY”) > stack trace  

### Riesgo extra y mitigación

| Riesgo | Mitigación |
|--------|------------|
| Código roto sin que lo veas | Tests + no avanzar task con rojo |
| “Suena a CC” pero bugs sutiles | Smoke LMU 3 veces (d7, d10, d13) |
| Repo sucio / conflictos | Solo rama `crewchief-parity` |
| Agentes duplican legacy + nuevo | Big-bang + test anti-legacy |

### Plan de 14 días **no** se multiplica por ser no-dev

Misma calendarización §9. Lo que sube es **exigencia de verificación automática**, no cantidad de tasks.

---

## 9. Sprint 14 días — orden y paralelismo

**~140 h humanas + agentes en paralelo.** Regla: **1 agente = 1 task**; agente demuestra tests verdes; **tú** validas comportamiento en LMU (d7/d10/d13), no código.

### Día 1–2 — Infra (bloqueante)

| Track | Tasks | Done cuando |
|-------|-------|-------------|
| A | **0**, **1**, **2** | tick 20 Hz + types + gates |
| B | **3**, **4** | suite runner + playback backend |
| C | **6** (FE expiry) | vitest priorityAudioQueue |

### Día 3–4 — Wire + templates

| Track | Tasks |
|-------|-------|
| A | **5** (engine wire, sin batch parity) |
| B | **7** (verbosity, speak-only) |
| C | **15** (templates ES + pack **Neutral** + pack prueba) |
| D | **16** (delayed queue — mínimo viable) |

### Día 5–7 — P0 race control (suena a CC)

| Track | Tasks |
|-------|-------|
| Paralelo | **17** flags, **18** penalties, **19** damage, **20** rain, **21** position |

### Día 8–10 — Core carrera

| Track | Tasks |
|-------|-------|
| Paralelo | **22** timings (sector MVP si falta mapa), **23–24** lap, **25** push, **26** session end |
| Paralelo | **27** fuel, **28** pit stops |

### Día 11–12 — Profundidad + spotter

| Track | Tasks | Nota |
|-------|-------|------|
| A | **29–34** tyres, engine, battery, multiclass, frozen | Priorizar 29, 33, 34 |
| B | **35–37** opponents, watched | P1 endurance |
| C | **42–43** spotter polish, FCY pause | LMU-01–05, 40 |
| D | **44** commands (sin pit write) | fuel/gap/spot/watch |

### Día 13 — Big-bang

| Orden | Task |
|-------|------|
| 1 | **48** cutover_registry + gut legacy emitters |
| 2 | `test_crewchief_no_legacy_emitters` + full pytest crewchief_* |
| 3 | Desactivar proactive commentary path en engine |
| 4 | LMU smoke §6 |

### Día 14 — Buffer + testers

| | |
|-|-|
| Fix regressions | LMU smoke |
| Matrix YAML | PARTIAL/MATCH solo con CI + nota smoke |
| Pack prueba | no bloqueante |

### Defer post-show (si el reloj aprieta)

Mantener en plan pero **después** del primer show si hace falta:

- **38–41** strategy/pearls/race_time/driver_swaps (pearls PTT-only OK)
- **32** overtaking aids
- **46–47** session delay/settings (nice)
- **13** fast commands extras más allá de PTT core
- Timings corner names completos (MVP gap sector/random primero)

---

## 10. Métrica “suena a CC” (día 14)

Checklist binario para testers cerrados:

- [ ] Urgencias hablan **<2 s** tras evento (no batch 3–8 s)
- [ ] FCY + penalty + rain + overtake = **mensajes separados**, texto fijo
- [ ] Spotter **no** compite con fuel/FCY en canal incorrecto (fuel → ingeniero)
- [ ] PTT responde con pack **Neutral**; **no** dispara commentary batch
- [ ] Tras big-bang, agente confirma `test_crewchief_no_legacy_emitters` verde (tú no lo ejecutas)

---

## 11. Enlaces

| Doc | Uso |
|-----|-----|
| [complete-port.md](./2026-06-07-crewchief-complete-port.md) | Tasks 0–48, archivos, emisores legacy §3.14 |
| [parity-port.md](./2026-06-07-crewchief-parity-port.md) | TDD Tasks 1–14 |
| [**pipeline-test-template.md**](./2026-06-07-crewchief-pipeline-test-template.md) | **Plantilla tests L1–L5 por eslabón pipeline** |
| `.omo/evidence/cc-behavior-parity-matrix.yaml` | Verdad conductual |
| `.omo/evidence/cc-permanent-ceilings.md` | Crear en Task 48 |
