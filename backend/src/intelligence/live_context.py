import copy
from typing import Any


class LiveContextManager:
    """Administrador de contexto incremental vuelta a vuelta en tres tiers de snapshots."""

    def __init__(self, history_store: Any | None = None) -> None:
        self._fast: dict[str, Any] = {}
        self._standard: dict[str, Any] = {}
        self._deep: dict[str, Any] = {}

        # HistoryStore opcional para persistencia de consumo
        self._history_store = history_store

        # Históricos en memoria para cálculos de tendencias
        self._fuel_history: list[float] = []  # Últimas 10 vueltas de consumo
        self._tyre_deg_history: list[float] = []  # Historial de desgaste promedio
        self._battery_history: list[float] = []  # Historial de SOC

    def on_lap_completed(self, telemetry: dict, strategy: dict, session: dict) -> None:
        """Actualiza los 3 snapshots internos al completar una vuelta válida."""
        # 1. Extraer variables básicas
        phase = session.get("phase") or telemetry.get("session_type", "RACE")
        lap = telemetry.get("lap_number", 0)
        fuel_in_tank = telemetry.get("fuel_in_tank", 0.0)
        fuel_capacity = telemetry.get("fuel_capacity", 100.0)

        fuel_info = strategy.get("fuel", {})
        estimated_laps_remaining = fuel_info.get("estimated_laps_remaining", 0.0)

        pit_window = strategy.get("pit_window", {})
        pit_window_open = pit_window.get("pit_window_open", False)

        gap_ahead = telemetry.get("gap_ahead", 99.0)
        gap_behind = telemetry.get("gap_behind", 99.0)

        # Evaluar si las temperaturas de gomas están en rango seguro (ej: 70°C a 105°C)
        fl_temp = telemetry.get("tyre_temp_fl", 90.0)
        fr_temp = telemetry.get("tyre_temp_fr", 90.0)
        rl_temp = telemetry.get("tyre_temp_rl", 90.0)
        rr_temp = telemetry.get("tyre_temp_rr", 90.0)
        tyre_temps_ok = all(70.0 <= t <= 105.0 for t in [fl_temp, fr_temp, rl_temp, rr_temp])

        # Registrar combustible histórico
        last_lap_consumption = fuel_info.get("fuel_rate_trend", 0.0)
        if last_lap_consumption > 0:
            self._fuel_history.append(last_lap_consumption)
            if len(self._fuel_history) > 10:
                self._fuel_history.pop(0)

        # 2. Construir snapshot FAST
        self._fast = {
            "phase": phase,
            "lap": lap,
            "fuel_in_tank": round(fuel_in_tank, 2),
            "fuel_capacity": round(fuel_capacity, 2),
            "estimated_laps_remaining": round(estimated_laps_remaining, 2),
            "pit_window_open": pit_window_open,
            "gap_ahead": round(gap_ahead, 2),
            "gap_behind": round(gap_behind, 2),
            "tyre_temps_ok": tyre_temps_ok,
            "speed": telemetry.get("speed", 0.0),
            "track_grip_level": telemetry.get("track_grip_level", 0),
            "cloud_coverage": telemetry.get("cloud_coverage", 0),
            "raining": telemetry.get("raining", 0.0),
        }

        # 3. Construir snapshot STANDARD
        # Historial y tendencias de consumo
        fuel_rate_trend = (
            round(sum(self._fuel_history[-3:]) / max(1, len(self._fuel_history[-3:])), 3) if self._fuel_history else 0.0
        )

        tyre_compound = telemetry.get("tyre_compound", "Medium")
        wear_fl = telemetry.get("tyre_wear_fl", 0.0)
        wear_fr = telemetry.get("tyre_wear_fr", 0.0)
        wear_rl = telemetry.get("tyre_wear_rl", 0.0)
        wear_rr = telemetry.get("tyre_wear_rr", 0.0)
        tyre_wear_current = round((wear_fl + wear_fr + wear_rl + wear_rr) / 4.0, 1)

        # Registrar desgaste promedio
        self._tyre_deg_history.append(tyre_wear_current)
        if len(self._tyre_deg_history) > 10:
            self._tyre_deg_history.pop(0)

        # Tendencia de degradación en las últimas 3 vueltas
        if len(self._tyre_deg_history) >= 2:
            tyre_deg_trend = round(
                self._tyre_deg_history[-1] - self._tyre_deg_history[-max(2, len(self._tyre_deg_history[-3:]))], 2
            )
        else:
            tyre_deg_trend = 0.0

        # Lifespan proyectado de gomas
        tyre_lifespan_laps = int((100.0 - tyre_wear_current) / max(0.5, tyre_deg_trend)) if tyre_deg_trend > 0 else 30

        pit_window_optimal_lap = pit_window.get("optimal_pit_lap", 0)
        pit_loss_time = strategy.get("pit_loss_time", 25.0)

        # Undercut / overcut potencial
        undercut_available = gap_behind < 2.0 and pit_window_open
        overcut_available = gap_ahead < 2.0 and pit_window_open

        # Competidores alrededor
        competitors = telemetry.get("competitors", [])
        my_position = telemetry.get("standing_position", 1)

        sorted_comps = (
            sorted(competitors, key=lambda c: c.get("standing_position", 99)) if isinstance(competitors, list) else []
        )

        comps_ahead = [
            c.get("driver_name", "Driver") for c in sorted_comps if c.get("standing_position", 99) < my_position
        ]
        comps_behind = [
            c.get("driver_name", "Driver") for c in sorted_comps if c.get("standing_position", 99) > my_position
        ]

        competitors_ahead = comps_ahead[-3:] if comps_ahead else []
        competitors_behind = comps_behind[:3] if comps_behind else []

        battery_charge = telemetry.get("battery_charge", 100.0)
        self._battery_history.append(battery_charge)
        if len(self._battery_history) > 10:
            self._battery_history.pop(0)

        if len(self._battery_history) >= 2:
            battery_net_trend = round(
                self._battery_history[-1] - self._battery_history[-max(2, len(self._battery_history[-3:]))], 2
            )
        else:
            battery_net_trend = 0.0

        self._standard = copy.deepcopy(self._fast)
        self._standard.update(
            {
                "fuel_rate_trend": fuel_rate_trend,
                "tyre_compound": tyre_compound,
                "tyre_wear_current": tyre_wear_current,
                "tyre_deg_trend": tyre_deg_trend,
                "tyre_lifespan_laps": tyre_lifespan_laps,
                "pit_window_optimal_lap": pit_window_optimal_lap,
                "pit_loss_time": round(pit_loss_time, 2),
                "undercut_available": undercut_available,
                "overcut_available": overcut_available,
                "competitors_ahead": competitors_ahead,
                "competitors_behind": competitors_behind,
                "battery_charge": round(battery_charge, 2),
                "battery_net_trend": battery_net_trend,
            }
        )

        # 4. Construir snapshot DEEP
        finish_criteria = session.get("finish_criteria", "TIME_LIMIT")

        weather_list = session.get("weather_forecast", [])
        weather_forecast = weather_list[:3] if isinstance(weather_list, list) else []

        # Lluvia prevista si la probabilidad en alguno de los primeros slots es > 20%
        rain_expected = any(
            float(slot.get("WNV_RAIN_CHANCE", 0.0)) > 20.0 for slot in weather_forecast if isinstance(slot, dict)
        )

        damage = {
            "aero": telemetry.get("damage_aero", 0.0),
            "brake_wear": round(
                (
                    telemetry.get("brake_wear_fl", 0.0)
                    + telemetry.get("brake_wear_fr", 0.0)
                    + telemetry.get("brake_wear_rl", 0.0)
                    + telemetry.get("brake_wear_rr", 0.0)
                )
                / 4.0,
                2,
            ),
            "suspension": telemetry.get("suspension_damage", 0.0),
        }

        setup = {"rear_wing": telemetry.get("rear_wing", 2), "brake_bias": round(telemetry.get("brake_bias", 55.0), 2)}

        self._deep = copy.deepcopy(self._standard)
        self._deep.update(
            {
                "finish_criteria": finish_criteria,
                "weather_forecast": weather_forecast,
                "rain_expected": rain_expected,
                "damage": damage,
                "setup": setup,
                "historical_consumption": [round(f, 3) for f in self._fuel_history],
            }
        )

        # Registrar consumo en HistoryStore persistente si está disponible
        if self._history_store is not None and last_lap_consumption > 0:
            lap_time = telemetry.get("lap_time_previous", 0.0)
            self._history_store.record_lap(
                lap=lap,
                fuel_used=last_lap_consumption,
                fuel_remaining=fuel_in_tank,
                lap_time=lap_time,
            )

    def snapshot(self, tier: str) -> dict:
        """Devuelve una copia del diccionario correspondiente al tier solicitado."""
        tier_upper = tier.upper()
        if tier_upper == "FAST":
            return copy.deepcopy(self._fast)
        elif tier_upper == "STANDARD":
            return copy.deepcopy(self._standard)
        else:
            return copy.deepcopy(self._deep)

    def update_realtime(self, telemetry: dict, strategy: dict) -> None:
        """Actualiza campos volátiles en los 3 snapshots sin esperar a completar vuelta.

        Necesario para que el ticker tenga datos frescos entre cruces de meta.
        """
        speed = telemetry.get("speed", 0.0)
        track_grip_level = telemetry.get("track_grip_level", 0)
        cloud_coverage = telemetry.get("cloud_coverage", 0)
        raining = telemetry.get("raining", 0.0)
        gap_ahead = telemetry.get("gap_ahead", 99.0)
        gap_behind = telemetry.get("gap_behind", 99.0)
        brake_wear = round(
            (
                telemetry.get("brake_wear_fl", 0.0)
                + telemetry.get("brake_wear_fr", 0.0)
                + telemetry.get("brake_wear_rl", 0.0)
                + telemetry.get("brake_wear_rr", 0.0)
            )
            / 4.0,
            2,
        )

        for snap in (self._fast, self._standard, self._deep):
            snap["speed"] = speed
            snap["track_grip_level"] = track_grip_level
            snap["cloud_coverage"] = cloud_coverage
            snap["raining"] = raining
            snap["gap_ahead"] = gap_ahead
            snap["gap_behind"] = gap_behind
            # Only update deep's damage dict if it already exists
            if "damage" in snap:
                snap["damage"]["brake_wear"] = brake_wear
