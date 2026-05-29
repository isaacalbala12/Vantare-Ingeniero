from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from src.intelligence.events.base_event import RaceEvent
from src.models.messages import AlertMessage

logger = logging.getLogger("vantare.lap_times")


class LapTimesEvent(RaceEvent):
    """Eventos de vueltas, sectores, ritmo y consistencia.

    Parámetros (sobrescribibles):
        goodLapPercent: float = 0.3
        consistencyLimit: float = 0.5
        windowSize: int = 5
    """

    def __init__(self, broadcast_callback=None, **kwargs: Any) -> None:
        super().__init__(broadcast_callback=broadcast_callback)
        self.good_lap_percent: float = kwargs.get("goodLapPercent", 0.3)
        self.consistency_limit: float = kwargs.get("consistencyLimit", 0.5)
        self.window_size: int = kwargs.get("windowSize", 5)

        # Historiales (estado interno)
        self._last_lap_times: List[float] = []
        self._last_sectors: Dict[str, Optional[float]] = {
            "sector1": None,
            "sector2": None,
            "sector3": None,
        }
        self._best_lap: float = 0.0
        self._best_lap_in_race: float = 0.0
        self._sector_best: Dict[str, float] = {
            "sector1": 0.0,
            "sector2": 0.0,
            "sector3": 0.0,
        }
        self._last_lap_rating: str = ""
        self._fired_personal_best: bool = False
        self._fired_best_in_race: bool = False
        self._last_lap_number: int = 0

        self._cooldowns: Dict[str, float] = {
            "personal_best": 0.0,
            "best_in_race": 0.0,
            "pace": 0.0,
            "consistency": 0.0,
            "improving": 0.0,
            "worsening": 0.0,
            "sector_delta": 0.0,
        }

    # ------------------------------------------------------------------ #
    # Helpers públicos
    # ------------------------------------------------------------------ #
    def reset_session(self) -> None:
        self._last_fired.clear()
        self._fired_in_tick.clear()
        self._last_lap_times = []
        self._last_sectors = {"sector1": None, "sector2": None, "sector3": None}
        self._best_lap = 0.0
        self._best_lap_in_race = 0.0
        self._sector_best = {"sector1": 0.0, "sector2": 0.0, "sector3": 0.0}
        self._last_lap_rating = ""
        self._fired_personal_best = False
        self._fired_best_in_race = False
        self._last_lap_number = 0
        self._cooldowns = {
            "personal_best": 0.0,
            "best_in_race": 0.0,
            "pace": 0.0,
            "consistency": 0.0,
            "improving": 0.0,
            "worsening": 0.0,
            "sector_delta": 0.0,
        }

    # ------------------------------------------------------------------ #
    # evaluate
    # ------------------------------------------------------------------ #
    def evaluate(self, state: Dict[str, Any]) -> List[AlertMessage]:
        alerts: List[AlertMessage] = []
        self.reset_tick()

        if not state:
            return alerts

        lap_number: int = int(state.get("lap_number", 0) or 0)
        is_new_lap: bool = bool(state.get("is_new_lap", False))
        lap_time_previous: float = float(state.get("lap_time_previous", 0.0) or 0.0)
        lap_time_best: float = float(state.get("lap_time_best", 0.0) or 0.0)

        sector1_time: Optional[float] = state.get("sector1_time")
        sector2_time: Optional[float] = state.get("sector2_time")
        sector3_time: Optional[float] = state.get("sector3_time")

        # Detectar nueva vuelta completada
        if is_new_lap and lap_number > 0 and lap_number != self._last_lap_number:
            self._process_lap_completed(
                lap_number=lap_number,
                lap_time=lap_time_previous,
                sector1_time=sector1_time,
                sector2_time=sector2_time,
                sector3_time=sector3_time,
                alerts=alerts,
            )
            self._last_lap_number = lap_number

        # Actualizar mejor vuelta global conocida (aunque no sea nueva vuelta)
        if lap_time_best > 0 and lap_time_best < self._best_lap or (self._best_lap == 0.0 and lap_time_best > 0):
            self._best_lap = lap_time_best

        # Pace / consistencia cada tick (no solo en nueva vuelta)
        if self._best_lap > 0 and lap_time_previous > 0:
            self._evaluate_pace(lap_time_previous, alerts)
            self._evaluate_consistency(alerts)
            self._evaluate_trend(alerts)

        # Sectores (cuando hay datos nuevos)
        if sector1_time is not None:
            self._evaluate_sector_delta("sector1", sector1_time, alerts)
        if sector2_time is not None:
            self._evaluate_sector_delta("sector2", sector2_time, alerts)
        if sector3_time is not None:
            self._evaluate_sector_delta("sector3", sector3_time, alerts)

        return alerts

    # ------------------------------------------------------------------ #
    # Lógica de vuelta completada
    # ------------------------------------------------------------------ #
    def _process_lap_completed(
        self,
        lap_number: int,
        lap_time: float,
        sector1_time: Optional[float],
        sector2_time: Optional[float],
        sector3_time: Optional[float],
        alerts: List[AlertMessage],
    ) -> None:
        if lap_time <= 0:
            return

        # Historial de vueltas
        self._last_lap_times.append(lap_time)
        if len(self._last_lap_times) > self.window_size:
            self._last_lap_times = self._last_lap_times[-self.window_size :]

        # Mejor vuelta personal
        if lap_time < self._best_lap or self._best_lap == 0.0:
            self._best_lap = lap_time
            if not self._fired_personal_best:
                self._fired_personal_best = True
                if self.can_fire("personal_best", self._cooldowns.get("personal_best", 0.0)):
                    self._cooldowns["personal_best"] = 60.0
                    alerts.append(
                        self._create_alert(
                            message=f"¡Nueva mejor vuelta personal! {lap_time:.3f}s",
                            severity="HIGH",
                            audio_priority=2,
                            ttl=10,
                            dismissable=True,
                            category="lap_times",
                            payload={"lap_time": lap_time, "lap_number": lap_number},
                        )
                    )

        # Mejor vuelta en carrera
        if lap_time < self._best_lap_in_race or self._best_lap_in_race == 0.0:
            self._best_lap_in_race = lap_time
            if not self._fired_best_in_race:
                self._fired_best_in_race = True
                if self.can_fire("best_in_race", self._cooldowns.get("best_in_race", 0.0)):
                    self._cooldowns["best_in_race"] = 60.0
                    alerts.append(
                        self._create_alert(
                            message=f"¡Mejor vuelta de la carrera! {lap_time:.3f}s",
                            severity="HIGH",
                            audio_priority=2,
                            ttl=10,
                            dismissable=True,
                            category="lap_times",
                            payload={"lap_time": lap_time, "lap_number": lap_number},
                        )
                    )

        # Mejores sectores
        if sector1_time is not None and (sector1_time < self._sector_best["sector1"] or self._sector_best["sector1"] == 0.0):
            self._sector_best["sector1"] = sector1_time
        if sector2_time is not None and (sector2_time < self._sector_best["sector2"] or self._sector_best["sector2"] == 0.0):
            self._sector_best["sector2"] = sector2_time
        if sector3_time is not None and (sector3_time < self._sector_best["sector3"] or self._sector_best["sector3"] == 0.0):
            self._sector_best["sector3"] = sector3_time

        # Buena vuelta
        if self._best_lap > 0:
            threshold = self._best_lap * (1.0 + self.good_lap_percent / 100.0)
            if lap_time < threshold:
                if self.can_fire("pace", self._cooldowns.get("pace", 0.0)):
                    self._cooldowns["pace"] = 8.0
                    alerts.append(
                        self._create_alert(
                            message=f"Buena vuelta: {lap_time:.3f}s",
                            severity="INFO",
                            audio_priority=1,
                            ttl=6,
                            dismissable=True,
                            category="lap_times",
                            payload={"lap_time": lap_time, "best_lap": self._best_lap},
                        )
                    )

    # ------------------------------------------------------------------ #
    # Pace
    # ------------------------------------------------------------------ #
    def _evaluate_pace(self, lap_time: float, alerts: List[AlertMessage]) -> None:
        if self._best_lap <= 0:
            return
        ratio = lap_time / self._best_lap
        if ratio <= 1.001:
            rating = "setting_pace"
            message = f"Ritmo: marcando el paso ({lap_time:.3f}s)"
            severity = "HIGH"
            audio_priority = 2
            ttl = 8
        elif ratio <= 1.005:
            rating = "close_to_pace"
            message = f"Ritmo: cerca del paso ({lap_time:.3f}s)"
            severity = "INFO"
            audio_priority = 1
            ttl = 6
        elif ratio <= 1.01:
            rating = "meh"
            message = f"Ritmo: fuera de paso ({lap_time:.3f}s)"
            severity = "INFO"
            audio_priority = 1
            ttl = 5
        else:
            rating = "bad"
            message = f"Ritmo: mal ritmo ({lap_time:.3f}s)"
            severity = "WARNING"
            audio_priority = 2
            ttl = 8

        if rating != self._last_lap_rating:
            self._last_lap_rating = rating
            if self.can_fire("pace", self._cooldowns.get("pace", 0.0)):
                self._cooldowns["pace"] = 6.0
                alerts.append(
                    self._create_alert(
                        message=message,
                        severity=severity,
                        audio_priority=audio_priority,
                        ttl=ttl,
                        dismissable=True,
                        category="lap_times",
                        payload={"rating": rating, "lap_time": lap_time, "best_lap": self._best_lap},
                    )
                )

    # ------------------------------------------------------------------ #
    # Consistencia
    # ------------------------------------------------------------------ #
    def _evaluate_consistency(self, alerts: List[AlertMessage]) -> None:
        if len(self._last_lap_times) < self.window_size:
            return
        recent = self._last_lap_times[-self.window_size :]
        best = min(recent)
        if best <= 0:
            return
        worst = max(recent)
        deviation = (worst - best) / best * 100.0
        if deviation <= self.consistency_limit:
            if self.can_fire("consistency", self._cooldowns.get("consistency", 0.0)):
                self._cooldowns["consistency"] = 12.0
                alerts.append(
                    self._create_alert(
                        message=f"Vueltas consistentes (Δ {deviation:.2f}% en últimas {self.window_size} vueltas)",
                        severity="INFO",
                        audio_priority=1,
                        ttl=6,
                        dismissable=True,
                        category="lap_times",
                        payload={"deviation": deviation, "window": self.window_size},
                    )
                )

    # ------------------------------------------------------------------ #
    # Tendencia (mejorando / empeorando)
    # ------------------------------------------------------------------ #
    def _evaluate_trend(self, alerts: List[AlertMessage]) -> None:
        if len(self._last_lap_times) < 3:
            return
        times = self._last_lap_times[-self.window_size :]
        # Regresión lineal simple sobre índices
        n = len(times)
        x_mean = (n - 1) / 2.0
        y_mean = sum(times) / n
        num = sum((i - x_mean) * (t - y_mean) for i, t in enumerate(times))
        den = sum((i - x_mean) ** 2 for i in range(n))
        if den == 0:
            return
        slope = num / den  # segundos por vuelta
        threshold = 0.05  # 50ms por vuelta
        if slope < -threshold:
            if self.can_fire("improving", self._cooldowns.get("improving", 0.0)):
                self._cooldowns["improving"] = 15.0
                alerts.append(
                    self._create_alert(
                        message="Tendencia: mejorando tiempos por vuelta.",
                        severity="INFO",
                        audio_priority=1,
                        ttl=6,
                        dismissable=True,
                        category="lap_times",
                        payload={"slope": slope},
                    )
                )
        elif slope > threshold:
            if self.can_fire("worsening", self._cooldowns.get("worsening", 0.0)):
                self._cooldowns["worsening"] = 15.0
                alerts.append(
                    self._create_alert(
                        message="Tendencia: empeorando tiempos por vuelta.",
                        severity="WARNING",
                        audio_priority=2,
                        ttl=6,
                        dismissable=True,
                        category="lap_times",
                        payload={"slope": slope},
                    )
                )

    # ------------------------------------------------------------------ #
    # Sectores vs mejor personal
    # ------------------------------------------------------------------ #
    def _evaluate_sector_delta(self, sector: str, sector_time: float, alerts: List[AlertMessage]) -> None:
        best = self._sector_best.get(sector, 0.0)
        if best <= 0 or sector_time <= 0:
            return
        delta = sector_time - best
        if delta < 0:
            # Nuevo mejor sector personal
            self._sector_best[sector] = sector_time
            return
        if delta > 2.0:
            # Outlier: no reportar
            return
        if self.can_fire("sector_delta", self._cooldowns.get("sector_delta", 0.0)):
            self._cooldowns["sector_delta"] = 6.0
            severity = "INFO"
            audio_priority = 1
            if delta < 0.05:
                message = f"{sector}: rápido ({delta:+.3f}s)"
            elif delta < 0.15:
                message = f"{sector}: una décima fuera ({delta:+.3f}s)"
            elif delta < 0.25:
                message = f"{sector}: dos décimas fuera ({delta:+.3f}s)"
            elif delta < 1.05:
                message = f"{sector}: un segundo fuera ({delta:+.3f}s)"
            else:
                message = f"{sector}: {delta:.2f}s fuera del paso"
                severity = "WARNING"
                audio_priority = 2
            alerts.append(
                self._create_alert(
                    message=message,
                    severity=severity,
                    audio_priority=audio_priority,
                    ttl=6,
                    dismissable=True,
                    category="lap_times",
                    payload={"sector": sector, "delta": delta, "sector_time": sector_time, "best": best},
                )
            )

    # ------------------------------------------------------------------ #
    # Helpers de alertas
    # ------------------------------------------------------------------ #
    def _create_alert(
        self,
        message: str,
        severity: str,
        audio_priority: int,
        ttl: int,
        dismissable: bool,
        category: str,
        payload: Dict[str, Any],
    ) -> AlertMessage:
        return AlertMessage(
            event="alert",
            alert_id=str(__import__("uuid").uuid4()),
            category=category,
            message=message,
            audio_priority=str(audio_priority),
            severity=severity,
            ttl=ttl,
            dismissable=dismissable,
            payload={
                "severity": severity,
                "ttl": ttl,
                "dismissable": dismissable,
                **payload,
            },
        )
