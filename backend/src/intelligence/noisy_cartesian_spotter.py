"""Spotter cartesiano — detecta coches alrededor del jugador.

Usa coordenadas mundiales X+Z + yaw del piloto. Sin LLM, sin red.
"""
import math
import time
import logging
from typing import List, Optional, Tuple, Dict, Any

from src.intelligence.coordinate_math import aligned_xz
from src.intelligence.spotter_messages import (
    CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
    THREE_WIDE, STILL_THERE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT,
)

logger = logging.getLogger("vantare.spotter")

# Mapa de mensaje lógico -> ruta de audio
_MESSAGE_TO_AUDIO = {
    "car_left": CAR_LEFT,
    "car_right": CAR_RIGHT,
    "clear_left": CLEAR_LEFT,
    "clear_right": CLEAR_RIGHT,
    "clear_all_round": CLEAR_ALL_ROUND,
    "three_wide": THREE_WIDE,
    "still_there": STILL_THERE,
    "three_wide_on_left": THREE_WIDE_ON_LEFT,
    "three_wide_on_right": THREE_WIDE_ON_RIGHT,
}


class NoisyCartesianCoordinateSpotter:
    """Spotter cartesiano. Inspirado en NoisyCartesianCoordinateSpotter.cs de CrewChiefV4.

    Args:
        ap: AudioPlayer o MockAudioPlayer (interfaz con play_spotter_message)
        zone: Radio de detección en metros (default 20m)
        min_speed: Velocidad mínima del jugador para activar (m/s, default 10)
        max_close: Velocidad máxima relativa para considerar "cerca" (m/s, default 50)
        clear_gap: Gap lateral para considerar "limpio" (m, default 1.0)
        car_len: Largo del coche (m, default 4.5)
        car_w: Ancho del coche (m, default 1.8)
        behind_extra: Margen extra detrás (m, default 0.4)
        max_per_side: Máximo de rivales contados por lado (default 3)
        clear_delay: Delay para decir "clear" (s, default 0.5)
        repeat_freq: Frecuencia de "still there" (s, default 3.0)
        to_3wide: Delay para decir "three wide" (s, default 0.5)
    """

    def __init__(self, ap=None, **kwargs):
        self.zone = kwargs.get("zone", 20.0)
        self.min_speed = kwargs.get("min_speed", 10.0)
        self.max_close = kwargs.get("max_close", 50.0)
        self.clear_gap = kwargs.get("clear_gap", 1.0)
        self.car_len = kwargs.get("car_len", 4.5)
        self.car_w = kwargs.get("car_w", 1.8)
        self.behind_extra = kwargs.get("behind_extra", 0.4)
        self.max_per_side = kwargs.get("max_per_side", 3)
        self.clear_delay = kwargs.get("clear_delay", 0.5)
        self.repeat_freq = kwargs.get("repeat_freq", 3.0)
        self.to_3wide = kwargs.get("to_3wide", 0.5)
        self.ap = ap
        # Estado
        self.cl = 0  # current count left
        self.cr = 0  # current count right
        self.clp = 0  # previous count left
        self.crp = 0  # previous count right
        self.has_overlap = False
        self._v: Dict[int, dict] = {}  # tracked rivals: {oid: {x,z,t,xs,zs}}
        self._next: Optional[str] = None  # pending message name
        self._due: float = 0.0  # when to play _next

    def trigger(self, st: dict, opps: List[dict], now: Optional[float] = None):
        """Evalúa el estado y emite mensajes del spotter.

        Args:
            st: dict con world_x, world_z, rotation_yaw, speed_ms
            opps: lista de dicts con id, world_x, world_z, speed
            now: timestamp (default time.time())
        """
        if now is None:
            now = time.time()
        px = st.get("world_x", 0.0)
        pz = st.get("world_z", 0.0)
        yaw = st.get("rotation_yaw", 0.0)
        sp = st.get("speed_ms", 0.0)
        # Si el piloto está parado o en origen, no activar
        if (px == 0 and pz == 0) or sp < self.min_speed:
            if self.clp > 0 or self.crp > 0:
                self.clp = self.crp = 0
            return

        cl, cr = 0, 0
        aids = set()  # rivales vistos este tick
        for o in opps:
            oid = o.get("id", 0)
            ox = o.get("world_x", 0.0)
            oz = o.get("world_z", 0.0)
            os = o.get("speed", 0.0)
            if ox == 0 and oz == 0:
                continue
            aids.add(oid)
            # Filtrar por zona
            if abs(ox - px) > self.zone or abs(oz - pz) > self.zone:
                self._v.pop(oid, None)
                continue
            is_close = self._check_v(oid, ox, oz, os, now)
            side, _ = self._side(yaw, px, pz, ox, oz, is_close)
            if side == "l":
                if cl < self.max_per_side:
                    cl += 1
            elif side == "r":
                if cr < self.max_per_side:
                    cr += 1
            # Salir si ambos lados están al máximo
            if cl >= self.max_per_side and cr >= self.max_per_side:
                break
        # Limpiar rivales que ya no se ven
        for oid in list(self._v.keys()):
            if oid not in aids:
                self._v.pop(oid, None)

        self._next_msg(cl, cr, now)
        self._play(cl, cr, now)
        # Actualizar previous = current (usar locales, no self.cl que es el anterior)
        self.clp, self.crp = cl, cr
        self.cl, self.cr = cl, cr
        self.has_overlap = cl > 0 or cr > 0

    def _check_v(self, oid: int, x: float, z: float, sp: float, now: float) -> bool:
        """Determina si un rival está cerca (velocidad < max_close)."""
        if sp > 0:
            return abs(sp - self.min_speed) < self.max_close
        p = self._v.get(oid)
        if not p:
            self._v[oid] = {"x": x, "z": z, "t": now, "xs": 0, "zs": 0}
            return True
        dt = now - p["t"]
        if dt >= 0.2:
            p["xs"] = (x - p["x"]) / dt if dt > 0 else 0
            p["zs"] = (z - p["z"]) / dt if dt > 0 else 0
            p["x"] = x
            p["z"] = z
            p["t"] = now
        vs = math.sqrt(p.get("xs", 0) ** 2 + p.get("zs", 0) ** 2)
        return vs < self.max_close

    def _side(self, y: float, px: float, pz: float, ox: float, oz: float, in_range: bool) -> Tuple[Optional[str], float]:
        """Determina si un rival está a izquierda ('l') o derecha ('r')."""
        ax, az = aligned_xz(y, px, pz, ox, oz)
        if abs(ax) >= self.zone:
            return (None, -1.0)
        # ax >= 0: derecha, ax < 0: izquierda
        if ax >= 0:
            # Lado derecho
            if self.crp > 0:
                if abs(az) < self.car_len + self.clear_gap:
                    return ("r", abs(ax))
            elif ((az < 0 and -az < self.car_len) or
                  (az > 0 and az < self.car_len + self.behind_extra)) and \
                 abs(ax) > self.car_w and in_range:
                return ("r", abs(ax))
        else:
            # Lado izquierdo
            if self.clp > 0:
                if abs(az) < self.car_len + self.clear_gap:
                    return ("l", abs(ax))
            elif ((az < 0 and -az < self.car_len) or
                  (az > 0 and az < self.car_len + self.behind_extra)) and \
                 abs(ax) > self.car_w and in_range:
                return ("l", abs(ax))
        return (None, -1.0)

    def _next_msg(self, l: int, r: int, now: float):
        """Decide cuál es el siguiente mensaje a reproducir (con su _due).

        Reglas:
        - Si la SITUACIÓN CAMBIÓ (clear cuando había coche), sobrescribe _next
          y reproduce inmediatamente (clear es importante)
        - Si la situación es estable, mantiene still_there
        """
        # Limpiezas: algo ocupado antes, ahora vacío
        if l == 0 and r == 0 and (self.clp > 0 or self.crp > 0):
            if self.clp > 0 and self.crp > 0:
                self._next = "clear_all_round"
            elif self.clp > 0:
                self._next = "clear_left"
            else:
                self._next = "clear_right"
            self._due = now + self.clear_delay
            return
        # Apariciones nuevas (siempre sobrescriben _next)
        if l > 0 and r > 0 and (self.clp == 0 or self.crp == 0):
            self._next = "three_wide"
            self._due = now
        elif l > 0 and r == 0 and self.clp == 0:
            if l > 1:
                self._next = "three_wide_on_right"
                self._due = now
            else:
                self._next = "car_left"
                self._due = now
        elif l == 0 and r > 0 and self.crp == 0:
            if r > 1:
                self._next = "three_wide_on_left"
                self._due = now
            else:
                self._next = "car_right"
                self._due = now
        elif l > 1 and r == 0 and self.clp == 1:
            self._next = "three_wide_on_right"
            self._due = now + self.to_3wide
        elif l == 0 and r > 1 and self.crp == 1:
            self._next = "three_wide_on_left"
            self._due = now + self.to_3wide
        # Si nada cambia (sigue habiendo coches), _next se mantiene (still_there)

    def _play(self, l: int, r: int, now: float):
        """Reproduce el mensaje pendiente si es tiempo."""
        if not self._next:
            return
        # Si el mensaje ya no aplica, descartarlo
        if (self._next == "car_left" and l == 0) or \
           (self._next == "car_right" and r == 0) or \
           (self._next == "three_wide" and (r == 0 or l == 0)):
            self._next = None
            self._due = 0.0
            return
        # Si no es tiempo todavía (still_there esperando), no hacer nada
        if now < self._due:
            return
        if self._next in _MESSAGE_TO_AUDIO:
            audio_path = _MESSAGE_TO_AUDIO[self._next]
            if self.ap is not None:
                try:
                    self.ap.play_spotter_message(audio_path, keep_channel=True)
                except AttributeError:
                    # Fallback: si el audio_player no tiene play_spotter_message,
                    # usar play() normal
                    self.ap.play(audio_path, priority=20)  # SPOTTER priority
        # Después de "car left/right" o "three wide": programar "still there"
        if self._next in ("car_left", "car_right", "three_wide",
                          "three_wide_on_left", "three_wide_on_right"):
            self._next = "still_there"
            self._due = now + self.repeat_freq
        elif self._next in ("clear_left", "clear_right", "clear_all_round"):
            self._next = None
            self._due = 0.0

    def clear_state(self):
        """Limpia todo el estado (llamar entre sesiones)."""
        self.cl = self.cr = self.clp = self.crp = 0
        self.has_overlap = False
        self._v.clear()
        self._next = None
        self._due = 0.0

    def get_grid_side(self, yaw: float, px: float, pz: float, opps: List[dict]) -> str:
        """Determina si el piloto está a la izquierda o derecha de la parrilla."""
        for o in opps[:5]:
            ax, _ = aligned_xz(yaw, px, pz, o.get("world_x", 0), o.get("world_z", 0))
            if ax < -2:
                return "LEFT"
            if ax > 2:
                return "RIGHT"
        return "UNKNOWN"
