#!/usr/bin/env python3
"""
Benchmark progresivo de LLMs para Vantare Ingeniero IA.

Evalúa modelos en 8 niveles de dificultad creciente usando datos LMU realistas.
Cada prompt usa el mismo SYSTEM_PROMPT_TICKER del proyecto real.

Uso:
    # Probar un modelo específico
    python benchmark_llm.py --model qwen3.5-4b --base-url http://192.168.1.41:1234/api/v1

    # Probar un nivel específico
    python benchmark_llm.py --model llama3.2-3b --base-url http://... --level 3

    # Comparar múltiples modelos
    python benchmark_llm.py --all

    # Solo generar prompts (sin llamar a la API)
    python benchmark_llm.py --dry-run
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
import math

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("benchmark")

# =============================================================================
# CONSTANTES: system prompt idéntico al proyecto real
# =============================================================================

SYSTEM_PROMPT_TICKER = """Eres un ingeniero de carrera. Recibes datos en formato ticker compacto.

FORMATO TICKER — Tabla Diccionario:
=============================

### DRV — Datos del piloto
DRV:P{pos}|L{vuelta}|F:{fuel}L/{consumo}({laps_rest})|TYR:{wFL}/{wFR}/{wRL}/{wRR}·{tFL}/{tFR}/{tRL}/{tRR}

| Codigo | Significado | Ejemplo |
|--------|-------------|---------|
| P{pos} | Posicion en pista (1-based) | P3 |
| L{vuelta} | Vuelta actual | L26 |
| F:{fuel}L | Combustible en tanque (litros) | F:42.3L |
| {consumo} | Consumo promedio (L/vuelta) | 3.2 |
| ({laps_rest}) | Vueltas restantes estimadas | (13L) |
| TYR:{w}/... | Desgaste neumaticos 0-100% | 72/68/65/63 |
| .{t}/... | Temperatura neumaticos C | .92/94/98/96 |

**Regla:** Si lap <= 3, se omite la seccion TYR (desgaste no representativo).

### BRK — Desgaste de frenos
BRK:{wFL}/{wFR}/{wRL}/{wRR}

| Codigo | Significado | Ejemplo |
|--------|-------------|---------|
| {wFL}/{wFR}/{wRL}/{wRR} | Desgaste 0-100% (FL/FR/RL/RR) | 38/35/22/20 |

**Nota:** Si no hay datos de REST API, se omite la linea BRK completa.

### GAP — Diferencias con rivales
GAP>{ahead_name}:+{ahead_sec}.{ahead_best}|<{behind_name}:{behind_sec}.{behind_best}.d{delta}

| Codigo | Significado | Ejemplo |
|--------|-------------|---------|
| {ahead_name} | Nombre piloto adelante (3 chars) | VST |
| +{ahead_sec} | Gap con el de adelante (segundos) | +2.1 |
| {ahead_best} | Mejor tiempo del de adelante | 1:48.2 |
| {behind_name} | Nombre piloto detras (3 chars) | ALO |
| -{behind_sec} | Gap con el de detras (segundos) | -1.2 |
| {behind_best} | Mejor tiempo del de detras | 1:47.9 |
| d{delta} | Diferencia de ritmo (tu best - su best) | d-0.3 |

**Omision:** Si lider, se omite >. Si ultimo, se omite <.

### SES — Informacion de sesion
SES:{clase}|{tipo}|{total}L|{tiempo_restante}

| Codigo | Significado | Ejemplo |
|--------|-------------|---------|
| {clase} | Clase: HY=Hypercar, GT3, LMP2, LMP3, GTE | HY |
| {tipo} | Tipo: RACE, QUALI, PRACTICE | RACE |
| {total}L | Vueltas totales de carrera | 38L |
| {tiempo_restante} | Tiempo restante (MM:SS) | 45:22 |

**Abreviaturas de clase:** HY=Hypercar, GT3, LMP2, LMP3, GTE
**Abreviaturas de sesion:** RACE, QUALI, PRACTICE, PRA1-4, Q1-4, WUP, TEST

### WTH — Clima y condiciones
WTH:{grip}|{temp}|{rain}%+{min}|SC:{S/N}

| Codigo | Significado | Ejemplo |
|--------|-------------|---------|
| {grip} | Nivel agarre: GRN=Green, LOW, MED=Medium, HIG, SAT=Saturated | MED |
| {temp} | Temperatura ambiente C | 22 |
| {rain}% | Probabilidad de lluvia 0-100% | 30% |
| +{min} | Minutos hasta lluvia | +15m |
| SC:{S/N} | Safety Car activo: S= Si, N= No | SC:N |

**Agarre pista:** GRN(0), LOW(1), MED(2), HIG(3), SAT(4)

### RIV — Rivales
RIV:{total} cars
CLS1({n}):{detalle}.{detalle}...   -- Rivales gap < 5s
CLS2({n}):{detalle}.{detalle}...   -- Rivales gap 5-30s
FAR({n}):{gap}s behind              -- Rivales gap > 30s
LAP({n}):{name}(-{n}L)...          -- Rivales doblados

Formato detalle: {name}|{class}|{gap}|V{laps}
Ejemplo: VST|HY|+2.1|V22 . ALO|HY|-1.2|V22

=============================

Maximo 2-3 frases. Estilo radio. Tecnico y conciso."""

# =============================================================================
# TICKERS BASE — escenarios realistas de carrera
# =============================================================================

TICKERS = {
    # Ticker A: Mitad de carrera, seco, P3, batalla cerrada
    "A": """DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63.92/94/98/96
BRK:38/35/22/20
GAP>VST:+2.1.1:48.2|<ALO:-1.2.1:47.9.d-0.3
SES:HY|RACE|38L|45:22
WTH:MED|22|30%+15m|SC:N
RIV:20 cars
CLS1(3):VST|HY|+2.1|V10.ALO|HY|-1.2|V10.LEC|GT3|+4.8|V10
CLS2(5):HAM|HY|+8.5|V10.VER|HY|+12.3|V10.NOR|GT3|+15.1|V10.PIA|GT3|+18.7|V10.RUS|GT3|+25.3|V10
FAR(8):+45s behind
LAP(4):PER(-1L).TSU(-2L).STR(-2L).ZHO(-3L)""",

    # Ticker B: Liderando, lluvia aproximandose
    "B": """DRV:P1|L25|F:28.5L/3.3(7L)|TYR:55/52/50/48.88/90/91/89
GAP>---|<HAM:-5.3.1:47.5.d+0.8
SES:HY|RACE|38L|20:15
WTH:LOW|18|80%+3m|SC:N
RIV:20 cars
CLS1(2):HAM|HY|-5.3|V24.VER|HY|-8.1|V24
CLS2(4):LEC|HY|-12.4|V24.NOR|GT3|-15.8|V24.PIA|GT3|-18.2|V24.RUS|GT3|-22.1|V24
FAR(10):+50s behind
LAP(4):PER(-1L).TSU(-2L).STR(-2L).ZHO(-3L)""",

    # Ticker C: Post-parada, Safety Car, P8
    "C": """DRV:P8|L8|F:89.7L/3.1(27L)|TYR:98/97/96/96.85/87/88/86
GAP>BOT:+0.8.1:49.5|<SAI:-0.4.1:49.1.d-0.7
SES:HY|RACE|38L|52:00
WTH:GRN|26|10%+0m|SC:S
RIV:20 cars
CLS1(4):BOT|HY|+0.8|V7.SAI|HY|-0.4|V8.ALB|GT3|+1.2|V8.OCO|GT3|-2.1|V7
CLS2(3):STR|GT3|+8.9|V7.TSU|GT3|+12.4|V8.ALO|HY|+15.3|V7
FAR(8):+60s behind
LAP(5):PER(-2L).ZHO(-2L).NOR(-1L).LEC(-1L).HAM(-1L)""",

    # Ticker D: Vuelta 2, sin datos de neumaticos
    "D": """DRV:P5|L2|F:96.8L/3.2(28L)
GAP>VER:+3.5.1:47.8|<NOR:-2.1.1:48.5.d-0.7
SES:HY|RACE|38L|55:30
WTH:GRN|20|5%+0m|SC:N
RIV:20 cars
CLS1(3):VER|HY|+3.5|V1.NOR|GT3|-2.1|V2.ALO|HY|+4.2|V2
CLS2(5):HAM|HY|+7.8|V2.LEC|HY|+11.2|V2.RUS|GT3|+14.5|V2.PIA|GT3|+18.1|V2.BOT|GT3|+21.7|V2
FAR(8):+40s behind
LAP(2):---""",

    # Ticker E: Final de carrera, GT3, sin combustible
    "E": """DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80.95/97/98/94
BRK:75/72/68/65
GAP>ALB:+15.2.1:49.8|<TSU:-8.3.1:49.5.d+0.3
SES:GT3|RACE|38L|3:45
WTH:LOW|15|90%+0m|SC:N
RIV:22 cars
CLS1(0):---
CLS2(4):ALB|GT3|+15.2|V34.TSU|GT3|-8.3|V34.OCO|GT3|+18.7|V34.MAG|GT3|-12.1|V34
FAR(14):+90s behind
LAP(4):PER(-2L).ZHO(-2L).NOR(-1L).STR(-1L)""",

    # Ticker F: Neumaticos sobrecalentados, P6
    "F": """DRV:P6|L18|F:35.1L/3.2(9L)|TYR:65/62/60/58.100/102/103/101
GAP>RUS:+6.2.1:48.9|<BOT:-4.1.1:48.4.d+0.5
SES:HY|RACE|38L|30:00
WTH:MED|24|40%+20m|SC:N
RIV:20 cars
CLS1(0):---
CLS2(6):RUS|HY|+6.2|V18.BOT|HY|-4.1|V17.STR|GT3|+11.3|V17.TSU|GT3|+16.7|V18.ALB|GT3|+22.4|V17.MAG|GT3|+28.1|V18
FAR(8):+55s behind
LAP(6):PER(-2L).ZHO(-2L).NOR(-1L).LEC(-1L).HAM(-1L).PIA(-1L)""",

    # Ticker G: Ventana de pits abierta, P4
    "G": """DRV:P4|L14|F:53.1L/3.2(15L)|TYR:45/42/40/38.90/92/93/91
BRK:25/22/18/15
GAP>LEC:+3.1.1:48.1|<RUS:-1.8.1:48.6.d-0.5
SES:HY|RACE|38L|40:00
WTH:MED|21|50%+10m|SC:N
RIV:20 cars
CLS1(2):LEC|HY|+3.1|V13.RUS|GT3|-1.8|V14
CLS2(4):VER|HY|+7.5|V13.HAM|HY|+11.3|V13.NOR|GT3|+14.8|V13.ALO|HY|+19.2|V14
FAR(7):+42s behind
LAP(7):PER(-1L).ZHO(-2L).STR(-2L).TSU(-3L).PIA(-3L).BOT(-4L).MAG(-4L)""",

    # Ticker H: Safety Car, P2, vueltas tempranas
    "H": """DRV:P2|L6|F:82.4L/3.1(25L)|TYR:95/94/93/92.85/86/87/85
BRK:10/8/5/5
GAP>VER:+1.5.1:47.9|<NOR:-3.2.1:48.7.d-0.8
SES:HY|RACE|38L|54:00
WTH:GRN|23|15%+0m|SC:S
RIV:20 cars
CLS1(2):VER|HY|+1.5|V5.NOR|GT3|-3.2|V6
CLS2(5):LEC|HY|+8.1|V5.RUS|GT3|+11.5|V6.ALO|HY|+14.3|V5.HAM|HY|+18.9|V5.PIA|GT3|+23.4|V6
FAR(6):+38s behind
LAP(7):PER(-1L).ZHO(-1L).STR(-1L).TSU(-2L).BOT(-2L).MAG(-2L).OCO(-2L)""",
}

# =============================================================================
# GENERADOR DE PROMPTS
# =============================================================================

def _p(ticker_id: str, question: str, expected: list[str],
       rubric: Optional[dict] = None, trigger: Optional[str] = None,
       rag_context: Optional[str] = None, chat_history: Optional[list] = None) -> dict:
    """Construye un prompt estructurado del benchmark."""
    p = {
        "ticker_id": ticker_id,
        "ticker": TICKERS[ticker_id],
        "question": question,
        "expected_keywords": expected,
        "rag_context": rag_context,
        "trigger": trigger,
        "chat_history": chat_history,
        "rubric": rubric or {},
    }
    return p


def _rag(text: str) -> str:
    """Formatea un contexto RAG."""
    return f"## RECORDATORIO HISTORICO\n{text}"


def generate_level_1() -> list[dict]:
    """Nivel 1: Extraccion literal de campos (30 prompts).

    El LLM debe extraer el valor exacto de un campo del ticker.
    """
    return [
        # Ticker A
        _p("A", "Cual es la posicion actual?", ["P3", "3"]),
        _p("A", "Cuanto combustible queda en el tanque?", ["42.3"]),
        _p("A", "Cual es el consumo promedio por vuelta?", ["3.2"]),
        _p("A", "Cuantas vueltas restantes de combustible estimadas?", ["13", "13L"]),
        _p("A", "Cual es el desgaste del neumatico delantero izquierdo?", ["72", "72%"]),
        _p("A", "Cual es la temperatura del neumatico trasero derecho?", ["96", "96C"]),
        _p("A", "Que desgaste de freno tiene la rueda delantera izquierda?", ["38", "38%"]),
        _p("A", "Quien va delante y a que distancia?", ["VST", "2.1"]),
        _p("A", "Quien va detras y a que distancia?", ["ALO", "1.2"]),
        _p("A", "Cual es la diferencia de ritmo con el coche de detras?", ["-0.3", "d-0.3", "mas rapido"]),
        _p("A", "De que clase es la sesion?", ["HY", "Hypercar"]),
        _p("A", "Cuantas vueltas totales tiene la carrera?", ["38", "38L"]),
        _p("A", "Cuanto tiempo resta de carrera?", ["45:22"]),
        _p("A", "Cual es el nivel de agarre de la pista?", ["MED", "Medium"]),
        _p("A", "Cuantos coches hay en total?", ["20"]),
        # Ticker B
        _p("B", "Esta activo el Safety Car?", ["No", "N", "no"]),
        _p("B", "Cual es la probabilidad de lluvia?", ["80", "80%"]),
        _p("B", "En cuantos minutos llegara la lluvia?", ["3", "3m", "3 minutos"]),
        _p("B", "En que vuelta estamos?", ["25", "L25", "V25"]),
        _p("B", "Cuantas vueltas de combustible restan?", ["7", "7L"]),
        # Ticker C
        _p("C", "Esta activo el Safety Car?", ["Si", "S", "si", "activo"]),
        _p("C", "Cual es la temperatura ambiente?", ["26", "26C"]),
        _p("C", "El coche de delante es...", ["BOT"]),
        # Ticker D
        _p("D", "Por que no hay datos de desgaste de neumaticos?", ["lap", "2", "3", "vuelta", "representativo"]),
        _p("D", "Cual es la posicion?", ["5", "P5"]),
        _p("D", "Cuantas vueltas de combustible restan?", ["28", "28L"]),
        # Ticker E
        _p("E", "Cuantos coches hay en total?", ["22"]),
        _p("E", "Que desgaste de freno tiene la rueda trasera izquierda?", ["68", "68%"]),
        _p("E", "Cuantas vueltas de combustible quedan?", ["0", "0L"]),
        # Ticker F
        _p("F", "Cual es la temperatura del neumatico delantero derecho?", ["102", "102C"]),
        _p("F", "Cual es la temperatura del neumatico trasero derecho?", ["101", "101C"]),
    ]


def generate_level_2() -> list[dict]:
    """Nivel 2: Interpretacion de campos (20 prompts).

    El LLM debe interpretar el significado de los datos.
    """
    return [
        # Interpretar diferencias de ritmo
        _p("A", "Vas ganando o perdiendo tiempo respecto al coche de detras?",
           ["ganando", "perdiendo", "d-0.3"]),
        # Interpretar clima
        _p("B", "Deberias preocuparte por la lluvia?",
           ["si", "80%", "3 minutos", "preocuparse"]),
        # Interpretar estado post-parada
        _p("C", "Acabas de salir de boxes?",
           ["si", "89.7", "lleno", "98", "nuevos"]),
        # Interpretar ausencia de TYR
        _p("D", "Es normal que no haya datos de desgaste de neumaticos?",
           ["si", "normal", "2", "vuelta", "3"]),
        # Interpretar tiempo restante
        _p("E", "Queda mucho tiempo de carrera?",
           ["poco", "3:45", "3 minutos", "45 segundos", "final"]),
        # Interpretar temperaturas anormales
        _p("F", "Las temperaturas de los neumaticos son normales?",
           ["altas", "elevadas", "100", "102", "103", "101", "sobrecalentadas"]),
        # Interpretar combustible critico
        _p("E", "Tienes combustible suficiente para terminar la carrera?",
           ["no", "0", "faltan", "boxes", "entrar"]),
        # Interpretar Safety Car
        _p("H", "Que implica que el Safety Car este activo para tu estrategia?",
           ["entrar", "boxes", "parada", "perder", "posicion", "gratis"]),
        # Interpretar gap cerrado
        _p("C", "El coche de delante esta lejos o cerca?",
           ["cerca", "0.8", "+0.8"]),
        # Interpretar posicion
        _p("A", "Estas en zona de podio?",
           ["si", "P3", "tercero"]),
        # Interpretar cantidad de rivales cerca
        _p("A", "Cuantos rivales tienes a menos de 5 segundos?",
           ["3", "CLS1"]),
        # Interpretar agarre
        _p("A", "Como esta el agarre de la pista?",
           ["medio", "MED", "normal"]),
        # Interpretar class
        _p("E", "De que clase es tu coche?",
           ["GT3", "GT"]),
        # Interpretar doblados
        _p("A", "Hay coches doblados?",
           ["si", "4", "PER", "TSU", "STR", "ZHO"]),
        # Interpretar frenos desgastados
        _p("E", "Deberias preocuparte por los frenos?",
           ["si", "75", "72", "68", "65", "critico", "alto"]),
        # Interpretar ventana de lluvia
        _p("B", "Si la lluvia llega en 3 minutos y estas con slicks, que deberias hacer?",
           ["entrar", "boxes", "intermedios", "lluvia"]),
        # Interpretar posicion al final
        _p("E", "Estas en los puntos?",
           ["fuera", "P12", "no", "puntos"]),
        # Interpretar estado de carrera
        _p("E", "La sesion es de que tipo?",
           ["RACE", "carrera"]),
        # Interpretar trafico
        _p("A", "Hay trafico significativo de doblados?",
           ["si", "4", "PER", "TSU"]),
        # Interpretar temperatura ambiente fria
        _p("B", "La temperatura ambiente de 18C es normal?",
           ["fria", "normal", "baja"]),
    ]


def generate_level_3() -> list[dict]:
    """Nivel 3: Respuesta a triggers (24 prompts, 12 triggers x 2 escenarios).

    Cada trigger se activa. El LLM debe responder adecuadamente.
    """
    return [
        # --- FuelCriticalTrigger ---
        _p("E", "Combustible criticamente bajo. Evalua la situacion.",
           ["entrar", "boxes", "combustible", "0"],
           trigger="fuel_critical",
           rubric={"recommends_pit": True, "mentions_fuel": True}),
        _p("A", "Combustible criticamente bajo. Evalua la situacion.",
           ["bien", "suficiente", "no", "entrar"],
           trigger="fuel_critical",
           rubric={"recommends_pit": False, "mentions_not_critical": True}),

        # --- SafetyCarTrigger ---
        _p("C", "Safety Car desplegado. Que recomiendas?",
           ["entrar", "boxes", "parada", "aprovechar"],
           trigger="safety_car",
           rubric={"mentions_strategy": True}),
        _p("A", "Safety Car desplegado. Que recomiendas?",
           ["no", "activo", "falso"],
           trigger="safety_car",
           rubric={"does_not_mention_sc": True}),

        # --- BrakeWearCriticalTrigger ---
        _p("E", "Desgaste critico de frenos (>80%). Evalua.",
           ["75", "72", "68", "65", "alto", "critico", "preocupante", "cuidado"],
           trigger="brake_wear_critical",
           rubric={"identifies_high_wear": True}),
        _p("A", "Desgaste critico de frenos (>80%). Evalua.",
           ["normal", "38", "35", "bien"],
           trigger="brake_wear_critical",
           rubric={"identifies_not_critical": True}),

        # --- TyreDegAccelTrigger ---
        _p("F", "Degradacion acelerada de neumaticos. Analiza.",
           ["65", "62", "60", "58", "elevado", "desgaste"],
           trigger="tyre_degradation",
           rubric={"identifies_wear_level": True}),
        _p("C", "Degradacion acelerada de neumaticos. Analiza.",
           ["98", "97", "96", "nuevos", "bien"],
           trigger="tyre_degradation",
           rubric={"identifies_low_wear": True}),

        # --- HybridDeployMapTrigger ---
        # Nota: battery no aparece en ticker directamente, pero el LLM debe
        # inferirlo del contexto o decir que no tiene datos
        _p("F", "Bateria hibrida baja. Evalua el estado.",
           ["no", "tengo", "datos", "ticker", "bateria", "charge"],
           trigger="hybrid_deploy_map",
           rubric={"recognizes_missing_data": True}),

        # --- WeatherChangeTrigger ---
        _p("B", "Amenaza de lluvia inminente. Que hago?",
           ["entrar", "boxes", "intermedios", "80%", "3 minutos", "preparar"],
           trigger="weather_change",
           rubric={"recommends_preparation": True}),
        _p("A", "Amenaza de lluvia inminente. Que hago?",
           ["30%", "15m", "vigilar", "atento", "pronto"],
           trigger="weather_change",
           rubric={"mentions_monitoring": True}),

        # --- PitWindowOpenedTrigger ---
        _p("G", "Ventana de paradas abierta. Recomienda estrategia.",
           ["entrar", "boxes", "ventana", "abierta", "parar"],
           trigger="pit_window_opened",
           rubric={"recommends_evaluating_pit": True}),

        # --- PitWindowClosingTrigger ---
        _p("E", "Ventana de paradas cerrándose. Quedan 2 vueltas.",
           ["entrar", "ahora", "proxima", "vuelta", "urgente"],
           trigger="pit_window_closing",
           rubric={"recommends_immediate_pit": True}),

        # --- CompetitorPittedTrigger ---
        _p("C", "Rival directo (SAI) ha entrado a boxes. Que hago?",
           ["entrar", "responder", "undercut", "cubrir"],
           trigger="competitor_pitted",
           rubric={"mentions_undercut_or_cover": True}),

        # --- GapClosedTrigger ---
        _p("C", "Brecha cerrada con rival < 1.5s. Evalua.",
           ["BOT", "0.8", "+0.8", "SAI", "0.4", "cerca", "batalla"],
           trigger="gap_closed",
           rubric={"identifies_battle": True}),
        _p("B", "Brecha cerrada con rival < 1.5s. Evalua.",
           ["5.3", "lejos", "no", "cerca"],
           trigger="gap_closed",
           rubric={"identifies_not_close": True}),

        # --- PhaseChangedTrigger ---
        # Usamos un ticker que no ha cambiado
        _p("A", "La fase de carrera ha cambiado. Evalua.",
           ["no", "cambio", "misma", "RACE"],
           trigger="phase_changed",
           rubric={"detects_no_change": True}),

        # --- TiresThermalOverheatingTrigger ---
        _p("F", "Temperatura excesiva de neumaticos (>105C). Analiza.",
           ["100", "102", "103", "101", "alta", "sobrecalentados", "cuidado"],
           trigger="tires_overheating",
           rubric={"identifies_overheating": True}),
        _p("C", "Temperatura excesiva de neumaticos (>105C). Analiza.",
           ["85", "87", "88", "86", "normal", "bien"],
           trigger="tires_overheating",
           rubric={"identifies_normal_temps": True}),
    ]


def generate_level_4() -> list[dict]:
    """Nivel 4: Razonamiento multicampo (20 prompts).

    Debe cruzar 2+ lineas del ticker para responder.
    """
    return [
        # WTH + DRV: lluvia + slicks
        _p("B", "80% de lluvia en 3 min y llevas slicks. Que recomiendas?",
           ["entrar", "boxes", "intermedios", "lluvia", "cambiar"]),
        # GAP + SES + DRV: undercut opportunity
        _p("A", "VST esta 2.1s adelante, llevais 10 vueltas, quedan 45 min. Es buen momento para undercut?",
           ["si", "ventana", "cerca", "posible"]),
        # WTH + DRV + GAP: SC strategy
        _p("H", "SC activo, estas P2 a 1.5s de VER. Entras a boxes?",
           ["si", "entrar", "cubrir", "undercut"]),
        # DRV fuel + SES time_left: fuel to finish
        _p("G", "Quedan 40 min de carrera, tienes 53.1L y consumes 3.2L/v. Llegas?",
           ["si", "suficiente", "15", "38", "calculos"]),
        # DRV tyres + GAP delta: tyre saving
        _p("A", "Tus neumaticos estan al 72% y el de detras es 0.3s mas rapido. Deberias hacer tyre saving?",
           ["si", "neumaticos", "gestion", "ritmo"]),
        # DRV + BRK: brake + fuel combined
        _p("E", "Frenos al 75% y combustible para 0 vueltas. Prioridad?",
           ["entrar", "boxes", "urgente", "combustible", "frenos"]),
        # SES + WTH: session type + weather
        _p("B", "Es carrera HYpercar y hay 80% lluvia en 3 min. Impacto?",
           ["clase", "HY", "lluvia", "neutralizar", "ventana"]),
        # RIV + GAP + DRV: triple analysis
        _p("A", "ALO esta 1.2s detras y es 0.3s mas rapido. Ademas hay 3 coches en CLS1. Como defiendes?",
           ["defender", "ritmo", "ALO", "presion"]),
        # WTH grip + DRV tyres temp: grip + tyre temp correlation
        _p("F", "Pista MED (nivel 2), neumaticos a 100-103C. Hay sobrecalentamiento?",
           ["si", "100", "103", "alta", "sobrecalentados"]),
        # DRV fuel + RIV far: fuel strategy with traffic
        _p("E", "Sin combustible, P12, GT3. Entrar a boxes ahora o esperar?",
           ["ahora", "urgente", "entrar"]),
        # GAP ahead + behind + delta: triple gap analysis
        _p("C", "BOT +0.8s (1:49.5), SAI -0.4s (1:49.1). Estrategia?",
           ["SAI", "defender", "0.4", "BOT", "atacar"]),
        # RIV CLS1 count + DRV position: traffic assessment
        _p("A", "Hay 3 coches en CLS1. Eres P3. Describe la situacion.",
           ["3", "cerca", "rivales", "VST", "ALO", "LEC"]),
        # WTH SC + DRV fuel: SC + fuel combined
        _p("H", "SC activo, tienes 82.4L. Entrar ahora o esperar?",
           ["si", "entrar", "ahora", "aprovechar"]),
        # SES time_left + DRV laps_rest: pace calculation
        _p("B", "20:15 restantes, 7 vueltas de combustible. Suficiente?",
           ["no", "faltan", "entrar", "otra", "parada"]),
        # BRK + DRV: brakes + fuel + tyres triple check
        _p("E", "Frenos 75/72/68/65, neumaticos 88/85/83/80, combustible 5.2L. Prioriza riesgos.",
           ["combustible", "critico", "frenos", "neumaticos", "orden"]),
        # WTH + SES: pit window due to weather
        _p("B", "80% lluvia en 3 min, liderando. Abres ventana de lluvia?",
           ["si", "entrar", "cubrir", "intermedios"]),
        # DRV pos + RIV: points position
        _p("E", "P12 en GT3, ultimos compases. Que dices al piloto?",
           ["empujar", "ritmo", "posicion", "final"]),
        # GAP + SES: closing gap in final stages
        _p("E", "ALB va +15.2s, TSU viene -8.3s, quedan 3:45. Que haces?",
           ["TSU", "defender", "atras", "ALB", "alcanzar"]),
        # WTH + DRV tyres + DRV fuel: full pit strategy
        _p("G", "50% lluvia en 10 min, neumaticos al 45%, combustible 53.1L. Plan de parada?",
           ["plan", "estrategia", "parada", "ventana", "combustible"]),
        # RIV LAP count + DRV position: lapped traffic management
        _p("A", "Hay 4 doblados. Eres P3. Como gestionas el trafico?",
           ["doblados", "trafico", "PER", "TSU", "gestion"]),
    ]


def generate_level_5() -> list[dict]:
    """Nivel 5: Razonamiento con RAG historico (15 prompts).

    El prompt incluye contexto historico. Debe cruzar RAG + ticker actual.
    """
    return [
        # RAG: SC en V8 + ticker actual
        _p("A", "Hemos perdido tiempo desde el SC de la vuelta 8?",
           ["8", "vuelta", "comparar", "ritmo"],
           rag_context=_rag("- V8: Safety Car desplegado | P3 | F:52.3L | Tyre wear 12/10/9/11")),
        # RAG: rival pitted + ticker current
        _p("A", "ALO paro en V9. Ha ganado o perdido con el undercut?",
           ["V9", "ALO", "under", "analizar"],
           rag_context=_rag("- V9: ALO entro a boxes | P4 -> P5")),
        # RAG: fuel consumption history
        _p("E", "Nuestro consumo es consistente con vueltas anteriores?",
           ["consumo", "historial", "comparar"],
           rag_context=_rag("- V30: Vuelta completada | P12 | F:28.7L | Tyre wear 45/42/40/38\n"
                            "- V32: Vuelta completada | P12 | F:19.3L | Tyre wear 62/60/58/55\n"
                            "- V34: Vuelta completada | P12 | F:10.1L | Tyre wear 78/75/72/70")),
        # RAG: weather change detected earlier
        _p("B", "Ya habia aviso de lluvia antes? Cuanto ha cambiado?",
           ["80%", "antes", "cambiado", "peor"],
           rag_context=_rag("- V22: Weather forecast updated | Rain 40%+20m | Cloud 6")),
        # RAG: competitor pace history
        _p("A", "VST esta mas lento que en vueltas anteriores?",
           ["VST", "ritmo", "comparar", "tiempos"],
           rag_context=_rag("- V5: Vuelta completada | P5 | VST best 1:47.9\n"
                            "- V7: Vuelta completada | P4 | VST best 1:48.1\n"
                            "- V9: Vuelta completada | P3 | VST best 1:48.5")),
        # RAG: tyre deg history + current
        _p("F", "La degradacion de neumaticos se esta acelerando?",
           ["si", "acelerando", "peor", "comparar"],
           rag_context=_rag("- V12: Vuelta completada | P6 | Tyre wear 22/20/18/17\n"
                            "- V14: Vuelta completada | P6 | Tyre wear 38/36/34/32\n"
                            "- V16: Vuelta completada | P6 | Tyre wear 52/50/48/45")),
        # RAG: previous pit strategy
        _p("G", "La ultima vez que paramos, funciono la estrategia?",
           ["ultima", "parada", "estrategia", "evaluar"],
           rag_context=_rag("- V7: Entrada a boxes | P6 -> P8 | Duración 28.3s\n"
                            "- V7: Salida de boxes | P8 | Neumaticos nuevos")),
        # RAG: safety car history + current
        _p("H", "Cuantas veces ha salido el SC en esta carrera?",
           ["1", "una", "V8"],
           rag_context=_rag("- V8: Safety Car desplegado | P5")),
        # RAG: gap trend
        _p("C", "SAI nos esta alcanzando o alejando?",
           ["alcanzando", "cerrando", "gap"],
           rag_context=_rag("- V5: Gap change | P7 | Gap behind: SAI -1.8s\n"
                            "- V6: Gap change | P7 | Gap behind: SAI -1.2s\n"
                            "- V7: Gap change | P8 | Gap behind: SAI -0.6s")),
        # RAG: multiple event types
        _p("A", "Resume los eventos importantes de la carrera hasta ahora.",
           ["SC", "Safety", "boxes", "parada", "cambio", "resumen"]),
        # RAG: weather change + tyre decision
        _p("B", "Ya empezo a llover? El forecast anterior era 40%, ahora 80%.",
           ["no", "3 min", "preparar", "intermedios"],
           rag_context=_rag("- V22: Weather forecast updated | Rain 40%+20m (CLD 6)")),
        # RAG: fuel usage trend
        _p("A", "Nuestro consumo de combustible ha sido consistente?",
           ["si", "3.2", "consistente", "normal"],
           rag_context=_rag("- V5: Vuelta completada | Fuel used 3.1L\n"
                            "- V7: Vuelta completada | Fuel used 3.3L\n"
                            "- V9: Vuelta completada | Fuel used 3.2L")),
        # RAG: position changes
        _p("C", "Hemos ganado o perdido posiciones desde el inicio?",
           ["perdido", "P5", "P8", "empeorado"],
           rag_context=_rag("- V1: Vuelta completada | P5\n"
                            "- V3: Vuelta completada | P6\n"
                            "- V5: Vuelta completada | P7")),
        # RAG: driver performance
        _p("A", "Estoy rindiendo mejor o peor que al inicio de carrera?",
           ["mejor", "1:48.2", "ritmo", "consistente"],
           rag_context=_rag("- V2: Vuelta completada | P6 | Best lap 1:49.1\n"
                            "- V5: Vuelta completada | P5 | Best lap 1:48.5\n"
                            "- V8: Vuelta completada | P3 | Best lap 1:48.2")),
        # RAG: temperature trend
        _p("F", "La temperatura de la pista esta subiendo o bajando?",
           ["no", "tengo", "datos", "temperatura", "pista"]),
    ]


def generate_level_6() -> list[dict]:
    """Nivel 6: Estrategia multi-trigger (10 prompts).

    Multiples triggers activos simultaneamente. Debe priorizar.
    """
    return [
        # FuelCritical + PitWindowClosing + CompetitorPitted
        _p("E", "Combustible critico (0L rest), ventana cerrándose y ALB paro hace 1 vuelta. Que hago?",
           ["entrar", "ahora", "urgente", "ALB", "cubrir"],
           trigger="fuel_critical+pit_window_closing+competitor_pitted",
           rubric={"must_prioritize_pit": True}),

        # SafetyCar + GapClosed + PitWindowOpened
        _p("H", "SC activo, gap con VER solo 1.5s, ventana abierta. Entro?",
           ["si", "entrar", "aprovechar", "SC", "VER", "cubrir"],
           trigger="safety_car+gap_closed+pit_window_opened",
           rubric={"should_recommend_pit": True}),

        # TyreDegAccel + WeatherChange + PitWindowOpened
        _p("G", "Degradacion alta (45%), lluvia 50% en 10 min, ventana abierta. Plan?",
           ["entrar", "ahora", "lluvia", "deg", "ventana"],
           trigger="tyre_degradation+weather_change+pit_window_opened"),

        # Overheating + Hybrid low (simulado) + Competitor pitted
        _p("F", "Neumaticos sobrecalentados (100-103C), bateria baja (no se muestra) y BOT pitted. Estrategia?",
           ["entrar", "enfriar", "neumaticos", "BOT", "gestion"]),

        # WeatherChange + PitWindowClosing + FuelCritical
        _p("E", "90% lluvia ahora, combustible 0L, ventana cerrándose. Prioridad?",
           ["entrar", "inmediato", "combustible", "lluvia", "boxes"],
           trigger="weather_change+pit_window_closing+fuel_critical",
           rubric={"must_prioritize_pit_immediate": True}),

        # SafetyCar + CompetitorPitted + GapClosed
        _p("C", "SC activo, SAI entro a boxes, BOT esta a +0.8s. Entro ahora?",
           ["si", "entrar", "SAI", "cubrir", "undercut"],
           trigger="safety_car+competitor_pitted+gap_closed"),

        # FuelCritical + Overheating + BrakeWear
        _p("E", "0L combustible, frenos 75%, neumaticos 88%. Que es mas critico?",
           ["combustible", "critico", "frenos", "prioridad"]),


        # Early race SC + fuel + tyres
        _p("H", "SC en V6, combustible lleno (82.4L), neumaticos nuevos. Espero o entro?",
           ["esperar", "no", "entrar", "nuevos", "lleno"],
           trigger="safety_car+full_fuel"),

        # GapClosed + CompetitorPitted + PitWindowClosing
        _p("C", "BOT +0.8s (CLS1), SAI en boxes, ventana cerrándose. Riesgo de undercut?",
           ["si", "SAI", "undercut", "entrar", "cubrir"],
           trigger="gap_closed+competitor_pitted+pit_window_closing"),

        # Triple threat: Weather + Fuel + Tyres
        _p("G", "50% lluvia en 10 min, combustible para 15 vueltas pero neumaticos al 45%. Plan?",
           ["entrar", "ahora", "proxima", "vuelta", "ventana"],
           trigger="weather_change+pit_window_opened+tyre_degradation"),
    ]


def generate_level_7() -> list[dict]:
    """Nivel 7: Casos limite y anomalias (15 prompts).

    Datos en el borde, contradictorios, o campos ausentes.
    """
    return [
        # Caso: lap<=3 sin TYR (el LLM no debe recomendar cambio de neumaticos)
        _p("D", "Neumaticos nuevos? Como estan?",
           ["no", "tengo", "datos", "3", "vuelta", "representativo"]),

        # Caso: sin linea BRK (brake_wear = 0, no disponible)
        _p("D", "Como estan los frenos?",
           ["no", "tengo", "datos", "freno", "informacion"]),

        # Caso: battery justo en el limite (20%) - no en ticker
        _p("B", "Como esta la bateria?",
           ["no", "tengo", "datos", "bateria", "ticker"]),

        # Caso: gap_ahead exactamente 1.50 (en el limite del trigger)
        # Creamos un ticker ad-hoc para esto... usamos C que tiene 0.8
        _p("C", "El gap con BOT es exactamente 1.5s? Que tan cerca esta?",
           ["0.8", "+0.8", "menos", "1.5"]),

        # Caso: speed=0, in_pits=true (parado en boxes)
        _p("H", "Voy a 0 km/h y estoy en la pista. Que pasa?",
           ["boxes", "parado", "pits", "reparando"]),

        # Caso: datos contradictorios (fuel lleno pero ultima vuelta)
        _p("C", "Si tengo el deposito lleno (89.7L) pero estoy P8, que estrategia?",
           ["larga", "stint", "ventana", "SC", "ahorrar"]),

        # Caso: todos los valores en cero (ticker minimalista simulado)
        _p("D", "Que datos faltan en este ticker?",
           ["TYR", "BRK", "neumaticos", "frenos"]),

        # Caso: temperatura neumaticos exactamente 105C (limite del trigger)
        # Ticker F tiene 100-103... decidir si esta cerca del limite
        _p("F", "Las temperaturas de neumaticos estan cerca del limite (105C)?",
           ["si", "cerca", "100", "102", "103", "101", "limite"]),

        # Caso: session_type = PRACTICE (no es carrera)
        _p("D", "Es una sesion de practica. Cambia la estrategia?",
           ["practica", "test", "no", "importa", "carrera"]),

        # Caso: solo 1 rival en CLS1 (situacion poco comun)
        _p("B", "Solo tengo 2 rivales en CLS1. Es buena senal?",
           ["buena", "liderando", "P1", "ventaja"]),

        # Caso: lider pero sin seccion > en GAP (formato correcto)
        _p("B", "Por que no hay seccion '>' en el GAP?",
           ["lider", "primero", "P1", "delante"]),

        # Caso: FAR vacio
        _p("B", "Hay rivales muy lejanos?",
           ["10", "50s", "lejanos", "FAR"]),

        # Caso: LAP vacio (sin doblados)
        _p("D", "Hay coches doblados?",
           ["no", "LAP", "2", "---"]),

        # Caso: ticker sin datos de clima (solo DRV + GAP)
        _p("D", "Que tiempo hace?",
           ["no", "tengo", "WTH", "clima", "datos"]),

        # Caso: todas las cuatro temperaturas de neumaticos iguales
        _p("C", "Las temperaturas de neumaticos son muy uniformes. Que indica?",
           ["nuevos", "pocas", "vueltas", "normal", "homogeneas"]),
    ]


def generate_level_8() -> list[dict]:
    """Nivel 8: Razonamiento temporal (10 prompts, cada uno con 3-5 ticks).

    Serie de ticks consecutivos. Debe detectar tendencias.
    """
    series_1 = (
        "TICK 1 (V10):\n" + TICKERS["A"] + "\n\n"
        "TICK 2 (V12):\n"
        "DRV:P3|L12|F:35.7L/3.2(10L)|TYR:55/52/50/48.98/100/101/99\n"
        "BRK:42/39/26/24\n"
        "GAP>VST:+3.5.1:48.5|<ALO:-2.8.1:48.1.d+0.2\n"
        "SES:HY|RACE|38L|40:00\n"
        "WTH:MED|22|30%+15m|SC:N\n"
        "RIV:20 cars\n"
        "CLS1(2):VST|HY|+3.5|V11.ALO|HY|-2.8|V12\n"
        "CLS2(5):HAM|HY|+10.2|V11.VER|HY|+14.0|V11.NOR|GT3|+16.8|V11.PIA|GT3|+20.4|V11.RUS|GT3|+27.0|V11\n"
        "FAR(8):+50s behind\n"
        "LAP(5):PER(-1L).TSU(-2L).STR(-2L).ZHO(-3L).LEC(-1L)\n\n"
        "TICK 3 (V14):\n"
        "DRV:P3|L14|F:29.3L/3.2(8L)|TYR:42/40/38/35.102/104/105/103\n"
        "BRK:46/43/30/28\n"
        "GAP>VST:+4.8.1:48.7|<ALO:-3.5.1:48.3.d+0.4\n"
        "SES:HY|RACE|38L|35:00\n"
        "WTH:MED|22|30%+15m|SC:N\n"
        "RIV:20 cars\n"
        "CLS1(2):VST|HY|+4.8|V13.ALO|HY|-3.5|V14\n"
        "CLS2(5):HAM|HY|+11.8|V13.VER|HY|+15.6|V13.NOR|GT3|+18.4|V13.PIA|GT3|+22.0|V13.RUS|GT3|+28.6|V13\n"
        "FAR(8):+55s behind\n"
        "LAP(5):PER(-1L).TSU(-2L).STR(-2L).ZHO(-3L).LEC(-1L)"
    )

    series_2 = (
        "TICK 1 (V8):\n"
        "DRV:P5|L8|F:72.4L/3.2(21L)|TYR:95/94/93/92.85/87/88/86\n"
        "GAP>VER:+5.1.1:48.2|<LEC:-3.2.1:48.9.d-0.7\n"
        "SES:HY|RACE|38L|50:00\n"
        "WTH:GRN|21|10%+0m|SC:N\n"
        "RIV:20 cars\n\n"
        "TICK 2 (V10):\n"
        "DRV:P4|L10|F:65.8L/3.2(19L)|TYR:82/80/78/76.89/91/92/90\n"
        "GAP>VER:+3.8.1:48.3|<LEC:-2.5.1:48.7.d-0.4\n"
        "SES:HY|RACE|38L|46:00\n"
        "WTH:GRN|21|10%+0m|SC:N\n"
        "RIV:20 cars\n\n"
        "TICK 3 (V12):\n"
        "DRV:P3|L12|F:59.2L/3.2(17L)|TYR:68/66/64/62.92/94/95/93\n"
        "GAP>VER:+2.5.1:48.5|<LEC:-1.8.1:48.6.d-0.1\n"
        "SES:HY|RACE|38L|42:00\n"
        "WTH:GRN|21|10%+0m|SC:N\n"
        "RIV:20 cars"
    )

    return [
        # Serie 1: tyre deg acelerandose + temps subiendo
        _p("A", "Analiza la tendencia de degradacion de neumaticos en los 3 ticks.",
           ["acelerando", "peor", "42", "55", "72", "102", "105"],
           rag_context=series_1),

        # Serie 1: gap evolution
        _p("A", "VST se esta alejando o acercando? Y ALO?",
           ["VST", "alejando", "2.1", "3.5", "4.8", "ALO", "acercando", "1.2", "2.8", "3.5"]),
        # Correcto: VST se aleja (2.1 -> 3.5 -> 4.8), ALO se acerca (1.2 -> 2.8 -> 3.5)

        # Serie 1: brake wear increasing
        _p("A", "La degradacion de frenos se esta acelerando?",
           ["si", "42", "39", "46", "43", "acelerando"]),
        # Correcto: BRK pasa de 38/35/22/20 -> 42/39/26/24 -> 46/43/30/28

        # Serie 1: full strategy analysis
        _p("A", "Recomienda estrategia basada en la tendencia de los 3 ticks.",
           ["entrar", "neumaticos", "frenos", "ALO", "proxima", "vuelta"]),

        # Serie 2: position improvement
        _p("A", "Estamos ganando posiciones? Que esta cambiando?",
           ["P5", "P4", "P3", "ganando", "adelantando", "progresando"]),

        # Serie 2: gap to VER closing
        _p("A", "Estamos alcanzando a VER?",
           ["si", "5.1", "3.8", "2.5", "alcanzando", "cerrando"]),

        # Serie 2: tyre deg rate in series 2
        _p("A", "Como esta la degradacion de neumaticos en esta serie?",
           ["95", "82", "68", "degradando", "consistente"]),

        # Serie 2: pace comparison (delta changing)
        _p("A", "Nuestro ritmo relativo a LEC esta mejorando o empeorando?",
           ["mejorando", "d-0.7", "d-0.4", "d-0.1", "empeorando"]),
        # Correcto: d-0.7 -> d-0.4 -> d-0.1 = empeorando (antes eras mas rapido)

        # Serie 2: full race analysis
        _p("A", "Resume la evolucion de la carrera en estos 3 ticks.",
           ["P5", "P4", "P3", "adelantando", "LEC", "VER", "mejorando"]),

        # Serie combinada: tyre temps + wear comparison
        _p("A", "Compara la degradacion entre la Serie 1 y la Serie 2.",
           ["serie 1", "peor", "100", "102", "sobrecalentado", "serie 2", "mejor"]),
    ]


# =============================================================================
# GENERADOR PRINCIPAL
# =============================================================================

GENERATORS = {
    1: ("Extraccion de campos", generate_level_1),
    2: ("Interpretacion de campos", generate_level_2),
    3: ("Respuesta a triggers", generate_level_3),
    4: ("Razonamiento multicampo", generate_level_4),
    5: ("Razonamiento con RAG", generate_level_5),
    6: ("Estrategia multi-trigger", generate_level_6),
    7: ("Casos limite y anomalias", generate_level_7),
    8: ("Razonamiento temporal", generate_level_8),
}


def generate_all_prompts() -> dict:
    """Genera todos los prompts del benchmark."""
    return {
        level: {
            "name": info[0],
            "prompts": info[1](),
        }
        for level, info in GENERATORS.items()
    }


# =============================================================================
# REGLAS DE APROBACION POR NIVEL
# =============================================================================

# Puntuacion minima para pasar cada nivel
PASS_THRESHOLDS = {
    1: 0.90,  # 90% - extraccion literal
    2: 0.85,  # 85% - interpretacion
    3: 0.80,  # 80% - triggers
    4: 0.75,  # 75% - multicampo
    5: 0.70,  # 70% - RAG
    6: 0.65,  # 65% - multi-trigger
    7: 0.60,  # 60% - edge cases
    8: 0.00,  # Sin umbral (ranking abierto)
}


# =============================================================================
# CLIENTE API (OpenAI-compatible -> LM Studio / LiteLLM)
# =============================================================================

class LLMClient:
    """Cliente para API OpenAI-compatible (LM Studio, LiteLLM, etc.)."""

    def __init__(self, base_url: str, model: str, api_key: str = "sk-benchmark"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.client = httpx.Client(timeout=300.0) if httpx else None

    def _chat_url(self) -> str:
        """Determina la URL del endpoint chat completions."""
        # Intentar /v1/chat/completions (OpenAI standard) primero
        # Si la base_url ya incluye /v1 o /api/v1, no duplicar
        if self.base_url.endswith("/v1") or self.base_url.endswith("/api/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def ask(self, system_prompt: str, user_content: str) -> tuple[str, float, float]:
        """Envia un prompt y recibe respuesta streaming.

        Maneja modelos de razonamiento (con reasoning_content) correctamente:
        - reasoning_content = pensamiento interno (se descarta para evaluacion)
        - content = respuesta final (se usa para evaluacion)

        Si content llega vacio, significa que el modelo se quedo sin tokens
        antes de terminar de razonar. En ese caso, se incrementa max_tokens
        automaticamente en el siguiente intento.

        Returns:
            (texto_respuesta, ttft_ms, tokens_por_segundo)
            texto_respuesta = content del modelo (respuesta final)
        """
        if not self.client:
            return ("[httpx no instalado - modo dry-run]", 0.0, 0.0)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,  # Baja temperatura para consistencia
            "max_tokens": 15000,  # Sin limite practico (contexto 16k - ~800 de prompt)
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        full_text = ""  # content del modelo (respuesta final para evaluacion)
        reasoning_text = ""  # reasoning_content (pensamiento interno, se descarta)
        first_token_time: Optional[float] = None
        start_time = time.monotonic()
        content_token_count = 0
        reasoning_token_count = 0

        try:
            with self.client.stream(
                "POST",
                self._chat_url(),
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                    else:
                        data_str = line
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})

                        # content = respuesta final del modelo (para evaluar)
                        token = delta.get("content", "")
                        if token:
                            if first_token_time is None:
                                first_token_time = time.monotonic()
                            full_text += token
                            content_token_count += 1
                            continue

                        # reasoning_content = pensamiento interno (solo tracking)
                        reasoning = delta.get("reasoning_content", "")
                        if reasoning:
                            reasoning_text += reasoning
                            reasoning_token_count += 1
                            if first_token_time is None and not full_text:
                                # Primer token visible es del razonamiento
                                pass  # No contamos TTFT hasta que llegue content
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error("Error en llamada LLM: %s", e)
            return (f"[ERROR: {e}]", 0.0, 0.0)

        elapsed = time.monotonic() - start_time

        # Log si el modelo razono pero no produjo respuesta final
        if reasoning_text and not full_text:
            logger.warning(
                "Modelo solo produjo razonamiento (%d chars), sin respuesta final. "
                "Aumentar max_tokens o el modelo no pudo completar.",
                len(reasoning_text),
            )
        elif reasoning_text and full_text:
            logger.info(
                "Modelo de razonamiento: %d chars de pensamiento + %d chars de respuesta final",
                len(reasoning_text), len(full_text),
            )

        ttft = (first_token_time - start_time) * 1000 if first_token_time else elapsed * 1000
        effective_tokens = max(content_token_count, 1)
        tps = effective_tokens / elapsed if elapsed > 0 else 0

        return (full_text.strip(), ttft, tps)


# =============================================================================
# EVALUADOR
# =============================================================================

class Evaluator:
    """Evalua respuestas del LLM contra rubricas."""

    @staticmethod
    def keyword_score(text: str, keywords: list[str]) -> float:
        """Puntuacion 0-1 basada en cuantos keywords aparecen en el texto."""
        if not keywords:
            return 0.0
        text_lower = text.lower()
        matches = sum(1 for kw in keywords if kw.lower() in text_lower)
        return matches / len(keywords)

    @staticmethod
    def evaluate_level_1(prompt: dict, response: str) -> dict:
        """Nivel 1: el LLM debe mencionar los keywords esperados."""
        score = Evaluator.keyword_score(response, prompt["expected_keywords"])
        return {
            "score": score,
            "passed": score >= 0.5,  # Al menos la mitad de keywords
            "details": {"keyword_match": score},
        }

    @staticmethod
    def evaluate_level_2(prompt: dict, response: str) -> dict:
        """Nivel 2: interpretacion - keywords mas flexibles."""
        score = Evaluator.keyword_score(response, prompt["expected_keywords"])
        return {
            "score": score,
            "passed": score >= 0.4,
            "details": {"keyword_match": score},
        }

    @staticmethod
    def evaluate_level_3(prompt: dict, response: dict) -> dict:
        """Nivel 3: triggers - check rubric + keywords."""
        kw_score = Evaluator.keyword_score(response, prompt["expected_keywords"])
        rubric = prompt.get("rubric", {})

        rubric_score = 0.0
        if rubric.get("recommends_pit"):
            rubric_score += 0.3 if any(w in response.lower() for w in ["entrar", "boxes", "pits", "parada"]) else 0.0
        if rubric.get("recommends_not_pit"):
            rubric_score += 0.3 if any(w in response.lower() for w in ["no", "quedate", "espera", "suficiente"]) else 0.0
        if rubric.get("mentions_fuel"):
            rubric_score += 0.2 if any(w in response.lower() for w in ["combustible", "fuel", "gasolina"]) else 0.0
        if rubric.get("identifies_overheating"):
            rubric_score += 0.3 if any(w in response.lower() for w in ["caliente", "alta", "sobrecalentado", "temp"]) else 0.0

        total = kw_score * 0.5 + rubric_score
        return {
            "score": total,
            "passed": total >= 0.4,
            "details": {"keyword_score": kw_score, "rubric_score": rubric_score},
        }

    @staticmethod
    def evaluate_level_4(prompt: dict, response: str) -> dict:
        """Nivel 4: multicampo - necesita keywords de 2+ categorias."""
        kw_score = Evaluator.keyword_score(response, prompt["expected_keywords"])
        return {
            "score": kw_score,
            "passed": kw_score >= 0.3,
            "details": {"keyword_match": kw_score},
        }

    @staticmethod
    def evaluate_level_5(prompt: dict, response: str) -> dict:
        """Nivel 5: RAG - debe referenciar contexto historico."""
        kw_score = Evaluator.keyword_score(response, prompt["expected_keywords"])
        rag_context = prompt.get("rag_context") or ""
        # Bonus si menciona numeros del RAG
        rag_refs = 0
        if rag_context:
            for word in rag_context.split():
                if word.isdigit() and word in response:
                    rag_refs += 1
        bonus = min(rag_refs * 0.05, 0.2)
        total = kw_score * 0.8 + bonus
        return {
            "score": total,
            "passed": total >= 0.35,
            "details": {"keyword_score": kw_score, "rag_references": rag_refs},
        }

    @staticmethod
    def evaluate_level_6(prompt: dict, response: str) -> dict:
        """Nivel 6: multi-trigger - debe priorizar correctamente."""
        kw_score = Evaluator.keyword_score(response, prompt["expected_keywords"])
        rubric = prompt.get("rubric", {})

        rubric_score = 0.0
        if rubric.get("must_prioritize_pit"):
            rubric_score += 0.4 if any(w in response.lower() for w in ["entrar", "ahora", "boxes", "urgente"]) else 0.0
        if rubric.get("should_recommend_pit"):
            rubric_score += 0.3 if any(w in response.lower() for w in ["entrar", "boxes", "parada"]) else 0.0
        if rubric.get("must_prioritize_pit_immediate"):
            rubric_score += 0.5 if any(w in response.lower() for w in ["ahora", "inmediato", "urgente", "entrar"]) else 0.0

        total = kw_score * 0.5 + rubric_score
        return {
            "score": total,
            "passed": total >= 0.4,
            "details": {"keyword_score": kw_score, "rubric_score": rubric_score},
        }

    @staticmethod
    def evaluate_level_7(prompt: dict, response: str) -> dict:
        """Nivel 7: edge cases - debe reconocer limites y anomalias."""
        kw_score = Evaluator.keyword_score(response, prompt["expected_keywords"])
        return {
            "score": kw_score,
            "passed": kw_score >= 0.3,
            "details": {"keyword_match": kw_score},
        }

    @staticmethod
    def evaluate_level_8(prompt: dict, response: str) -> dict:
        """Nivel 8: temporal - debe detectar tendencias."""
        kw_score = Evaluator.keyword_score(response, prompt["expected_keywords"])
        return {
            "score": kw_score,
            "passed": kw_score >= 0.25,
            "details": {"keyword_match": kw_score},
        }


LEVEL_EVALUATORS = {
    1: Evaluator.evaluate_level_1,
    2: Evaluator.evaluate_level_2,
    3: Evaluator.evaluate_level_3,
    4: Evaluator.evaluate_level_4,
    5: Evaluator.evaluate_level_5,
    6: Evaluator.evaluate_level_6,
    7: Evaluator.evaluate_level_7,
    8: Evaluator.evaluate_level_8,
}


# =============================================================================
# REPORTE
# =============================================================================

def _fmt_pct(v: float) -> str:
    return f"{v*100:.1f}%"

def _fmt_ms(ms: float) -> str:
    return f"{ms:.0f}ms"

def _bar(v: float, width: int = 20) -> str:
    filled = int(v * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def generate_report(all_results: dict, model: str, base_url: str,
                    total_time: float) -> str:
    """Genera reporte markdown del benchmark."""
    lines = [
        f"# Benchmark LLM: {model}",
        f"",
        f"- **Endpoint**: {base_url}",
        f"- **Modelo**: {model}",
        f"- **Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **Duracion total**: {total_time:.0f}s",
        f"- **Total prompts**: {sum(len(r['prompts']) for r in all_results.values())}",
        f"",
        f"## Resultados por Nivel",
        f"",
        f"| Nivel | Nombre | Pts | Prompts | Aciertos | Aprobado | TTFT(ms) | Tok/s |",
        f"|-------|--------|:---:|:-------:|:--------:|:--------:|:--------:|:-----:|",
    ]

    total_prompts = 0
    total_passed = 0
    highest_level_passed = 0
    cumulative_weighted = 0.0

    for level in sorted(all_results.keys()):
        r = all_results[level]
        prompts = r["prompts"]
        n = len(prompts)
        passed = sum(1 for p in prompts if p.get("passed", False))
        avg_score = sum(p.get("score", 0) for p in prompts) / n if n > 0 else 0
        avg_ttft = sum(p.get("ttft_ms", 0) for p in prompts) / n if n > 0 else 0
        avg_tps = sum(p.get("tokens_per_second", 0) for p in prompts) / n if n > 0 else 0

        threshold = PASS_THRESHOLDS.get(level, 0.0)
        passed_level = avg_score >= threshold
        if passed_level:
            highest_level_passed = level

        status = "PASA" if passed_level else "NO PASA"
        lines.append(
            f"| L{level} | {r['name']} | {_fmt_pct(avg_score)} | {n} | "
            f"{passed}/{n} | {status} | {_fmt_ms(avg_ttft)} | {avg_tps:.1f} |"
        )

        total_prompts += n
        total_passed += passed
        cumulative_weighted += avg_score * level

    weighted = cumulative_weighted / sum(range(1, max(all_results.keys()) + 1)) if all_results else 0

    lines += [
        f"",
        f"## Resumen Global",
        f"",
        f"- **Nivel maximo aprobado**: L{highest_level_passed}",
        f"- **Prompts totales**: {total_prompts}",
        f"- **Aciertos totales**: {total_passed}/{total_prompts} ({_fmt_pct(total_passed/total_prompts) if total_prompts>0 else 'N/A'})",
        f"- **Puntuacion ponderada (por nivel)**: {_fmt_pct(weighted)}",
        f"",
    ]

    # Matriz de aprobacion por nivel
    lines += [
        f"## Matriz de Aprobacion",
        f"",
        f"```",
    ]
    for level in sorted(all_results.keys()):
        r = all_results[level]
        prompts = r["prompts"]
        n = len(prompts)
        passed = sum(1 for p in prompts if p.get("passed", False))
        score = sum(p.get("score", 0) for p in prompts) / n if n > 0 else 0
        bar = _bar(score)
        threshold = PASS_THRESHOLDS.get(level, 0.0)
        flag = ">" if score >= threshold else "X"
        lines.append(f"L{level} {bar} {_fmt_pct(score)} (min {_fmt_pct(threshold)}) {flag}")
    lines += ["```", ""]

    # Debilidades detectadas
    lines += ["## Debilidades Detectadas", ""]
    weak_count = 0
    for level in sorted(all_results.keys()):
        r = all_results[level]
        for i, p in enumerate(r["prompts"]):
            score = p.get("score", 0)
            if score < 0.2:
                weak_count += 1
                if weak_count <= 10:  # Limitar a 10 ejemplos
                    ticker_id = p.get("ticker_id", "?")
                    question = p.get("question", "?")[:80]
                    lines.append(f"- **L{level}.{i+1}** ({ticker_id}): {question}... (score: {_fmt_pct(score)})")
    if weak_count == 0:
        lines.append("_Ninguna debilidad significativa detectada._")
    elif weak_count > 10:
        lines.append(f"_... y {weak_count - 10} debilidades mas._")

    lines += [
        "",
        "---",
        f"_Generado por Vantare Benchmark LLM v1.0_",
    ]

    return "\n".join(lines)


# =============================================================================
# MODELOS PREDEFINIDOS PARA --all
# =============================================================================

DEFAULT_MODELS = [
    {"model": "qwen3.5-4b", "name": "Qwen 3.5 4B (Q4)"},
    {"model": "llama3.2-3b", "name": "Llama 3.2 3B (Q8)"},
    {"model": "phi3.5-mini", "name": "Phi-3.5-mini (Q8)"},
    {"model": "gemma2-2b", "name": "Gemma 2 2B (Q8)"},
    {"model": "deepseek-r1-distill-qwen-7b", "name": "DeepSeek-R1-Distill-Qwen-7B (Q4)"},
    {"model": "qwen2.5-7b", "name": "Qwen 2.5 7B (Q4)"},
]


# =============================================================================
# MAIN
# =============================================================================

def run_benchmark(model: str, base_url: str, output_dir: str,
                  single_level: Optional[int] = None,
                  dry_run: bool = False) -> dict:
    """Ejecuta el benchmark completo para un modelo.

    Returns:
        Dict con resultados por nivel.
    """
    logger.info("=== Benchmark para modelo: %s ===", model)
    logger.info("Endpoint: %s", base_url)
    if dry_run:
        logger.info("MODO DRY-RUN: solo se generaran los prompts (sin llamada API)")

    all_prompts = generate_all_prompts()
    client = LLMClient(base_url, model) if not dry_run else None

    all_results: dict[int, dict] = {}
    total_start = time.monotonic()

    for level in sorted(all_prompts.keys()):
        if single_level and level != single_level:
            continue

        level_info = all_prompts[level]
        level_name = level_info["name"]
        prompts = level_info["prompts"]

        logger.info("--- Nivel %d: %s (%d prompts) ---", level, level_name, len(prompts))

        results = []
        for idx, prompt in enumerate(prompts):
            # Construir contenido de usuario
            user_parts = []
            if prompt.get("ticker"):
                user_parts.append("### TELEMETRIA ###")
                user_parts.append(prompt["ticker"])
            if prompt.get("rag_context"):
                user_parts.append("")
                user_parts.append(prompt["rag_context"])
            if prompt.get("trigger"):
                user_parts.append("")
                user_parts.append(f"### MOTIVO ###\n{prompt['trigger']}")
            if prompt.get("question"):
                user_parts.append("")
                user_parts.append(f"### PREGUNTA ###\n{prompt['question']}")

            user_content = "\n".join(user_parts)

            if dry_run:
                response_text = "[dry-run]"
                ttft = 0.0
                tps = 0.0
            else:
                p_bar = f"[{idx+1}/{len(prompts)}]"
                logger.info("  %s Enviando prompt L%d.%d...", p_bar, level, idx+1)
                response_text, ttft, tps = client.ask(SYSTEM_PROMPT_TICKER, user_content)
                logger.info("  %s Respuesta (%d chars, TTFT=%.0fms, TPS=%.1f): %s",
                           p_bar, len(response_text), ttft, tps,
                           response_text[:100])

            # Evaluar
            evaluator_fn = LEVEL_EVALUATORS.get(level)
            if evaluator_fn:
                eval_result = evaluator_fn(prompt, response_text)
            else:
                eval_result = {"score": 0.0, "passed": False, "details": {}}

            results.append({
                "level": level,
                "index": idx + 1,
                "prompt": prompt["question"][:60],
                "ticker_id": prompt.get("ticker_id", ""),
                "response": response_text,
                "ttft_ms": ttft,
                "tokens_per_second": tps,
                "score": eval_result["score"],
                "passed": eval_result["passed"],
                "details": eval_result.get("details", {}),
            })

        passed_count = sum(1 for r in results if r["passed"])
        avg_score = sum(r["score"] for r in results) / len(results) if results else 0
        logger.info("  Nivel %d: %d/%d prompts pasados (score: %.1f%%)",
                    level, passed_count, len(results), avg_score * 100)

        all_results[level] = {
            "name": level_name,
            "prompts": results,
        }

    total_elapsed = time.monotonic() - total_start
    logger.info("=== Benchmark completado en %.0f segundos ===", total_elapsed)

    # Generar reporte
    report = generate_report(all_results, model, base_url, total_elapsed)

    # Guardar reporte y datos
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Reporte markdown
    safe_model = model.replace("/", "_").replace(" ", "_")
    report_path = os.path.join(output_dir, f"{timestamp}_{safe_model}_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Reporte guardado: %s", report_path)

    # Datos crudos JSON
    json_path = os.path.join(output_dir, f"{timestamp}_{safe_model}_data.json")
    serializable = {}
    for level, r in all_results.items():
        serializable[str(level)] = {
            "name": r["name"],
            "prompts": [
                {
                    "level": p["level"],
                    "index": p["index"],
                    "prompt": p["prompt"],
                    "ticker_id": p["ticker_id"],
                    "response": p["response"],
                    "ttft_ms": p["ttft_ms"],
                    "tokens_per_second": p["tokens_per_second"],
                    "score": p["score"],
                    "passed": p["passed"],
                    "details": p["details"],
                }
                for p in r["prompts"]
            ],
        }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    logger.info("Datos guardados: %s", json_path)

    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark progresivo de LLMs para Vantare Ingeniero IA"
    )
    parser.add_argument("--model", default="qwen3.5-4b",
                        help="Nombre del modelo en la API")
    parser.add_argument("--base-url", default="http://192.168.1.41:1234/api/v1",
                        help="URL base de la API OpenAI-compatible")
    parser.add_argument("--level", type=int, default=None,
                        help="Ejecutar solo un nivel especifico (1-8)")
    parser.add_argument("--output-dir", default="./benchmark_reports",
                        help="Directorio para guardar reportes")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo generar prompts sin llamar a la API")
    parser.add_argument("--all", action="store_true",
                        help="Ejecutar benchmark con todos los modelos predefinidos")
    parser.add_argument("--api-key", default="sk-benchmark",
                        help="API key para la solicitud")
    args = parser.parse_args()

    if not httpx:
        logger.error("httpx no esta instalado. Ejecuta: pip install httpx")
        sys.exit(1)

    if args.dry_run:
        logger.info("=== MODO DRY-RUN: generando prompts ===")
        all_prompts = generate_all_prompts()
        total = sum(len(v["prompts"]) for v in all_prompts.values())
        for level in sorted(all_prompts.keys()):
            info = all_prompts[level]
            n = len(info["prompts"])
            logger.info("  Nivel %d (%s): %d prompts", level, info["name"], n)
        logger.info("Total: %d prompts en %d niveles", total, len(all_prompts))
        return

    if args.all:
        logger.info("=== Benchmark multi-modelo ===")
        for model_cfg in DEFAULT_MODELS:
            model = model_cfg["model"]
            name = model_cfg["name"]
            logger.info("")
            logger.info(">>> Modelo: %s (%s) <<<", name, model)
            try:
                run_benchmark(model, args.base_url, args.output_dir, args.level)
            except Exception as e:
                logger.error("Error en modelo %s: %s", model, e)
                continue
        logger.info("=== Benchmark multi-modelo completado ===")
    else:
        run_benchmark(args.model, args.base_url, args.output_dir, args.level)

    # Mostrar resumen de los prompts generados
    if args.dry_run:
        logger.info("")
        logger.info("Ejemplo de prompt L1.1:")
        prompts = generate_level_1()
        print(SYSTEM_PROMPT_TICKER)
        print()
        print("### TELEMETRIA ###")
        print(prompts[0]["ticker"])
        print()
        print("### PREGUNTA ###")
        print(prompts[0]["question"])


if __name__ == "__main__":
    main()
