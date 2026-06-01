#!/usr/bin/env python3
"""
Benchmark LLM V2 - Prompts realistas basados en telemetría LMU real.

Diferencias vs V1:
- L5 (RAG): Histórico rico de 5-10 vueltas con lap times, fuel used, tyre temps
- L3 (Triggers): Situaciones reales de carrera (SC deployed, tyre puncture, etc.)
- L1-L2: Campos adicionales LMU (RPM, ERS, DRS, engine temp)
- L8 (Temporal): Series más largas con 5 ticks para tendencias claras
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

try:
    import httpx
except ImportError:
    httpx = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("benchmark_v2")

# =============================================================================
# SYSTEM PROMPT - Más conciso y dirigido
# =============================================================================

SYSTEM_PROMPT = """Eres un ingeniero de carrera de Elite Motorsport. Responde en estilo radio.
Máximo 2-3 frases. Sé técnico y conciso.

DATOS LMU DISPONIBLES (formato ticker):
- DRV: posicion, vuelta, combustible (L), consumo (L/v), vueltas restantes
- TYR: desgaste %, temperaturas °C
- BRK: desgaste %
- GAP: rival adelante/atrás, mejor vuelta, diferencia de ritmo (d+0.1 = +0.1s más lento)
- SES: clase (HY/GT3), tipo (RACE/QUALI), vueltas totales, tiempo restante
- WTH: agarre (GRN/LOW/MED/HIG/SAT), temp °C, probabilidad lluvia, Safety Car (S/N)
- RIV: coches en pista, gap grupos (CLS1 <5s, CLS2 5-30s, FAR >30s), doblados

IMPORTANTE:
- Si no tienes datos en el ticker, di "no tengo datos"
- "d-0.3" significa: tu mejor vuelta es 0.3s más lento que el rival
- "d+0.3" significa: tu mejor vuelta es 0.3s más rápido que el rival"""

# =============================================================================
# TICKERS REALISTAS - Con campos adicionales LMU
# =============================================================================

TICKERS = {
    # Ticker A: Hypercar, mitad de carrera, seco, P3, batalla cerrada
    "A": """DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96°C
BRK:38/35/22/20%
GAP>VST:+2.1s|best1:48.2|d-0.3|<ALO:-1.2s|best1:47.9
SES:HY|RACE|38L|45:22
WTH:MED|22°C|30%|+15min|SC:N
RIV:20 cars
CLS1(3):VST+2.1|V10, ALO-1.2|V10, LEC+4.8|V10
CLS2(5):HAM+8.5, VER+12.3, NOR+15.1, PIA+18.7, RUS+25.3
FAR:8 cars|+45s
LAP:PER-1L, TSU-2L, STR-2L, ZHO-3L""",

    # Ticker B: Liderando, lluvia aproximandose, Hypercar
    "B": """DRV:P1|L25|F:28.5L/3.3(7L)|TYR:55/52/50/48|88/90/91/89°C
GAP>---|<HAM:-5.3s|best1:47.5|d+0.8
SES:HY|RACE|38L|20:15
WTH:LOW|18°C|80%|+3min|SC:N
RIV:20 cars
CLS1(2):HAM-5.3|V24, VER-8.1|V24
CLS2(4):LEC-12.4, NOR-15.8, PIA-18.2, RUS-22.1
FAR:10 cars|+50s
LAP:PER-1L, TSU-2L, STR-2L, ZHO-3L""",

    # Ticker C: Safety Car, post-pit, P8
    "C": """DRV:P8|L8|F:89.7L/3.1(27L)|TYR:98/97/96/96|85/87/88/86°C
GAP>BOT:+0.8s|best1:49.5|d-0.7|<SAI:-0.4s|best1:49.1
SES:HY|RACE|38L|52:00
WTH:GRN|26°C|10%|+0min|SC:S
RIV:20 cars
CLS1(4):BOT+0.8|V7, SAI-0.4|V8, ALB+1.2|V8, OCO-2.1|V7
CLS2(3):STR+8.9, TSU+12.4, ALO+15.3
FAR:8 cars|+60s
LAP:PER-2L, ZHO-2L, NOR-1L, LEC-1L, HAM-1L""",

    # Ticker D: GT3 qualy, vueltas iniciales, sin TYR
    "D": """DRV:P5|L2|F:96.8L/3.1(28L)|TYR:---
GAP>VER:+3.5s|best1:47.8|d-0.7|<NOR:-2.1s|best1:48.5
SES:GT3|QUALI|12L|55:30
WTH:GRN|20°C|5%|+0min|SC:N
RIV:22 cars
CLS1(3):VER+3.5|V1, NOR-2.1|V2, ALO+4.2|V2
CLS2(5):HAM+7.8, LEC+11.2, RUS+14.5, PIA+18.1, BOT+21.7
FAR:8 cars|+40s
LAP:---""",

    # Ticker E: Final carrera, combustible crítico
    "E": """DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|95/97/98/94°C
BRK:75/72/68/65%
GAP>ALB:+15.2s|best1:49.8|d+0.3|<TSU:-8.3s|best1:49.5
SES:GT3|RACE|38L|3:45
WTH:LOW|15°C|90%|+0min|SC:N
RIV:22 cars
CLS2(4):ALB+15.2, TSU-8.3, OCO+18.7, MAG-12.1
FAR:14 cars|+90s
LAP:PER-2L, ZHO-2L, NOR-1L, STR-1L""",

    # Ticker F: Neumaticos sobrecalentados, P6
    "F": """DRV:P6|L18|F:35.1L/3.2(9L)|TYR:65/62/60/58|100/102/103/101°C
BRK:42/40/38/36%
GAP>RUS:+6.2s|best1:48.9|d+0.5|<BOT:-4.1s|best1:48.4
SES:HY|RACE|38L|30:00
WTH:MED|24°C|40%|+20min|SC:N
RIV:20 cars
CLS2(6):RUS+6.2, BOT-4.1, STR+11.3, TSU+16.7, ALB+22.4, MAG+28.1
FAR:8 cars|+55s
LAP:PER-2L, ZHO-2L, NOR-1L, LEC-1L, HAM-1L, PIA-1L""",

    # Ticker G: Ventana boxes abierta, stint strategy
    "G": """DRV:P4|L14|F:53.1L/3.2(15L)|TYR:45/42/40/38|90/92/93/91°C
BRK:25/22/18/15%
GAP>LEC:+3.1s|best1:48.1|d-0.5|<RUS:-1.8s|best1:48.6
SES:HY|RACE|38L|40:00
WTH:MED|21°C|50%|+10min|SC:N
RIV:20 cars
CLS1(2):LEC+3.1|V13, RUS-1.8|V14
CLS2(4):VER+7.5, HAM+11.3, NOR+14.8, ALO+19.2
FAR:7 cars|+42s
LAP:PER-1L, ZHO-2L, STR-2L, TSU-3L, PIA-3L, BOT-4L, MAG-4L""",

    # Ticker H: SC deployed, early race
    "H": """DRV:P2|L6|F:82.4L/3.1(25L)|TYR:95/94/93/92|85/86/87/85°C
BRK:10/8/5/5%
GAP>VER:+1.5s|best1:47.9|d-0.8|<NOR:-3.2s|best1:48.7
SES:HY|RACE|38L|54:00
WTH:GRN|23°C|15%|+0min|SC:S
RIV:20 cars
CLS1(2):VER+1.5|V5, NOR-3.2|V6
CLS2(5):LEC+8.1, RUS+11.5, ALO+14.3, HAM+18.9, PIA+23.4
FAR:6 cars|+38s
LAP:PER-1L, ZHO-1L, STR-1L, TSU-2L, BOT-2L, MAG-2L, OCO-2L""",
}

# =============================================================================
# HISTÓRICO RICO PARA L5 (RAG) - 5-10 vueltas de datos reales
# =============================================================================

HISTORICO_L5 = {
    # Histórico para Ticker A: 5 vueltas de fuel, tyre wear, lap times
    "A_consumo": """HISTORICO CARRERA (ultimas 5 vueltas):
V5: Lap time 1:48.2 | Fuel used 3.1L | Tyre 52/50/48/47% | Brake 28/26/18/17%
V6: Lap time 1:48.5 | Fuel used 3.2L | Tyre 58/56/54/52% | Brake 32/30/22/20%
V7: Lap time 1:48.1 | Fuel used 3.2L | Tyre 64/62/60/58% | Brake 35/33/25/23%
V8: Lap time 1:48.9 | Fuel used 3.3L | Tyre 68/66/64/61% | Brake 38/36/28/26%
V9: Lap time 1:49.2 | Fuel used 3.4L | Tyre 72/68/65/63% | Brake 38/35/22/20%

TENDENCIA OBSERVADA:
- Fuel: 3.1 → 3.2 → 3.2 → 3.3 → 3.4 (+0.3L/vuelta)
- Tyre FL: 52 → 58 → 64 → 68 → 72% (+20% en 5 vueltas)
- Brake FL: 28 → 32 → 35 → 38 → 38% (estabilizado)""",

    "A_rivales": """HISTORICO RIVALES (ultimas 5 vueltas):
V5: VST best 1:47.8, ALO best 1:48.3, gap VST +1.5s
V6: VST best 1:48.0, ALO best 1:48.5, gap VST +2.0s
V7: VST best 1:47.9, ALO best 1:48.2, gap VST +1.9s
V8: VST best 1:48.3, ALO best 1:48.7, gap VST +2.5s
V9: VST best 1:48.2, ALO best 1:47.9, gap VST +2.1s

TENDENCIA: VST está manteniendo ritmo consistente (~1:48.0), ALO ha mejorado a 1:47.9""",

    "A_clima": """HISTORICO CLIMA:
V15: GRN, 20°C, 10% lluvia, seca
V18: MED, 22°C, 25% lluvia, seco
V20: MED, 23°C, 35% lluvia, seco
V22: MED, 22°C, 45% lluvia, seco
V24: LOW, 20°C, 60% lluvia, seco

TENDENCIA: Grip cayendo de GRN a MED, probabilidad lluvia aumentando 10%→60%""",

    # Histórico para Ticker B: Strategy race
    "B_undercut": """HISTORICO STRATEGY:
V18: HAM entra a boxes (undercut) | Sale P3 | New tyres | Delta +2.5s
V19: HAM rápido, reduce gap | P3
V20: HAM best 1:47.2 | Estamos P1 con 28.5L

UNDERECUT DETECTADO: HAM entró V18, salió 3s por detrás pero con neumáticos frescos.
Nuestro ritmo con neumáticos viejos: 1:48.5 avg
Ritmo HAM con nuevos: 1:47.2 avg
Gap closing: 3.0s → 2.2s → 1.8s → 1.5s""",

    # Histórico para Ticker E: Final stint
    "E_stint_final": """STINT ACTUAL (ultimas 5 vueltas):
V30: Lap 1:50.8 | Fuel 32.1L | TYR 78/76/74/72% | Temp 88/90/92/91°C
V31: Lap 1:51.2 | Fuel 28.7L | TYR 82/80/78/76% | Temp 91/93/95/93°C
V32: Lap 1:52.1 | Fuel 25.3L | TYR 85/83/81/79% | Temp 93/95/97/95°C
V33: Lap 1:52.8 | Fuel 21.9L | TYR 87/85/83/81% | Temp 94/96/98/96°C
V34: Lap 1:53.5 | Fuel 18.5L | TYR 88/85/83/80% | Temp 95/97/98/94°C

ANÁLISIS:
- Degradación acelerándose: 2.4s → 2.7s → 3.2s → 3.5s
- Fuel burn: 3.4L/vuelta (por encima del plan 3.1L)
- Temp FL alcanzando 95°C (límite 100°C)
- BL舒适性: +0.5s/vuelta vs stint anterior""",

    # Histórico para Ticker G: Pit window
    "G_pit_window": """VENTANA BOXES ANALYSIS:
V10: Entrada boxes abierta | Optimal: V12-V16 | Window closes V20
V11: ALB entra boxes | Sale P6 | New Medium | Delta +1.8s
V12: LEC entra boxes | Sale P4 | New Medium | Delta +1.5s

NUESTRO STINT:
V10: TYR 35/33/31/29% | Fuel 65.8L | Gap LEC +8.2s
V11: TYR 38/36/34/32% | Fuel 62.6L | Gap LEC +5.5s
V12: TYR 42/40/38/36% | Fuel 59.4L | Gap LEC +4.1s
V13: TYR 45/42/40/38% | Fuel 56.2L | Gap LEC +3.5s

OPCIÓN UNDERCUT: Si entramos ahora (V13), salimos por detrás de LEC pero con ritmo mejor.
OPCIÓN OVERCUT: Esperar V16, entrar antes del cierre, salir por delante.""",

    # Histórico para Ticker F: Overheating
    "F_overheating": """TENDENCIA TEMPERATURAS (ultimas 5 vueltas):
V13: FL 92°C, FR 94°C, RL 96°C, RR 95°C
V14: FL 95°C, FR 97°C, RL 99°C, RR 97°C
V15: FL 97°C, FR 99°C, RL 101°C, RR 100°C
V16: FL 99°C, FR 101°C, RL 103°C, RR 102°C
V17: FL 100°C, FR 102°C, RL 103°C, RR 101°C

ALERTA: Temperatura FL subiendo +2°C/vuelta
Límite operativo: 105°C
Margen remaining: 5°C FL, 3°C FR, 2°C RL

CAUSA: Track temp 24°C + stint length 18 vueltas + degraded tyres""",
}

# =============================================================================
# GENERADORES DE PROMPTS MEJORADOS
# =============================================================================

def _p(ticker_id: str, question: str, expected: list[str],
       rag_context: str = None, trigger: str = None,
       rubric: dict = None) -> dict:
    """Construye un prompt estructurado."""
    return {
        "ticker_id": ticker_id,
        "ticker": TICKERS.get(ticker_id, ""),
        "question": question,
        "expected_keywords": expected,
        "rag_context": rag_context,
        "trigger": trigger,
        "rubric": rubric or {},
    }


def generate_level_1() -> list[dict]:
    """Nivel 1: Extracción literal de campos LMU."""
    return [
        # Campos DRV
        _p("A", "¿Cuál es mi posición y vuelta actual?", ["P3", "L10", "3", "10"]),
        _p("A", "¿Cuánto combustible tengo y para cuántas vueltas?", ["42.3", "13", "L"]),
        _p("A", "¿Cuál es mi consumo promedio por vuelta?", ["3.2", "3.2L"]),
        _p("B", "¿Cuántas vueltas de combustible me quedan?", ["7", "7L"]),

        # Campos TYR
        _p("A", "¿Cuál es el desgaste del neumático trasero derecho?", ["63", "63%"]),
        _p("A", "¿Qué temperatura tiene el neumático delantero izquierdo?", ["92", "92°C"]),
        _p("F", "¿El neumático trasero izquierdo está cerca del límite de temperatura?", ["100", "101", "cerca", "límite"]),
        _p("C", "¿Los neumáticos están casi nuevos después del pit stop?", ["98", "97", "96", "96", "nuevos"]),

        # Campos BRK
        _p("A", "¿Cuál es el desgaste del freno trasero derecho?", ["20", "20%"]),
        _p("E", "¿Los frenos están críticos? ¿Cuál es el más caliente?", ["75", "72", "crítico", "delantero"]),

        # Campos GAP
        _p("A", "¿Quién va delante y a qué distancia? ¿Y el de atrás?", ["VST", "2.1", "ALO", "1.2"]),
        _p("A", "¿Estoy ganando o perdiendo ritmo con ALO?", ["d-0.3", "más rápido", "ALO", "0.3"]),
        _p("B", "¿Estoy liderando? ¿Cuánto gano a HAM?", ["P1", "lidero", "5.3", "HAM"]),
        _p("C", "¿Cuál es el gap exacto con BOT?", ["+0.8", "0.8", "BOT"]),

        # Campos SES
        _p("A", "¿Cuántas vueltas tiene la carrera y cuánto tiempo queda?", ["38", "45:22", "45"]),
        _p("D", "¿Qué tipo de sesión es? ¿Entrenamiento o clasificación?", ["QUALI", "GT3"]),

        # Campos WTH
        _p("A", "¿Está lloviendo o hay probabilidad?", ["30%", "15min", "no"]),
        _p("B", "¿En cuántos minutos llega la lluvia?", ["3", "3min", "minutos"]),
        _p("B", "¿Cuál es el nivel de agarre actual?", ["LOW", "18°C", "bajo"]),
        _p("C", "¿El Safety Car está desplegado?", ["SC:S", "sí", "activo"]),

        # Campos RIV
        _p("A", "¿Cuántos coches hay en pista?", ["20", "20 cars"]),
        _p("A", "¿Quiénes son mis rivales principales (gap < 5s)?", ["VST", "ALO", "LEC", "CLS1"]),

        # Edge cases
        _p("D", "¿Por qué no hay datos de neumáticos?", ["vuelta 2", "3", "no representativo"]),
        _p("B", "¿Cuánto combustible gasto por vuelta en este stint?", ["3.3", "3.3L"]),
        _p("E", "¿Tengo combustible para llegar a meta?", ["0", "0L", "crítico", "no"]),

        # Campos adicionales reales LMU
        _p("C", "¿Cuántos coches hay doblados?", ["5", "LAP"]),
        _p("A", "¿Cuántos rivales están muy lejos (+30s)?", ["8", "45s", "FAR"]),
    ]


def generate_level_2() -> list[dict]:
    """Nivel 2: Interpretación de campos LMU."""
    return [
        # Interpretación DRV
        _p("A", "¿Puedo hacer la distancia hasta el final con este combustible?", ["sí", "13", "L", "suficiente"]),
        _p("E", "¿Tengo combustible para otra vuelta?", ["0", "0L", "crítico", "no"]),
        _p("B", "¿El consumo ha aumentado o disminuido en este stint?", ["3.3", "aumentado", "más"]),

        # Interpretación TYR
        _p("F", "¿Debería cambiar los neumáticos ahora mismo?", ["sí", "102", "103", "sobrecalentado", "entrar"]),
        _p("G", "¿Cuántas vueltas puedo hacer con estos neumáticos?", ["15", "42", "moderado", "ok"]),
        _p("C", "¿Los neumáticos están suficientemente frescos después del pit?", ["98", "97", "sí", "nuevos"]),

        # Interpretación GAP
        _p("A", "¿Estoy amenazado por ALO desde atrás?", ["-1.2", "sí", "cerca", "atrás"]),
        _p("B", "¿HAM me está alcanzando desde detrás?", ["-5.3", "no", "lejos", "OK"]),
        _p("C", "¿El gap con SAI es crítico (dentro de 1s)?", ["-0.4", "sí", "crítico", "cerca"]),

        # Interpretación SES
        _p("A", "¿Queda más de la mitad de la carrera?", ["38", "45:22", "sí", "mitad"]),
        _p("E", "¿Estamos en la fase final de la carrera?", ["3:45", "sí", "final"]),

        # Interpretación WTH
        _p("B", "¿El Safety Car podría desplegarse pronto?", ["80%", "LOW", "posible", "lluvia"]),
        _p("F", "¿Las condiciones son óptimas para rendimiento?", ["MED", "24°C", "sí", "ok"]),

        # Interpretación estratégica
        _p("G", "¿Es buen momento para entrar a boxes?", ["ventana", "abierta", "sí", "LEC"]),
        _p("H", "¿Debería esperar durante el SC para entrar más tarde?", ["82.4", "lleno", "no", "esperar"]),
        _p("A", "¿Tengo margen de combustible suficiente para probar undercut?", ["42.3", "sí", "margen"]),
    ]


def generate_level_3() -> list[dict]:
    """Nivel 3: Triggers reales de carrera."""
    return [
        # Safety Car triggers
        _p("C", "SC desplegado. ¿Qué hago con este combustible lleno (89.7L)?",
           ["esperar", "no entrar", "lleno", "ventaja"],
           trigger="safety_car_deployed"),
        _p("H", "SC activo. Neumáticos nuevos, combustible 82.4L. ¿Entro ahora?",
           ["esperar", "no", "ventaja", "SC"],
           trigger="safety_car_early"),

        # Fuel critical triggers
        _p("E", "Combustible 0L. ¿Qué hago?",
           ["entrar", "inmediato", "ahora", "urgente"],
           trigger="fuel_critical",
           rubric={"must_prioritize_pit": True}),

        # Tyre overheating triggers
        _p("F", "Temperaturas FL 100°C, FR 102°C, RL 103°C. ¿Entro a boxes?",
           ["sí", "entrar", "enfriar", "103"],
           trigger="tyre_overheating",
           rubric={"identifies_overheating": True}),

        # Weather change triggers
        _p("B", "Lluvia 80% probabilidad, 3 minutos. Neumáticos slicks. ¿Cambio?",
           ["intermedios", "lluvia", "entrar", "ahora"],
           trigger="weather_change_imminent"),

        # Undercut detection
        _p("A", "ALO acaba de entrar a boxes. ¿Me ataca por undercut?",
           ["undercut", "ALO", "boxes", "sí", "atacar"],
           trigger="competitor_undercut"),

        # Gap closing triggers
        _p("G", "Gap con LEC +3.1s cerrando. ¿Cuánto puedo ganar entrando ahora?",
           ["3.1", "undercut", "si", "entrar", "cubrir"],
           trigger="gap_closing"),

        # Pit window triggers
        _p("G", "Ventana abierta, neumáticos 45%. ¿Entro ahora o espero?",
           ["ahora", "ventana", "abierta", "entrar"],
           trigger="pit_window_opened"),

        # Strategy recommendation
        _p("A", "STINT de 10 vueltas con neumáticos 72%. ¿Estrategia óptima?",
           ["15", "entrar", "vueltas", "gestionar"],
           trigger="long_stint_strategy"),

        # Brake warning
        _p("E", "Frenos 75%. ¿Qué riesgo tengo?",
           ["frenos", "75%", "crítico", "reducir"],
           trigger="brake_wear_warning"),
    ]


def generate_level_4() -> list[dict]:
    """Nivel 4: Razonamiento multicampo."""
    return [
        _p("A", "P3 con VST +2.1s y ALO -1.2s. Neumáticos 72%, combustible 42.3L. ¿Analiza la batalla?",
           ["P3", "VST", "ALO", "72%", "42.3"]),
        _p("B", "Liderando con 28.5L, lluvia 80% en 3min, HAM -5.3s. ¿Estrategia?",
           ["28.5", "HAM", "5.3", "lluvia", "cambiar"]),
        _p("C", "SC activo, P8, neumáticos 98%, combustible 89.7L. ¿Espero o entro?",
           ["SC", "P8", "98%", "89.7", "esperar"]),
        _p("F", "Neumáticos sobrecalentados (100-103°C), gap RUS +6.2s, BOT -4.1s. ¿Qué priorizo?",
           ["103", "RUS", "BOT", "enfriar"]),
        _p("G", "Ventana boxes abierta, TYR 45%, gap LEC +3.1s y RUS -1.8s. ¿Undercut o overcut?",
           ["45%", "LEC", "3.1", "RUS", "undercut"]),
        _p("E", "Combustible 0L, neumáticos 88%, brecha ALB +15.2s, TSU -8.3s. ¿Crítico?",
           ["0L", "88%", "ALB", "TSU", "combustible"]),

        # Multi-field analysis
        _p("H", "SC en V6, P2, FR 94°C, gap VER +1.5s. ¿Análisis completo?",
           ["SC", "P2", "94°C", "VER", "1.5"]),
        _p("A", "Neumáticos 72%, brakes 38%, fuel 42.3L, gap VST +2.1s. ¿Estado del coche?",
           ["72%", "38%", "42.3", "2.1"]),
        _p("D", "QUALI GT3, P5, fuel 96.8L, sin TYR, gap VER +3.5s. ¿Tiempo objetivo?",
           ["QUALI", "P5", "96.8", "VER", "3.5"]),
        _p("B", "P1, fuel 28.5L/3.3L/v, LLUVIA 80%, gap HAM -5.3s. ¿Plan completo?",
           ["P1", "28.5", "3.3", "HAM", "5.3", "lluvia"]),
    ]


def generate_level_5() -> list[dict]:
    """Nivel 5: RAG con histórico rico (5-10 vueltas)."""
    return [
        # Consumo con histórico detallado
        _p("A", "¿El consumo de combustible está aumentando? ¿Cuánto he ganado o perdido?",
           ["3.1", "3.4", "aumentando", "+0.3", "sí"],
           rag_context=HISTORICO_L5["A_consumo"]),

        # Rival pace con histórico
        _p("A", "¿VST ha mejorado o empeorado su ritmo en las últimas 5 vueltas?",
           ["1:47.8", "1:48.2", "consistent", "mejorado", "empeorado"],
           rag_context=HISTORICO_L5["A_rivales"]),

        # Clima con tendencia
        _p("B", "¿Está empeorando el clima? ¿Cuánto ha variado la probabilidad de lluvia?",
           ["10%", "60%", "aumentando", "sí", "peor"],
           rag_context=HISTORICO_L5["A_clima"]),

        # Undercut analysis
        _p("B", "¿HAM me está alcanzando con el undercut? ¿Cuánto ha cerrado el gap?",
           ["2.5", "1.5", "si", "cerrando", "HAM"],
           rag_context=HISTORICO_L5["B_undercut"]),

        # Final stint analysis
        _p("E", "¿La degradación de neumáticos se está acelerando? ¿Cuánto más lento por vuelta?",
           ["2.4", "3.5", "acelerando", "+1.1", "sí"],
           rag_context=HISTORICO_L5["E_stint_final"]),

        # Pit window strategy
        _p("G", "¿Cuál es mejor: undercut (entrar ahora) u overcut (esperar V16)?",
           ["undercut", "overcut", "V13", "V16", "LEC"],
           rag_context=HISTORICO_L5["G_pit_window"]),

        # Overheating trend
        _p("F", "¿Cuántas vueltas tengo antes de que los neumáticos excedan 105°C?",
           ["100", "103", "2", "vueltas", "105"],
           rag_context=HISTORICO_L5["F_overheating"]),

        # Tyre deg comparison
        _p("A", "¿Mi degradación de neumáticos es normal o algo está mal?",
           ["20%", "normal", "5", "vueltas", "ok"],
           rag_context=HISTORICO_L5["A_consumo"]),

        # Brake wear trend
        _p("E", "¿Los frenos están peor que el stint anterior? ¿Qué incremento hay?",
           ["75%", "estabilizado", "no", "normal"]),
        _p("F", "¿La temperatura de los neumáticos está bajo control o es crítica?",
           ["100", "102", "103", "crítico", "no", "control"]),
    ]


def generate_level_6() -> list[dict]:
    """Nivel 6: Multi-trigger con priorización."""
    return [
        # Triple threat: Fuel + Weather + Tyres
        _p("E", "Combustible 0L, lluvia 90% ahora, neumáticos 88%. ¿Prioridad?",
           ["combustible", "urgente", "entrar", "lluvia"],
           trigger="fuel_critical+weather_change",
           rubric={"must_prioritize_pit_immediate": True}),

        # SC + Gap + Window
        _p("C", "SC activo, gap BOT +0.8s, ventana cerrándose. ¿Entro ahora?",
           ["sí", "entrar", "SC", "BOT", "0.8"],
           trigger="safety_car+gap_closed+window_closing"),

        # Tyres + Weather + Strategy
        _p("G", "Neumáticos 45%, lluvia 50% en 10min, ventana abierta. ¿Plan?",
           ["entrar", "ahora", "lluvia", "45%", "ventana"],
           trigger="tyre_deg+weather_change+window_opened"),

        # Undercut + Gap + Position
        _p("A", "ALO entró boxes, gap VST +2.1s cerrando, P3. ¿Ataco o cubro?",
           ["undercut", "VST", "cubrir", "ALO"],
           trigger="undercut+gab_changing+position"),

        # Overheating + Fuel + Safety
        _p("F", "FL 100°C, FR 102°C, fuel 35.1L, RUS +6.2s. ¿Qué hago primero?",
           ["enfriar", "frenos", "entrar", "100"],
           trigger="overheating+fuel_critical"),

        # SC early entry decision
        _p("H", "SC en V6, fuel 82.4L, tyres 95%. Esperar V10 o entrar ahora?",
           ["esperar", "no", "82.4", "lleno", "V10"],
           trigger="safety_car+early_entry"),

        # Complex weather decision
        _p("B", "Lluvia en 3min, fuel 28.5L para 7vueltas, gap HAM -5.3s. ¿Cambio a inters?",
           ["sí", "lluvia", "inter", "3min", "HAM"],
           trigger="weather_imminent+fuel_ok+gap"),

        # Brake + Tyre + Strategy
        _p("E", "Frenos 75%, tyres 88%, fuel 5.2L, TSU -8.3s. ¿Riesgo crítico?",
           ["combustible", "75%", "88%", "entrar", "urgente"],
           trigger="fuel_critical+brake_wear"),

        # Position defense
        _p("G", "LEC +3.1s, RUS -1.8s, tyres 45%, fuel 53.1L. ¿Defiendo o ataco?",
           ["RUS", "atacar", "1.8", "45%", "defender"],
           trigger="gap_both+strategy"),

        # Late race strategy
        _p("E", "3:45 para final, fuel 5.2L, ALB +15.2s, tyres 88%. ¿Puedo llegar?",
           ["3.4", "0", "no", "entrar", "ahora"],
           trigger="final_stint+fuel_critical"),
    ]


def generate_level_7() -> list[dict]:
    """Nivel 7: Edge cases y anomalías."""
    return [
        # Missing TYR data
        _p("D", "¿Por qué no hay datos de neumáticos en este ticker?",
           ["vuelta 2", "3", "no representativo", "nuevos"]),

        # Contradictory data
        _p("C", "Fuel 89.7L (lleno) pero P8 post-pit. ¿Estrategia correcta?",
           ["larga", "stint", "esperar", "ventaja"]),

        # Boundary values
        _p("F", "FL 100°C, FR 102°C, RL 103°C. ¿Estoy en el límite exacto?",
           ["sí", "102", "103", "límite", "105"]),

        # Safety Car edge case
        _p("H", "Solo 1 rival en CLS1 (VER +1.5s). ¿Es buena señal o alerta?",
           ["VER", "1.5", "bien", "cerca"]),

        # Leader without gap ahead
        _p("B", "¿Por qué no hay sección '>' en GAP?",
           ["P1", "lidero", "delante", "nadie"]),

        # Empty sections
        _p("E", "¿Hay rivales muy lejanos (más de 30s)?",
           ["90s", "FAR", "sí", "14", "lejanos"]),

        # No lapped cars
        _p("B", "¿Hay coches doblados en esta vuelta?",
           ["LAP", "4", "sí", "PER", "TSU"]),

        # Missing WTH data
        _p("D", "¿Qué tiempo hace? No veo datos de clima.",
           ["no", "WTH", "datos", "GRN", "20°C"]),

        # Equal tyre temps
        _p("C", "Las 4 temperaturas de neumáticos casi iguales (85-88°C). ¿Qué indica?",
           ["nuevos", "pocas", "vueltas", "normal"]),

        # Last lap fuel
        _p("E", "Fuel 5.2L en vuelta 35 de 38. ¿Puedo hacer las 3 vueltas restantes?",
           ["3.4", "0", "no", "crítico"]),

        # Gap at exact threshold
        _p("A", "Gap VST +2.1s. ¿Es seguro o debo intentar atacar?",
           ["2.1", "seguro", "VST", "atacar", "no"]),

        # Session type edge
        _p("D", "¿La sesión es clasificatoria? ¿Cambia la estrategia?",
           ["QUALI", "GT3", "sí", "diferente", "apretar"]),

        # BRK not available
        _p("D", "¿Tengo datos de freno? No veo la línea BRK.",
           ["no", "BRK", "datos", "disponible"]),

        # Large gap change
        _p("A", "Gap VST +2.1s pero hace 2 vueltas era +1.5s. ¿Qué pasó?",
           ["VST", "alejando", "2.1", "1.5", "perdido"]),

        # Near pit window close
        _p("G", "Ventana cierra en 4 vueltas. ¿Entro ahora o espero?",
           ["4", "cerrando", "ahora", "ventana"]),
    ]


def generate_level_8() -> list[dict]:
    """Nivel 8: Series temporales con 5 ticks."""
    # Serie 1: Tyre deg acceleration + gap evolution
    series_tyre_gap = """SERIE TEMPORAL (5 ticks, misma vuelta):

TICK 1 (V10): DRV:P3|L10|F:42.3L|TYR:72/68/65/63|92/94/98/96°C|GAP>VST:+2.1
TICK 2 (V11): DRV:P3|L11|F:39.1L|TYR:68/64/61/59|94/96/100/98°C|GAP>VST:+2.8
TICK 3 (V12): DRV:P3|L12|F:35.9L|TYR:63/59/57/55|96/98/102/100°C|GAP>VST:+3.5
TICK 4 (V13): DRV:P3|L13|F:32.7L|TYR:58/55/52/50|98/100/104/102°C|GAP>VST:+4.2
TICK 5 (V14): DRV:P3|L14|F:29.5L|TYR:52/50/48/46|100/102/105/103°C|GAP>VST:+4.8"""

    # Serie 2: Position gaining + pace improvement
    series_position = """SERIE TEMPORAL (5 ticks):

TICK 1 (V8):  DRV:P5|L8|F:72.4L|TYR:95/93/91/89|85/86/87/85°C|GAP>VER:+5.1|d-0.7
TICK 2 (V9):  DRV:P4|L9|F:69.2L|TYR:88/86/84/82|86/88/89/87°C|GAP>VER:+3.8|d-0.5
TICK 3 (V10): DRV:P4|L10|F:66.0L|TYR:82/80/78/76|87/89/90/88°C|GAP>VER:+2.9|d-0.3
TICK 4 (V11): DRV:P3|L11|F:62.8L|TYR:75/73/71/69|88/90/91/89°C|GAP>VER:+2.1|d-0.1
TICK 5 (V12): DRV:P3|L12|F:59.6L|TYR:68/66/64/62|89/91/92/90°C|GAP>VER:+1.5|d+0.1"""

    # Serie 3: Overheating crisis
    series_overheat = """SERIE TEMPORAL (5 ticks):

TICK 1 (V14): DRV:P6|L14|F:38.9L|TYR:65/62/60/58|100/102/103/101°C|BRK:42/40/38/36%
TICK 2 (V15): DRV:P6|L15|F:35.7L|TYR:68/65/63/60|102/104/105/102°C|BRK:45/43/40/38%
TICK 3 (V16): DRV:P6|L16|F:32.5L|TYR:71/68/66/63|104/106/107/104°C|BRK:48/46/43/41%
TICK 4 (V17): DRV:P6|L17|F:29.3L|TYR:74/71/69/66|106/108/109/106°C|BRK:51/49/46/44%
TICK 5 (V18): DRV:P6|L18|F:26.1L|TYR:77/74/72/69|108/110/111/108°C|BRK:54/52/49/47%"""

    # Serie 4: Fuel critical countdown
    series_fuel = """SERIE TEMPORAL (5 ticks):

TICK 1 (V31): DRV:P12|L31|F:18.5L/3.4(4L)|TYR:88/85/83/80|95/97/98/94°C
TICK 2 (V32): DRV:P12|L32|F:15.1L/3.4(3L)|TYR:90/87/85/82|96/98/99/95°C
TICK 3 (V33): DRV:P12|L33|F:11.7L/3.4(2L)|TYR:92/89/87/84|97/99/100/96°C
TICK 4 (V34): DRV:P12|L34|F:8.3L/3.4(1L)|TYR:94/91/89/86|98/100/101/97°C
TICK 5 (V35): DRV:P12|L35|F:5.2L/3.4(0L)|TYR:96/93/91/88|99/101/102/98°C"""

    return [
        # Tyre + Gap evolution
        _p("A", "Analiza la tendencia de degradación de neumáticos en los 5 ticks. ¿Cuántas vueltas quedan?",
           ["52", "50", "48", "105", "2", "vueltas"],
           rag_context=series_tyre_gap),

        _p("A", "VST se está alejando (+2.1 → +4.8s en 4 ticks). ¿Qué está pasando?",
           ["VST", "alejando", "2.1", "4.8", "sí", "perdiendo"]),

        # Position gain
        _p("A", "Hemos pasado de P5 a P3 en 5 ticks. ¿Qué ha cambiado?",
           ["P5", "P4", "P3", "ganando", "VER", "adelantando"]),
        _p("A", "¿Nuestro ritmo está mejorando o empeorando respecto a VER?",
           ["d-0.7", "d-0.5", "d-0.3", "d-0.1", "d+0.1", "mejorando"]),

        # Overheating trend
        _p("F", "Las temperaturas RL están subiendo: 103 → 105 → 107 → 109 → 111°C. ¿Cuántas vueltas?",
           ["111", "109", "107", "105", "2", "vueltas", "límite", "105"]),
        _p("F", "¿Los frenos están funcionando normalmente o hay problema?",
           ["42", "45", "48", "51", "54", "normal", "incremento"]),

        # Fuel countdown
        _p("E", "Fuel cayendo: 18.5L → 15.1L → 11.7L → 8.3L → 5.2L. ¿Puedo hacer la última vuelta?",
           ["3.4", "0", "no", "crítico", "entrar"]),
        _p("E", "Con 0L de combustible restantes estimados, ¿cuántas vueltas quedan realmente?",
           ["3.4", "2", "0", "crítico"]),

        # Combined analysis
        _p("A", "Resumen de la serie: ¿qué recomendaciones das para los próximos 5 ticks?",
           ["entrar", "neumaticos", "VST", "atacar", "TYR"]),
    ]


# =============================================================================
# GENERADOR TOTAL Y CONFIG
# =============================================================================

GENERATORS = {
    1: ("Extraccion de campos", generate_level_1),
    2: ("Interpretacion de campos", generate_level_2),
    3: ("Triggers de carrera", generate_level_3),
    4: ("Razonamiento multicampo", generate_level_4),
    5: ("RAG con historico rico", generate_level_5),
    6: ("Multi-trigger y priorizacion", generate_level_6),
    7: ("Edge cases y anomalias", generate_level_7),
    8: ("Series temporales", generate_level_8),
}


def generate_all_prompts() -> dict:
    """Genera todos los prompts."""
    return {
        level: {"name": info[0], "prompts": info[1]()}
        for level, info in GENERATORS.items()
    }


PASS_THRESHOLDS = {
    1: 0.70,  # Reducido de 90% a 70% (más realista)
    2: 0.65,  # Reducido de 85% a 65%
    3: 0.60,  # Reducido de 80% a 60%
    4: 0.55,  # Reducido de 75% a 55%
    5: 0.50,  # Reducido de 70% a 50% (con histórico rico)
    6: 0.45,  # Reducido de 65% a 45%
    7: 0.40,  # Reducido de 60% a 40%
    8: 0.00,  # Sin umbral (ranking abierto)
}


# =============================================================================
# CLIENTE API
# =============================================================================

class LLMClient:
    def __init__(self, base_url: str, model: str, api_key: str = "sk-benchmark"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.client = httpx.Client(timeout=300.0) if httpx else None

    def _chat_url(self) -> str:
        if self.base_url.endswith("/v1") or self.base_url.endswith("/api/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def ask(self, system_prompt: str, user_content: str) -> tuple[str, float, float]:
        if not self.client:
            return ("[httpx not installed]", 0.0, 0.0)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "max_tokens": 15000,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        start_time = time.monotonic()
        try:
            response = self.client.post(self._chat_url(), headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            ttft = (time.monotonic() - start_time) * 1000
            content = data["choices"][0]["message"]["content"]

            # Quick token estimate
            tps = len(content) / (ttft / 1000) if ttft > 0 else 0

            return (content, ttft, tps)
        except Exception as e:
            return (f"[Error: {e}]", 0.0, 0.0)


class Evaluator:
    @staticmethod
    def keyword_score(text: str, keywords: list[str]) -> float:
        text_lower = text.lower()
        matches = sum(1 for kw in keywords if kw.lower() in text_lower)
        return matches / len(keywords) if keywords else 0.5

    @staticmethod
    def evaluate(prompt: dict, response: str) -> dict:
        level = prompt.get("_level", 1)
        kw_score = Evaluator.keyword_score(response, prompt["expected_keywords"])

        rubric = prompt.get("rubric", {})
        rubric_score = 0.0

        if rubric.get("must_prioritize_pit") or rubric.get("must_prioritize_pit_immediate"):
            rubric_score += 0.3 if any(w in response.lower() for w in ["entrar", "ahora", "urgente", "inmediato"]) else 0.0

        if rubric.get("identifies_overheating"):
            rubric_score += 0.3 if any(w in response.lower() for w in ["sobrecalent", "102", "103", "enfriar"]) else 0.0

        total = kw_score * 0.7 + rubric_score * 0.3

        return {
            "score": total,
            "passed": total >= PASS_THRESHOLDS.get(level, 0.0),
            "details": {"keyword_score": kw_score, "rubric_score": rubric_score},
        }


# =============================================================================
# REPORTE
# =============================================================================

def generate_report(all_results: dict, model: str, total_time: float) -> str:
    lines = [
        f"# Benchmark LLM V2: {model}",
        f"",
        f"- **Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **Duracion**: {total_time:.0f}s",
        f"",
        f"## Resultados por Nivel",
        f"",
        f"| Nivel | Nombre | Score | Prompts | Aprobado | TTFT |",
        f"|-------|--------|:-----:|:-------:|:--------:|:----:|",
    ]

    total_prompts = 0
    total_passed = 0
    cumulative_weighted = 0.0

    for level in sorted(all_results.keys()):
        r = all_results[level]
        prompts = r["prompts"]
        n = len(prompts)
        passed = sum(1 for p in prompts if p.get("passed", False))
        avg_score = sum(p.get("score", 0) for p in prompts) / n if n > 0 else 0
        avg_ttft = sum(p.get("ttft_ms", 0) for p in prompts) / n if n > 0 else 0
        threshold = PASS_THRESHOLDS.get(level, 0.0)
        passed_level = avg_score >= threshold

        lines.append(f"| L{level} | {r['name']} | {avg_score*100:.1f}% | {n} | {'✅' if passed_level else '❌'} | {avg_ttft:.0f}ms |")

        total_prompts += n
        total_passed += passed
        cumulative_weighted += avg_score * level

    weighted = cumulative_weighted / sum(range(1, max(all_results.keys()) + 1)) if all_results else 0
    accuracy = total_passed / total_prompts if total_prompts > 0 else 0

    lines += [
        f"",
        f"## Resumen",
        f"",
        f"- **Accuracy real**: {accuracy*100:.1f}% ({total_passed}/{total_prompts})",
        f"- **Score ponderado**: {weighted*100:.1f}%",
        f"",
        f"## Matriz de Aprobacion",
        f"",
    ]

    for level in sorted(all_results.keys()):
        r = all_results[level]
        score = sum(p.get("score", 0) for p in r["prompts"]) / len(r["prompts"])
        threshold = PASS_THRESHOLDS.get(level, 0.0)
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        status = "✅" if score >= threshold else "❌"
        lines.append(f"L{level}: [{bar}] {score*100:.1f}% (min {threshold*100:.0f}%) {status}")

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def run_benchmark(model: str, base_url: str, api_key: str, output_dir: str = "./benchmark_reports") -> dict:
    logger.info("=== Benchmark V2: %s ===", model)

    all_prompts = generate_all_prompts()
    client = LLMClient(base_url, model, api_key)

    all_results: dict[int, dict] = {}
    total_start = time.monotonic()

    for level in sorted(all_prompts.keys()):
        level_info = all_prompts[level]
        level_name = level_info["name"]
        prompts = level_info["prompts"]

        logger.info("--- L%d: %s (%d prompts) ---", level, level_name, len(prompts))

        results = []
        for idx, prompt in enumerate(prompts):
            prompt["_level"] = level

            user_parts = []
            if prompt.get("ticker"):
                user_parts.append(f"### TELEMETRIA ###\n{prompt['ticker']}")
            if prompt.get("rag_context"):
                user_parts.append(f"\n### HISTORICO ###\n{prompt['rag_context']}")
            if prompt.get("trigger"):
                user_parts.append(f"\n### CONTEXTO ###\n{prompt['trigger']}")
            if prompt.get("question"):
                user_parts.append(f"\n### PREGUNTA ###\n{prompt['question']}")

            user_content = "\n".join(user_parts)

            response, ttft, tps = client.ask(SYSTEM_PROMPT, user_content)
            eval_result = Evaluator.evaluate(prompt, response)

            results.append({
                "level": level,
                "index": idx + 1,
                "prompt": prompt["question"][:60],
                "ttft_ms": ttft,
                "tokens_per_second": tps,
                "score": eval_result["score"],
                "passed": eval_result["passed"],
                "response": response[:200],
            })

            logger.info("  [%d/%d] %s: %.0f%%", idx + 1, len(prompts), prompt["question"][:40], eval_result["score"] * 100)

        all_results[level] = {"name": level_name, "prompts": results}

    total_elapsed = time.monotonic() - total_start

    report = generate_report(all_results, model, total_elapsed)

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "_").replace(" ", "_")

    report_path = os.path.join(output_dir, f"{timestamp}_{safe_model}_v2_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    json_path = os.path.join(output_dir, f"{timestamp}_{safe_model}_v2_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    logger.info("=== Completed in %.0fs ===", total_elapsed)
    logger.info("Report: %s", report_path)

    return all_results


def main():
    parser = argparse.ArgumentParser(description="Benchmark LLM V2")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://192.168.1.41:1234/v1")
    parser.add_argument("--api-key", default="sk-benchmark")
    parser.add_argument("--output-dir", default="./benchmark_reports")
    args = parser.parse_args()

    run_benchmark(args.model, args.base_url, args.api_key, args.output_dir)


if __name__ == "__main__":
    main()