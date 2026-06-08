"""Matriz contrato audio: triggers spotter + ingeniero → evento WS → elegibilidad voz."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.intelligence.triggers import TriggerAction, get_all_triggers

WsEvent = Literal["alert", "llm_pending+advice_*", "commentary_end", "strategy_update", "none"]


@dataclass(frozen=True)
class AudioContractRow:
    id: str
    source: str
    category: str
    sample_message: str
    audio_priority: str
    severity: str
    ws_event: WsEvent
    expect_voice: bool
    expect_tts_priority: Literal["IMMEDIATE", "NORMAL", "N/A"]


def _trigger_rows() -> list[AudioContractRow]:
    rows: list[AudioContractRow] = []
    for trigger in get_all_triggers():
        if trigger.action == TriggerAction.ALERT_ONLY:
            ws: WsEvent = "alert"
            prio = trigger.priority.name
            expect_voice = trigger.priority.name in ("CRITICAL", "HIGH", "WARNING")
            tts_prio: Literal["IMMEDIATE", "NORMAL", "N/A"] = (
                "IMMEDIATE" if expect_voice else "N/A"
            )
        elif trigger.action == TriggerAction.LLM_REQUIRED:
            ws = "llm_pending+advice_*"
            prio = trigger.priority.name
            expect_voice = True
            tts_prio = "NORMAL"
        else:
            ws = "strategy_update"
            prio = trigger.priority.name
            expect_voice = False
            tts_prio = "N/A"

        rows.append(
            AudioContractRow(
                id=f"trigger:{trigger.__class__.__name__}",
                source="IntelligenceEngine",
                category="strategy",
                sample_message=trigger.alert_text,
                audio_priority=prio,
                severity=prio,
                ws_event=ws,
                expect_voice=expect_voice,
                expect_tts_priority=tts_prio,
            )
        )
    return rows


SPOTTER_AUDIO_ROWS: list[AudioContractRow] = [
    AudioContractRow(
        id="spotter:proximity_enter",
        source="SpotterService",
        category="proximity",
        sample_message="Coche a la derecha",
        audio_priority="2",
        severity="INFO",
        ws_event="alert",
        expect_voice=True,
        expect_tts_priority="IMMEDIATE",
    ),
    AudioContractRow(
        id="spotter:proximity_clear",
        source="SpotterService",
        category="proximity",
        sample_message="Despejado derecha",
        audio_priority="2",
        severity="INFO",
        ws_event="alert",
        expect_voice=True,
        expect_tts_priority="IMMEDIATE",
    ),
    AudioContractRow(
        id="spotter:three_wide",
        source="SpotterService",
        category="proximity",
        sample_message="En el medio",
        audio_priority="3",
        severity="WARNING",
        ws_event="alert",
        expect_voice=True,
        expect_tts_priority="IMMEDIATE",
    ),
    AudioContractRow(
        id="spotter:limiter_enter",
        source="SpotterService",
        category="limiter",
        sample_message="Activa el limiter de boxes.",
        audio_priority="4",
        severity="CRITICAL",
        ws_event="alert",
        expect_voice=True,
        expect_tts_priority="IMMEDIATE",
    ),
    AudioContractRow(
        id="spotter:limiter_exit",
        source="SpotterService",
        category="limiter",
        sample_message="Desactiva el limiter de boxes.",
        audio_priority="3",
        severity="WARNING",
        ws_event="alert",
        expect_voice=True,
        expect_tts_priority="IMMEDIATE",
    ),
    AudioContractRow(
        id="spotter:fuel_critical",
        source="SpotterService",
        category="fuel",
        sample_message="¡Combustible crítico! Menos de 1 vuelta restante.",
        audio_priority="4",
        severity="CRITICAL",
        ws_event="alert",
        expect_voice=True,
        expect_tts_priority="IMMEDIATE",
    ),
    AudioContractRow(
        id="spotter:safety_car",
        source="SpotterService",
        category="safety_car",
        sample_message="Safety car desplegado / FCY activo en pista.",
        audio_priority="4",
        severity="CRITICAL",
        ws_event="alert",
        expect_voice=True,
        expect_tts_priority="IMMEDIATE",
    ),
    AudioContractRow(
        id="spotter:last_lap",
        source="SpotterService",
        category="session",
        sample_message="¡Última vuelta de la carrera!",
        audio_priority="2",
        severity="INFO",
        ws_event="alert",
        expect_voice=True,
        expect_tts_priority="IMMEDIATE",
    ),
    AudioContractRow(
        id="spotter:damage",
        source="SpotterService",
        category="damage",
        sample_message="Daños detectados en el monoplaza.",
        audio_priority="3",
        severity="WARNING",
        ws_event="alert",
        expect_voice=True,
        expect_tts_priority="IMMEDIATE",
    ),
    AudioContractRow(
        id="spotter:gaps",
        source="SpotterService",
        category="gaps",
        sample_message="Coche a 0.3s delante",
        audio_priority="1",
        severity="INFO",
        ws_event="alert",
        expect_voice=False,
        expect_tts_priority="N/A",
    ),
    AudioContractRow(
        id="spotter:ack",
        source="SpotterService",
        category="spotter",
        sample_message="Spotter activado.",
        audio_priority="1",
        severity="INFO",
        ws_event="alert",
        expect_voice=False,
        expect_tts_priority="N/A",
    ),
    AudioContractRow(
        id="engine:pearl",
        source="IntelligenceEngine",
        category="pearl",
        sample_message="Buen trabajo piloto.",
        audio_priority="2",
        severity="INFO",
        ws_event="alert",
        expect_voice=True,
        expect_tts_priority="NORMAL",
    ),
    AudioContractRow(
        id="pilot:advice",
        source="PilotQuestion",
        category="advice",
        sample_message="Tu combustible aguanta unas ocho vueltas más.",
        audio_priority="HIGH",
        severity="INFO",
        ws_event="llm_pending+advice_*",
        expect_voice=True,
        expect_tts_priority="NORMAL",
    ),
]

COMMENTARY_AUDIO_ROWS: list[AudioContractRow] = [
    AudioContractRow(
        id="commentary:batch",
        source="CommentaryOrchestrator",
        category="commentary",
        sample_message="Subiste a P3. Gap adelante +0.8s.",
        audio_priority="NORMAL",
        severity="INFO",
        ws_event="commentary_end",
        expect_voice=True,
        expect_tts_priority="NORMAL",
    ),
    AudioContractRow(
        id="commentary:race_start",
        source="CommentaryOrchestrator",
        category="commentary",
        sample_message="¡Salida! ¡Vamos vamos vamos!",
        audio_priority="HIGH",
        severity="INFO",
        ws_event="commentary_end",
        expect_voice=True,
        expect_tts_priority="NORMAL",
    ),
]

TRIGGER_AUDIO_ROWS: list[AudioContractRow] = _trigger_rows()
ALL_AUDIO_CONTRACT_ROWS: list[AudioContractRow] = (
    SPOTTER_AUDIO_ROWS + TRIGGER_AUDIO_ROWS + COMMENTARY_AUDIO_ROWS
)
