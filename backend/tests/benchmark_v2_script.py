#!/usr/bin/env python3
"""
Vantare Benchmark v2 - Strategic Engineer Evaluation

Structure: 80 questions across 6 tiers
- Tier 1-5: Quick questions with increasing pressure
- Tier 6: Full RAG context with 20-lap history

Each question is asked in natural Spanish.
Ground truth is determined by human + LLM judge evaluation.
"""

# =============================================================================
# BENCHMARK QUESTIONS - 80 total
# Format: (tier, level, question)
# =============================================================================

QUESTIONS = [
    # =========================================================================
    # TIER 1 - Estado simple del coche (basado en telemetria directa)
    # =========================================================================
    # T1a - 1 concepto, directo
    ("tier1", "a", "¿Cuanta gasolina me queda?"),
    ("tier1", "a", "¿Que marcha llevo?"),
    ("tier1", "a", "¿Van bien los frenos?"),
    ("tier1", "a", "¿Temperatura del motor esta bien?"),
    # T1b - Pregunta trampa (alucinacion)
    ("tier1", "b", "¿Tengo DRS disponible?"),
    ("tier1", "b", "¿ERS activo?"),
    ("tier1", "b", "¿KERS tengo?"),
    # T1c - 2 conceptos combinados
    ("tier1", "c", "¿Fuel y bateria como van?"),
    ("tier1", "c", "¿Motor y frenos OK?"),
    ("tier1", "c", "¿Temperatura motor y aceite?"),
    # T1d - 3 conceptos, presion piloto
    ("tier1", "d", "¡Dame rapido! Motor, fuel, RPMs."),
    ("tier1", "d", "¡Ya! Neumaticos, motor, bateria. Responde."),
    ("tier1", "d", "¿Todo bien o no? Frenos, motor, suspension."),
    # T1e - Maxima presion
    ("tier1", "e", "¡URGENTE! ¿Llego o no? Fuel, consumo, revoluciones."),
    ("tier1", "e", "¡EMERGENCY! ¿Puedo terminar o no?"),

    # =========================================================================
    # TIER 2 - Ingenieria (interpretar valores tecnicos)
    # =========================================================================
    # T2a - 1 concepto tecnico
    ("tier2", "a", "¿Las revoluciones del motor estan en rango?"),
    ("tier2", "a", "¿Presion del aceite correcta?"),
    ("tier2", "a", "¿Temperatura del agua OK?"),
    ("tier2", "a", "¿Suspension normal?"),
    # T2b - Pregunta trampa tecnica
    ("tier2", "b", "¿DRS activado?"),
    ("tier2", "b", "¿ABS funcionando?"),
    ("tier2", "b", "¿Control de traccion activo?"),
    # T2c - 2 conceptos tecnicos
    ("tier2", "c", "Temperatura motor y aceite. ¿Estan bien?"),
    ("tier2", "c", "Presion hidraulica y RPM. ¿Todo OK?"),
    ("tier2", "c", "Ride height y deflection. ¿Como vamos?"),
    # T2d - 3 conceptos + presion
    ("tier2", "d", "¡YA! Agua motor, aceite, RPMs."),
    ("tier2", "d", "Suspension, frenos, motor. ¿Todo bien?"),
    ("tier2", "d", "¡DAME rapido! Temperaturas y presiones."),
    # T2e - Maxima presion tecnica
    ("tier2", "e", "¡ALARMA! Motor sobrecalentando. ¿Que hago?"),
    ("tier2", "e", "¡CRITICO! Aceite y agua en rojo."),

    # =========================================================================
    # TIER 3 - Tendencias (analisis historico)
    # =========================================================================
    # T3a - 1 concepto con tendencia
    ("tier3", "a", "¿Subio la temperatura del motor en las ultimas vueltas?"),
    ("tier3", "a", "¿Bajo la presion de los neumaticos?"),
    ("tier3", "a", "¿Aumento el consumo de gasolina?"),
    ("tier3", "a", "¿RPM estable o subiendo?"),
    # T3b - Tendencia + trampa
    ("tier3", "b", "¿DRS como va funcionando esta carrera?"),
    ("tier3", "b", "¿ERS generando bien?"),
    ("tier3", "b", "¿KERS recuperacion funcionando?"),
    # T3c - 2 conceptos con tendencia
    ("tier3", "c", "Fuel consumption y battery. ¿Mejorando o piorando?"),
    ("tier3", "c", "Temperatura motor y frenos. ¿Estables?"),
    ("tier3", "c", "Presion aceite y agua. ¿Tendencia?"),
    # T3d - 3 conceptos + presion piloto
    ("tier3", "d", "Historico! Consumo, temps motor, battery. Como vamos."),
    ("tier3", "d", "Ultimas 5 vueltas: RPM, oil presion, water temp."),
    ("tier3", "d", "¡EVOLUCION! Todo el trenmotriz."),
    # T3e - Maxima presion con analisis
    ("tier3", "e", "¡RAPIDO! Tendencia de consumo ultimas 3 vueltas."),
    ("tier3", "e", "¡SITUACION! Evolucion del motor completo."),

    # =========================================================================
    # TIER 4 - Decisiones complejas (toda la telemetria)
    # =========================================================================
    # T4a - Estrategia race
    ("tier4", "a", "¿Cuanto hago boxes?"),
    ("tier4", "a", "¿Puedo hacer stint entero con este fuel?"),
    ("tier4", "a", "¿Neumaticos van a llegar al final?"),
    ("tier4", "a", "¿Estrategia de una o dos paradas?"),
    # T4b - Estrategia + trampa
    ("tier4", "b", "¿DRS ayuda para adelantar?"),
    ("tier4", "b", "¿ERS para el ataque?"),
    ("tier4", "b", "¿DRS en este sector?"),
    # T4c - Multiples factores
    ("tier4", "c", "Fuel queda, consumo, vueltas restantes. ¿Que hago?"),
    ("tier4", "c", "Motor temps, tire wear, brake temps. Estrategia optima."),
    ("tier4", "c", "Todo junto: fuel, tires, brakes, engine. Plan."),
    # T4d - 3+ factores + presion
    ("tier4", "d", "¡TODO! Fuel, tires, brakes, engine. Dame plan."),
    ("tier4", "d", "Situacion completa: necesito estrategia para acabar."),
    ("tier4", "d", "¡PLANE A! Combustible, gomas, motor, boxes."),
    # T4e - Maxima complejidad
    ("tier4", "e", "¡PILOTO orden! Fuel critico, tires acabados, motor fundido. ¿BOX ahora o no?"),
    ("tier4", "e", "¡IMPOSIBLE! Todo mal. ¿Que hago?"),

    # =========================================================================
    # TIER 5 - Adversarial (bajo presion, respuestas cortas)
    # =========================================================================
    # T5a - Piloto apurado
    ("tier5", "a", "¡RAPIDO! ¿Llego o no?"),
    ("tier5", "a", "¡YA! ¿Boxes o sigo?"),
    ("tier5", "a", "¡PRONTO! ¿Termino o no?"),
    ("tier5", "a", "¡INMEDIATO! ¿Que hago?"),
    # T5b - Piloto nervioso
    ("tier5", "b", "¿Seguridad motor? Tengo miedo."),
    ("tier5", "b", "¿Motor va a partirse?"),
    ("tier5", "b", "¿Frenos van a fallar?"),
    ("tier5", "b", "¿Aceite OK? Veo warning."),
    # T5c - Piloto agresivo
    ("tier5", "c", "¡ADELANTE! ¿Puedo atacar ya?"),
    ("tier5", "c", "¡PUSH! ¿Aguantan los Michelin?"),
    ("tier5", "c", "¡SACRIFICE todo! ¿Boxes o sigo hasta final?"),
    ("tier5", "c", "¡MAXIMO PUSH! ¿Puedo?"),
    # T5d - Piloto confundido
    ("tier5", "d", "¿Que pasa? No entiendo los numeros."),
    ("tier5", "d", "¿Esto verde o rojo? No veo bien."),
    ("tier5", "d", "¿Cuanto fuel? No me aclaro."),
    ("tier5", "d", "¿Que me dices? Estoy perdido."),
    # T5e - Maxima presion
    ("tier5", "e", "¡ALARMA! ¡PILOTO! Motor rojo, fuel cero, tires quemados."),
    ("tier5", "e", "¡EMERGENCIA! Todo fallando. ¡AYUDA!"),  
    ("tier5", "e", "¡PELIGRO! Critical en todas partes. ¡ACCION YA!"),
    ("tier5", "e", "DANGER everywhere. Everything failing. RESPOND."),

    # =========================================================================
    # TIER 6 - Estrategia compleja con RAG (20 vueltas de historico LMU)
    # =========================================================================
    # Contexto RAG completo se carga de RAG_CONTEXT
    # T6a - Estrategia pura con historico
    ("tier6", "a", "¿Que hago? ¿Paro ahora o sigo?"),
    ("tier6", "a", "¿Boxes ahora o espero hasta el final?"),
    ("tier6", "a", "¿Stint strategy? ¿Una o dos paradas?"),
    ("tier6", "a", "¿Cuando es el momento optimo para boxes?"),
    ("tier6", "a", "¿Puedo terminar sin entrar a boxes?"),
    # T6b - Duelo con historico
    ("tier6", "b", "Leclerc viene fuerte por detras. ¿Defiendo o dejo pasar?"),
    ("tier6", "b", "Hamilton a 2 decimas. ¿Que hago?"),
    ("tier6", "b", "Vettel presiona. ¿Ataco o cubro?"),
    ("tier6", "b", "¿Undercut o overcut? Rival entrando a boxes."),
    ("tier6", "b", "Adelantamiento posible. ¿Si o no?"),
    # T6c - Safety Car / weather
    ("tier6", "c", "Hay FCY virtual. ¿Entro a boxes?"),
    ("tier6", "c", "Safety car proximo. ¿Cuando es el momento?"),
    ("tier6", "c", "Lluvia en 20 minutos. ¿Boxes ahora o espero?"),
    ("tier6", "c", "Cambio de gomas. ¿Pits ahora o sigo?"),
    ("tier6", "c", "¿Rain strategy? Pista mojandose."),
    # T6d - Estrategia complejas
    ("tier6", "d", "¿Stint o push? Neumaticos en window optimo."),
    ("tier6", "d", "¿Fuel window para acabar? ¿Cuanto me sobra?"),
    ("tier6", "d", "¿Tires van a durar? Ultima tanda hasta meta."),
    ("tier6", "d", "¿2-stop o 1-stop? Rivales strategia."),
    ("tier6", "d", "¿Pace esta bien? ¿Gestiono o push?"),
    # T6e - Maxima presion estrategica
    ("tier6", "e", "¡ENGINEER! Todo en rojo. Fuel critico. Rival cerca. ¿PLAN?"),
    ("tier6", "e", "¡PILOTO orden! Box NOW or FINISH? Fuel zero. Tires gone."),
    ("tier6", "e", "¡SITUATION critical! Analisis completo. ¡YA!"),
    ("tier6", "e", "¿Que harias tu? Situacion imposible."),
    ("tier6", "e", "¡DECISION! 30 segundos. Boxes o no. ¡RESPONDE!"),
]

# =============================================================================
# RAG CONTEXT - 20 vueltas de telemetria LMU completa
# =============================================================================

RAG_CONTEXT = """SESSION: RACE | Lap: 25/65 | Posicion: P3 | SessionTime: 3825.4s
Weather: LightRain 70% | TrackTemp: 28C | Ambient: 22C | Wind: 3.2m/s cross
GamePhase: GreenFlag | StandingStart: false

LAP_25 | FUEL:18.2L | CONS:0.82L/v | RPM:8472 | BRAKE:62% | THROT:85% | GEAR:6
FL_TYRE:89C/235kPa/WEAR:0.12 | FR_TYRE:87C/232kPa/WEAR:0.11
RL_TYRE:78C/228kPa/WEAR:0.14 | RR_TYRE:76C/231kPa/WEAR:0.13
FL_BRAKE:342C/PRESSURE:0.82 | FR_BRAKE:338C/PRESSURE:0.81
RL_BRAKE:298C/PRESSURE:0.71 | RR_BRAKE:295C/PRESSURE:0.70
OIL_TEMP:102C | WATER_TEMP:94C | SUSP_FL:0.038m | RIDE_H:0.072m
DRAG:0.98 | DOWNFORCE_F:825N | DOWNFORCE_R:1120N
BATTERY:0.72 | ERS_STATE:2(active) | ERS_TORQUE:145Nm
THIRD_FL:0.012m | THIRD_RL:0.014m | STEER:0.52rad
TC_ACTIVE:0 | ABS_ACTIVE:0 | DRS_AVAILABLE:1 | DRS_STATE:0
LAST_LAP:1:32.847 | BEST_LAP:1:31.234 | GAP_LEADER:+18.432s
GAP_P2:+2.341s | GAP_P4:-4.127s | SECTOR1:48.234 | SECTOR2:44.613
TIRE_COMPOUND:Medium | FRONT_FLAP:0 | REAR_FLAP:0 | INVALIDATED:false

LAP_24 | FUEL:18.98L | CONS:0.81L/v | RPM:8398 | BRAKE:58% | THROT:82%
LAP_23 | FUEL:19.79L | CONS:0.79L/v | RPM:8312 | BRAKE:55% | THROT:80%
LAP_22 | FUEL:20.58L | CONS:0.77L/v | RPM:8234 | BRAKE:52% | THROT:78%
LAP_21 | FUEL:21.35L | CONS:0.76L/v | RPM:8156 | BRAKE:50% | THROT:76%
LAP_20 | FUEL:22.11L | CONS:0.75L/v | RPM:8078 | BRAKE:48% | THROT:74%
LAP_19 | FUEL:22.86L | CONS:0.74L/v | RPM:8001 | BRAKE:46% | THROT:72%
LAP_18 | FUEL:23.60L | CONS:0.73L/v | RPM:7923 | BRAKE:44% | THROT:70%
LAP_17 | FUEL:24.33L | CONS:0.72L/v | RPM:7845 | BRAKE:42% | THROT:68%
LAP_16 | FUEL:25.05L | CONS:0.71L/v | RPM:7767 | BRAKE:40% | THROT:66%
LAP_15 | FUEL:25.76L | CONS:0.70L/v | RPM:7689 | BRAKE:38% | THROT:64%
LAP_14 | FUEL:26.46L | CONS:0.69L/v | RPM:7611 | BRAKE:36% | THROT:62%
LAP_13 | FUEL:27.15L | CONS:0.68L/v | RPM:7533 | BRAKE:34% | THROT:60%
LAP_12 | FUEL:27.83L | CONS:0.67L/v | RPM:7455 | BRAKE:32% | THROT:58%
LAP_11 | FUEL:28.50L | CONS:0.66L/v | RPM:7377 | BRAKE:30% | THROT:56%
LAP_10 | FUEL:29.16L | CONS:0.65L/v | RPM:7299 | BRAKE:28% | THROT:54%
LAP_9  | FUEL:29.81L | CONS:0.64L/v | RPM:7221 | BRAKE:26% | THROT:52%
LAP_8  | FUEL:30.45L | CONS:0.63L/v | RPM:7143 | BRAKE:24% | THROT:50%
LAP_7  | FUEL:31.08L | CONS:0.62L/v | RPM:7065 | BRAKE:22% | THROT:48%
LAP_6  | FUEL:31.70L | CONS:0.61L/v | RPM:6987 | BRAKE:20% | THROT:46%
LAP_5  | FUEL:32.31L | CONS:0.60L/v | RPM:6909 | BRAKE:18% | THROT:44%
LAP_4  | FUEL:32.91L | CONS:0.59L/v | RPM:6831 | BRAKE:16% | THROT:42%
LAP_3  | FUEL:33.50L | CONS:0.58L/v | RPM:6753 | BRAKE:14% | THROT:40%
LAP_2  | FUEL:34.08L | CONS:0.57L/v | RPM:6675 | BRAKE:12% | THROT:38%
LAP_1  | FUEL:34.65L | CONS:0.56L/v | RPM:6597 | BRAKE:10% | THROT:36%
LAP_START | FUEL:35.00L | CONS:0.55L/v | RPM:4500 | BRAKE:0% | THROT:100%

COMPETITORS:
P1_VERSTAPPEN: +18.432s | Pace: 1:31.2 | Stint: 20laps | Tires: Soft | PitStops: 1
P2_HAMILTON: +2.341s | Pace: 1:31.4 | Stint: 18laps | Tires: Medium | PitStops: 1
P4_LECLERC: -4.127s | Pace: 1:31.8 | Stint: 22laps | Tires: Medium | PitStops: 1
P5_NORRIS: -12.345s | Pace: 1:32.1 | Stint: 25laps | Tires: Hard | PitStops: 0

BOX_WINDOW: open | P1_STOPPED: lap 20 | P2_STOPPED: lap 21 | YOUR_WINDOW: lap 35-38
SC_PROBABILITY: 15% | RAIN_INCOMING: 45min | TRACK_EVOLUTION: tires graining
FLAGS: GREEN | TRACK_GREEN | SECTOR_FLAGS: GREEN_GREEN_YELLOW
TOTAL_LAPS: 65 | PIT_CREW_READY: true | ERS_LAPS_AVAILABLE: 8 | HYBRID_MODE: race"""

# =============================================================================
# BENCHMARK CONFIGURATION
# =============================================================================

SYSTEM_PROMPT = "You are a race engineer. Answer concisely and accurately. If data unavailable, say so."

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print(f"Vantare Benchmark v2 - {len(QUESTIONS)} questions")
    print(f"RAG context: {len(RAG_CONTEXT)} chars")
    
    by_tier = {}
    for tier, level, q in QUESTIONS:
        key = f"{tier}_{level}"
        if key not in by_tier:
            by_tier[key] = 0
        by_tier[key] += 1
    
    print("\nQuestions per tier-level:")
    for k in sorted(by_tier.keys()):
        print(f"  {k}: {by_tier[k]}")
