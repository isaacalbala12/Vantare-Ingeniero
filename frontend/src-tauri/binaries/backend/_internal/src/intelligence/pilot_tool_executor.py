from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("vantare.pilot_tool_executor")

ACTION_TOOLS = frozenset({
    "set_speak_only",
    "set_verbosity",
    "spotter_toggle",
    "set_braking_zones_mute",
    "monitor_competitor",
    "set_pit_fuel",
    "set_pit_tyres",
    "watch_snip",
})
QUERY_TOOLS = frozenset({
    "get_fuel_status",
    "get_gap_status",
    "query_competitor",
    "get_damage_report",
    "get_tire_wear",
    "get_flag_status",
    "get_race_time_remaining",
    "get_pit_window_status",
})


@dataclass
class ToolResult:
    ok: bool
    spoken_message: Optional[str] = None
    data: Optional[dict] = None
    is_action: bool = False


class PilotToolExecutor:
    """Ejecuta tools PTT; el handler genera la voz (no el LLM)."""

    async def run(
        self,
        engine,
        name: str,
        args: dict,
        *,
        emit_voice: bool = True,
    ) -> ToolResult:
        handler = getattr(self, f"_handle_{name}", None)
        if handler is None:
            logger.warning("Tool PTT desconocida: %s", name)
            return ToolResult(ok=False)
        try:
            return await handler(engine, args or {}, emit_voice=emit_voice)
        except Exception as exc:
            logger.warning("Error ejecutando tool %s: %s", name, exc)
            msg = "No pude procesar ese comando ahora."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)

    async def run_all(
        self,
        engine,
        tool_calls: list,
        *,
        emit_voice: bool = True,
    ) -> list[ToolResult]:
        results = []
        for tc in tool_calls:
            results.append(
                await self.run(engine, tc.name, tc.arguments, emit_voice=emit_voice)
            )
        return results

    @staticmethod
    def is_pure_action(tool_calls: list) -> bool:
        if not tool_calls:
            return False
        names = {tc.name for tc in tool_calls}
        return names.issubset(ACTION_TOOLS)

    @staticmethod
    def is_mixed_intent(tool_calls: list) -> bool:
        if len(tool_calls) <= 1:
            return False
        names = {tc.name for tc in tool_calls}
        has_action = bool(names & ACTION_TOOLS)
        has_query = bool(names & QUERY_TOOLS)
        return has_action and has_query

    async def _handle_set_speak_only(
        self, engine, args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        enabled = bool(args.get("enabled", True))
        msg = engine.apply_speak_only(enabled, emit_voice=emit_voice)
        return ToolResult(ok=True, spoken_message=msg, is_action=True)

    async def _handle_set_verbosity(
        self, engine, args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        level = str(args.get("level", "") or "").strip()
        if not level:
            msg = "No entendí el nivel de verbosidad."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        msg = engine.apply_set_verbosity(level)
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg, is_action=True)

    async def _handle_spotter_toggle(
        self, engine, args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        enabled = bool(args.get("enabled", True))
        msg = engine.apply_spotter_toggle(enabled, emit_alert=emit_voice)
        return ToolResult(
            ok=msg is not None,
            spoken_message=msg,
            is_action=True,
            data={"spotter_enabled": enabled},
        )

    async def _handle_get_fuel_status(
        self, engine, _args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        tele = engine._resolve_ptt_telemetry()
        laps = tele.get("fuel_laps_remaining")
        if laps is None:
            advice = engine._to_dict(getattr(engine._get_strategy_service(), "latest_advice", None))
            fuel = advice.get("fuel") if isinstance(advice.get("fuel"), dict) else {}
            laps = fuel.get("estimated_laps_remaining")
        if laps is None:
            msg = "No tengo datos de combustible ahora."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        msg = f"Te quedan unos {float(laps):.1f} vueltas de combustible."
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg, data={"fuel_laps_remaining": float(laps)})

    async def _handle_get_gap_status(
        self, engine, _args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        tele = engine._resolve_ptt_telemetry()
        ahead = tele.get("time_gap_car_ahead") or tele.get("gap_ahead")
        behind = tele.get("time_gap_car_behind") or tele.get("gap_behind")
        if ahead is None and behind is None:
            msg = "No tengo datos de gap ahora."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        parts = []
        if ahead is not None:
            parts.append(f"delante {float(ahead):.1f}")
        if behind is not None:
            parts.append(f"detrás {float(behind):.1f}")
        msg = f"Gap {' y '.join(parts)} segundos."
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg, data={"ahead": ahead, "behind": behind})

    async def _handle_query_competitor(
        self, engine, args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        competitors = engine.get_competitors_list()
        if not competitors:
            msg = "Sin datos de rivales disponibles."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        from src.intelligence.competitor_queries import resolve_from_tool_args

        comp_dicts = [c.model_dump() if hasattr(c, "model_dump") else c for c in competitors]
        result = resolve_from_tool_args(args, comp_dicts)
        summary = (result.summary or "").strip()
        if not summary:
            msg = "No encontré ese rival."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        if emit_voice:
            engine._emit_competitor_response(summary, payload={"summary": summary})
        return ToolResult(ok=True, spoken_message=summary, data={"summary": summary})

    async def _handle_set_braking_zones_mute(
        self, engine, args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        if "enabled" not in args:
            msg = "No entendí si activar o desactivar el silencio en frenada."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        msg = engine.apply_set_braking_zones_mute(bool(args["enabled"]))
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg, is_action=True)

    async def _handle_monitor_competitor(
        self, engine, args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        action = args.get("action")
        driver_index = args.get("driver_index")
        if not action or driver_index is None:
            msg = "Necesito acción start/stop e índice del rival."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        msg = engine.apply_monitor_competitor(str(action), int(driver_index))
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg, is_action=True)

    async def _handle_get_damage_report(
        self, engine, _args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        from src.intelligence.damage_report import (
            active_damage_items,
            format_damage_status_message,
            format_damage_summary,
        )

        tele = engine._resolve_ptt_telemetry()
        items = active_damage_items(tele)
        msg = format_damage_status_message(tele, items) if items else None
        if not msg:
            msg = format_damage_summary(tele)
        if not msg or "leves" in msg.lower() and float(tele.get("damage_aero", 0) or 0) <= 0:
            if items:
                pass
            elif float(tele.get("damage_aero", 0) or 0) <= 0 and not any(
                tele.get(k) for k in ("detached", "tyre_flat_fl", "tyre_flat_fr", "tyre_flat_rl", "tyre_flat_rr")
            ):
                msg = "No detecto daños significativos en el coche."
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg, data={"damage_items": items})

    async def _handle_get_tire_wear(
        self, engine, _args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        tele = engine._resolve_ptt_telemetry()
        keys = ("tyre_wear_fl", "tyre_wear_fr", "tyre_wear_rl", "tyre_wear_rr")
        labels = ("delantero izquierdo", "delantero derecho", "trasero izquierdo", "trasero derecho")
        wears = [float(tele.get(k, 0) or 0) for k in keys]
        if not any(w > 0 for w in wears):
            advice = engine._to_dict(getattr(engine._get_strategy_service(), "latest_advice", None))
            wear_block = advice.get("tyre_wear") if isinstance(advice.get("tyre_wear"), dict) else {}
            if wear_block:
                wears = [
                    float(wear_block.get("fl", wear_block.get("front_left", 0)) or 0),
                    float(wear_block.get("fr", wear_block.get("front_right", 0)) or 0),
                    float(wear_block.get("rl", wear_block.get("rear_left", 0)) or 0),
                    float(wear_block.get("rr", wear_block.get("rear_right", 0)) or 0),
                ]
        if not any(w > 0 for w in wears):
            msg = "No tengo datos de desgaste de neumáticos ahora."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        worst_i = max(range(4), key=lambda i: wears[i])
        avg = sum(wears) / 4.0
        msg = (
            f"Desgaste medio {avg:.0f}%. "
            f"El más castigado es el {labels[worst_i]} al {wears[worst_i]:.0f}%."
        )
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(
            ok=True,
            spoken_message=msg,
            data={"avg_wear": avg, "worst_wheel": labels[worst_i], "wears": wears},
        )

    async def _handle_set_pit_fuel(
        self, engine, args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        litres = args.get("litres")
        if litres is None:
            msg = "Indica cuántos litros quieres en boxes."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        try:
            required = max(1, int(litres))
        except (TypeError, ValueError):
            msg = "No entendí la cantidad de litros."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        if engine.lmu_api is None:
            msg = "Menú de boxes no disponible ahora."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        from src.intelligence.crewchief_events.pit_menu import PitMenuClient

        client = PitMenuClient(engine.lmu_api, dry_run=engine.pit_menu_dry_run())
        raw = await client.set_fuel_level(required)
        msg = _localize_pit_menu_message(raw, required)
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg, is_action=True, data={"litres": required})

    async def _handle_get_flag_status(
        self, engine, _args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        tele = engine._resolve_ptt_telemetry()
        session = engine._to_dict(getattr(engine, "_eval_session", None) or {})
        sc = bool(tele.get("safety_car_active") or tele.get("full_course_yellow_active"))
        yellow = int(tele.get("yellow_flag_state") or 0)
        if sc:
            msg = "Safety car o full course yellow activo."
        elif yellow > 0:
            msg = f"Amarilla activa — fase {yellow}."
        else:
            msg = "Pista en verde, sin banderas especiales."
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg, data={"yellow_flag_state": yellow, "sc": sc})

    async def _handle_get_race_time_remaining(
        self, engine, _args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        tele = engine._resolve_ptt_telemetry()
        laps_left = tele.get("session_laps_left")
        time_left = tele.get("session_time_left")
        if laps_left is not None and float(laps_left) >= 0:
            msg = f"Quedan {int(float(laps_left))} vueltas."
        elif time_left is not None and float(time_left) > 0:
            minutes = int(float(time_left) // 60)
            msg = f"Quedan unos {minutes} minutos de sesión."
        else:
            msg = "No tengo tiempo restante de sesión ahora."
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg)

    async def _handle_get_pit_window_status(
        self, engine, _args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        tele = engine._resolve_ptt_telemetry()
        strategy = engine._to_dict(getattr(engine, "_eval_strategy", None) or {})
        open_flag = tele.get("pit_window_open") or strategy.get("pit_window_open")
        if open_flag:
            msg = "Ventana de boxes abierta."
        elif tele.get("in_pits"):
            msg = "Estás en boxes."
        else:
            msg = "Ventana de boxes cerrada por ahora."
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg)

    async def _handle_watch_snip(
        self, engine, args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        action = str(args.get("action") or "snip").lower()
        session = engine._eval_session if isinstance(getattr(engine, "_eval_session", None), dict) else {}
        if action == "clear":
            session["watch_snip_requested"] = False
            msg = "Snip desactivado."
        else:
            session["watch_snip_requested"] = True
            msg = "Vigilando al rival activo — snip activado."
        engine._eval_session = session
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg, is_action=True)

    async def _handle_set_pit_tyres(
        self, engine, args: dict, *, emit_voice: bool = True
    ) -> ToolResult:
        from src.config import settings

        compound = str(args.get("compound") or "").strip()
        if not compound:
            msg = "Indica qué neumáticos quieres en boxes."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        if settings.PIT_MENU_CONFIRM_WRITES and not args.get("confirm"):
            msg = "¿Confirmas cambio de neumáticos en boxes? Repite confirmando."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=True, spoken_message=msg)
        if engine.lmu_api is None:
            msg = "Menú de boxes no disponible ahora."
            if emit_voice:
                engine._emit_voice_response(msg)
            return ToolResult(ok=False, spoken_message=msg)
        from src.intelligence.crewchief_events.pit_menu import PitMenuClient

        client = PitMenuClient(engine.lmu_api, dry_run=engine.pit_menu_dry_run())
        raw = await client.set_tyre_compound(compound)
        msg = _localize_pit_menu_message(raw, 0)
        if "tyres would be set" in raw.lower() or "tyres set" in raw.lower():
            msg = raw.replace("Dry run: tyres would be set to", "Simulación: neumáticos").replace(
                "Tyres set to", "Neumáticos configurados:"
            )
        if emit_voice:
            engine._emit_voice_response(msg)
        return ToolResult(ok=True, spoken_message=msg, is_action=True, data={"compound": compound})


def _localize_pit_menu_message(raw: str, litres: int) -> str:
    lower = raw.lower()
    if lower.startswith("dry run"):
        return f"Simulación: en boxes quedarían unos {litres} litros configurados."
    if "not available" in lower:
        return "El menú de combustible en boxes no está disponible."
    if "rejected" in lower:
        return "LMU rechazó el cambio en el menú de boxes."
    if lower.startswith("fuel level set"):
        return raw.replace("Fuel level set to", "Combustible en boxes configurado a").replace("litres", "litros")
    return raw

