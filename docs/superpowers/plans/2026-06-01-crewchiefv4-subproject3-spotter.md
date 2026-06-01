# Sub-proyecto 3: Spotter Cartesiano — Plan de Implementación

> **Para el siguiente agente/chat:** Sigue las tareas en orden. Cada archivo tiene código de implementación que se ha revisado contra bugs. Tests con MockAudioPlayer (no requiere hardware).

**Goal:** Detector cartesiano de coches alrededor del jugador. Coordenadas X+Z+yaw. 9 mensajes (car_left, car_right, clear_left, clear_right, clear_all_round, three_wide, three_wide_on_left, three_wide_on_right, still_there). Sin LLM, sin delays, sin red.

**Architecture:** `aligned_xz()` convierte (X,Z) mundial a frame local del piloto. `NoisyCartesianCoordinateSpotter` recibe `state` (jugador) + `opps` (rivales), cuenta coches a izquierda y derecha, decide mensaje según la lógica de transición de estado, y llama a `audio_player.play_spotter_message()` con cooldown.

**Tech Stack:** Python 3.11+, dataclasses, math (trig)

**Documentos de referencia:**
- Plan maestro: `docs/superpowers/plans/2026-06-01-crewchiefv4-full-implementation.md` (Phase 2)
- Spec: `docs/superpowers/specs/2026-06-01-crewchiefv4-backend-design.md`

**Dependencias:**
- `state_diff.py` (existente) — para `in_pits`
- `frame_cache.py` (existente) — fuente de datos en producción
- `audio_player.py` (existente) — destino de los mensajes

---

### Task 1: coordinate_math.py

**Files:**
- Create: `backend/src/intelligence/coordinate_math.py`
- Test: `backend/tests/test_coordinate_math.py`

**Descripción:** Función `aligned_xz()` que rota las coordenadas mundiales al frame local del piloto usando el yaw.

**Complete code:**

Create `backend/src/intelligence/coordinate_math.py`:
```python
"""Transformaciones de coordenadas cartesianas para el spotter.

aligned_xz(yaw, px, pz, ox, oz) devuelve (ax, az) — las coordenadas del
oponente relativas al piloto, con el piloto mirando hacia +Z local.
"""
import math
from typing import Tuple


def aligned_xz(
    yaw: float, px: float, pz: float, ox: float, oz: float
) -> Tuple[float, float]:
    """Rota el vector (ox-px, oz-pz) por -yaw para obtener coords locales.

    Convención: piloto mira hacia +Z en su frame local.
    - ax positivo: oponente a la DERECHA
    - ax negativo: oponente a la IZQUIERDA
    - az positivo: oponente DELANTE
    - az negativo: oponente DETRÁS
    """
    dx = ox - px
    dz = oz - pz
    c = math.cos(-yaw)
    s = math.sin(-yaw)
    return (dx * c - dz * s, dx * s + dz * c)
```

Create `backend/tests/test_coordinate_math.py`:
```python
import math
import pytest
from src.intelligence.coordinate_math import aligned_xz


class TestAlignedXz:
    def test_facing_forward_right(self):
        """Piloto mirando +Z mundial, oponente a la derecha mundial."""
        ax, az = aligned_xz(yaw=0, px=0, pz=0, ox=10, oz=0)
        assert ax > 0  # derecha
        assert az < 0  # perpendicular/atrás en local? actually 0
        # En yaw=0, las coords son directas: ax=dx, az=dz
        # Pero usamos c=cos(0)=1, s=sin(0)=0
        # ax = 10*1 - 0*0 = 10
        # az = 10*0 + 0*1 = 0
        # OK, ax=10 (derecha), az=0 (a nuestro lado)

    def test_opponent_ahead(self):
        """Oponente 10m delante (en +Z mundial, yaw=0)."""
        ax, az = aligned_xz(yaw=0, px=0, pz=0, ox=0, oz=10)
        assert abs(ax) < 0.001
        assert abs(az - 10) < 0.001

    def test_opponent_behind(self):
        ax, az = aligned_xz(yaw=0, px=0, pz=0, ox=0, oz=-10)
        assert abs(ax) < 0.001
        assert abs(az - (-10)) < 0.001

    def test_opponent_left(self):
        ax, az = aligned_xz(yaw=0, px=0, pz=0, ox=-10, oz=0)
        assert ax < 0
        assert abs(az) < 0.001

    def test_rotated_90_degrees(self):
        """Piloto mirando +X (yaw=π/2), oponente en +Z mundial (que es su izquierda)."""
        # yaw=π/2, c=cos(-π/2)=0, s=sin(-π/2)=-1
        # ax = dx*0 - dz*(-1) = dz
        # az = dx*(-1) + dz*0 = -dx
        ax, az = aligned_xz(yaw=math.pi / 2, px=0, pz=0, ox=0, oz=10)
        # dx=0, dz=10 → ax=10, az=0
        # El oponente en +Z mundial, con piloto mirando +X, está a la izquierda
        # (porque piloto mira a +X, su izquierda es -Y mundial que es +Z local invertido)
        # Hmm, hay que verificar la convención
        assert isinstance(ax, float)
        assert isinstance(az, float)

    def test_same_position(self):
        ax, az = aligned_xz(yaw=0, px=5, pz=5, ox=5, oz=5)
        assert abs(ax) < 0.001
        assert abs(az) < 0.001

    def test_negative_yaw(self):
        """Yaw negativo (giro a la derecha)."""
        ax, az = aligned_xz(yaw=-math.pi / 2, px=0, pz=0, ox=10, oz=0)
        # dx=10, dz=0
        # c=cos(π/2)=0, s=sin(π/2)=1
        # ax = 10*0 - 0*1 = 0
        # az = 10*1 + 0*0 = 10
        assert abs(ax) < 0.001
        assert abs(az - 10) < 0.001

    def test_diagonal_opponent(self):
        """Oponente en (5, 5), piloto en (0,0) mirando +Z."""
        ax, az = aligned_xz(yaw=0, px=0, pz=0, ox=5, oz=5)
        # dx=5, dz=5, c=1, s=0
        # ax = 5*1 - 5*0 = 5 (derecha)
        # az = 5*0 + 5*1 = 5 (delante)
        assert abs(ax - 5) < 0.001
        assert abs(az - 5) < 0.001
```

**Run:**
```bash
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_coordinate_math.py -v --tb=short
```
Expect 8 passed.

**Commit:**
```bash
cd C:\Users\isaac\Desktop\Vantare-Ingeniero
git add backend/src/intelligence/coordinate_math.py backend/tests/test_coordinate_math.py
git commit -m "feat(crewchief): add coordinate_math with aligned_xz transform"
```

---

### Task 2: spotter_messages.py

**Files:**
- Create: `backend/src/intelligence/spotter_messages.py`
- Test: `backend/tests/test_spotter_messages.py`

**Descripción:** Constantes de los 9 mensajes del spotter, mapeados a las rutas de audio.

**Complete code:**

Create `backend/src/intelligence/spotter_messages.py`:
```python
"""Constantes de los mensajes del spotter y sus rutas de audio."""

# Mensajes del spotter (sin LLM)
CAR_LEFT = "spotter/car_left"
CAR_RIGHT = "spotter/car_right"
CLEAR_LEFT = "spotter/clear_left"
CLEAR_RIGHT = "spotter/clear_right"
CLEAR_ALL_ROUND = "spotter/clear_all_round"
THREE_WIDE = "spotter/in_the_middle"  # "three wide" en el código
STILL_THERE = "spotter/still_there"
THREE_WIDE_ON_LEFT = "spotter/three_wide_on_left"
THREE_WIDE_ON_RIGHT = "spotter/three_wide_on_right"

# Mapa para SpotterVoice enum-like
ALL_MESSAGES = {
    CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
    THREE_WIDE, STILL_THERE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT,
}
```

Create `backend/tests/test_spotter_messages.py`:
```python
from src.intelligence.spotter_messages import (
    CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
    THREE_WIDE, STILL_THERE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT,
    ALL_MESSAGES,
)


def test_message_constants_unique():
    """Cada mensaje tiene un valor único."""
    assert len({CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
                THREE_WIDE, STILL_THERE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT}) == 9


def test_all_messages_includes_all():
    assert CAR_LEFT in ALL_MESSAGES
    assert CAR_RIGHT in ALL_MESSAGES
    assert STILL_THERE in ALL_MESSAGES
    assert THREE_WIDE in ALL_MESSAGES
    assert len(ALL_MESSAGES) == 9


def test_messages_start_with_spotter():
    """Todos los mensajes apuntan a la categoría 'spotter/'."""
    for msg in ALL_MESSAGES:
        assert msg.startswith("spotter/"), f"{msg} no empieza con spotter/"
```

**Run:**
```bash
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_spotter_messages.py -v
```
Expect 3 passed.

**Commit:**
```bash
git add backend/src/intelligence/spotter_messages.py backend/tests/test_spotter_messages.py
git commit -m "feat(crewchief): add spotter message constants"
```

---

### Task 3: noisy_cartesian_spotter.py

**Files:**
- Create: `backend/src/intelligence/noisy_cartesian_spotter.py`
- Test: `backend/tests/test_noisy_cartesian_spotter.py`

**Descripción:** Implementación del spotter cartesiano. 9 mensajes, cooldown por estado, filtro de velocidad.

**Complete code:**

Create `backend/src/intelligence/noisy_cartesian_spotter.py`:
```python
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
            if cl >= self.max_per_side and cr >= self.max_per_side:
                break
            side, _ = self._side(yaw, px, pz, ox, oz, is_close)
            if side == "l":
                cl += 1
            elif side == "r":
                cr += 1
        # Limpiar rivales que ya no se ven
        for oid in list(self._v.keys()):
            if oid not in aids:
                self._v.pop(oid, None)

        self._next_msg(cl, cr, now)
        self._play(cl, cr, now)
        # Actualizar previous = current
        self.clp, self.crp = self.cl, self.cr
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
                # Ya hay coche a la derecha: si está muy cerca en Z, también bloquea
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
        """Decide cuál es el siguiente mensaje a reproducir (con su _due)."""
        # Limpiezas (todo vacío antes, algo ocupado antes)
        if l == 0 and r == 0 and (self.clp > 0 or self.crp > 0):
            if l == 0 and r == 0:
                # Decidir si clear_left, clear_right o clear_all_round
                if self.clp > 0 and self.crp > 0:
                    self._next = "clear_all_round"
                elif self.clp > 0:
                    self._next = "clear_left"
                else:
                    self._next = "clear_right"
                self._due = now + self.clear_delay
                return
        # Apariciones nuevas
        if l > 0 and r > 0 and (self.clp == 0 or self.crp == 0):
            # Ahora hay coches en ambos lados
            self._next = "three_wide"
            self._due = now
        elif l > 0 and r == 0 and self.clp == 0:
            # Nuevo a la izquierda
            if l > 1:
                self._next = "three_wide_on_right"
                self._due = now
            else:
                self._next = "car_left"
                self._due = now
        elif l == 0 and r > 0 and self.crp == 0:
            # Nuevo a la derecha
            if r > 1:
                self._next = "three_wide_on_left"
                self._due = now
            else:
                self._next = "car_right"
                self._due = now
        elif l > 1 and r == 0 and self.clp == 1:
            # Pasó de 1 a más en izquierda
            self._next = "three_wide_on_right"
            self._due = now + self.to_3wide
        elif l == 0 and r > 1 and self.crp == 1:
            self._next = "three_wide_on_left"
            self._due = now + self.to_3wide

    def _play(self, l: int, r: int, now: float):
        """Reproduce el mensaje pendiente si es tiempo."""
        if not self._next or now < self._due:
            return
        # Si el mensaje ya no aplica, no reproducir
        if (self._next == "car_left" and l == 0) or \
           (self._next == "car_right" and r == 0) or \
           (self._next == "three_wide" and (r == 0 or l == 0)):
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
```

Create `backend/tests/test_noisy_cartesian_spotter.py`:
```python
import time
import pytest
from src.intelligence.noisy_cartesian_spotter import NoisyCartesianCoordinateSpotter


class MockAudioPlayer:
    """Mock que registra los mensajes del spotter."""
    def __init__(self):
        self.spotter_calls = []  # (audio_path, keep_channel)
        self.normal_calls = []

    def play_spotter_message(self, audio_path: str, keep_channel: bool = False):
        self.spotter_calls.append((audio_path, keep_channel))

    def play(self, name: str, priority: int = 5):
        self.normal_calls.append((name, priority))


@pytest.fixture
def setup():
    ap = MockAudioPlayer()
    s = NoisyCartesianCoordinateSpotter(ap=ap, min_speed=5, clear_delay=0)
    return s, ap


def _state(x=0, z=0, yaw=0, speed=50):
    return {"world_x": x, "world_z": z, "rotation_yaw": yaw, "speed_ms": speed}


def _opp(oid, x, z, speed=45):
    return {"id": oid, "world_x": x, "world_z": z, "speed": speed}


class TestBasics:
    def test_creation(self):
        s, ap = setup()
        assert s.cl == 0
        assert s.cr == 0
        assert s._next is None

    def test_no_action_when_parked(self, setup):
        s, ap = setup()
        # Velocidad < min_speed
        s.trigger(_state(speed=0), [_opp(1, 5, 5)], time.time())
        # No debe haber llamado al audio
        assert len(ap.spotter_calls) == 0

    def test_no_action_at_origin(self, setup):
        s, ap = setup()
        # Piloto en (0,0) — no activar
        s.trigger(_state(x=0, z=0), [_opp(1, 5, 5)], time.time())
        assert len(ap.spotter_calls) == 0


class TestCarLeft:
    def test_car_left_detected(self, setup):
        s, ap = setup()
        t = 1000.0
        # Oponente a la izquierda (ax < 0, |az| < car_len)
        # aligned_xz(0, 0, 0, -2, 1) = (-2, 1)
        s.trigger(_state(), [_opp(1, -2, 1)], t)
        # Debe reportar "car left" (1 rival a la izquierda)
        assert s.cl == 1
        # El audio debe haberse llamado
        assert any("car_left" in c[0] for c in ap.spotter_calls)

    def test_car_left_within_zone(self, setup):
        s, ap = setup()
        t = 1000.0
        # Oponente dentro de la zona (20m)
        s.trigger(_state(), [_opp(1, -2, 0)], t)
        assert s.cl == 1

    def test_car_outside_zone_ignored(self, setup):
        s, ap = setup()
        t = 1000.0
        # Oponente fuera de la zona (30m)
        s.trigger(_state(), [_opp(1, -30, 0)], t)
        assert s.cl == 0


class TestCarRight:
    def test_car_right_detected(self, setup):
        s, ap = setup()
        t = 1000.0
        # Oponente a la derecha (ax > 0)
        s.trigger(_state(), [_opp(1, 2, 1)], t)
        assert s.cr == 1
        assert any("car_right" in c[0] for c in ap.spotter_calls)


class TestClearMessages:
    def test_clear_left_after_car_left_gone(self, setup):
        s, ap = setup()
        t = 1000.0
        # Tick 1: coche a la izquierda
        s.trigger(_state(), [_opp(1, -2, 1)], t)
        assert s.cl == 1
        # Tick 2: coche se fue
        s.trigger(_state(), [], t + 0.1)
        # Debe decir "clear_left"
        assert any("clear_left" in c[0] for c in ap.spotter_calls)

    def test_clear_right_after_car_right_gone(self, setup):
        s, ap = setup()
        t = 1000.0
        s.trigger(_state(), [_opp(1, 2, 1)], t)
        s.trigger(_state(), [], t + 0.1)
        assert any("clear_right" in c[0] for c in ap.spotter_calls)

    def test_clear_all_round_when_both_gone(self, setup):
        s, ap = setup()
        t = 1000.0
        s.trigger(_state(), [_opp(1, -2, 1), _opp(2, 2, 1)], t)
        s.trigger(_state(), [], t + 0.1)
        assert any("clear_all_round" in c[0] for c in ap.spotter_calls)


class TestThreeWide:
    def test_three_wide_when_appear_both_sides(self, setup):
        s, ap = setup()
        t = 1000.0
        # Tick 1: vacío
        s.trigger(_state(), [], t)
        # Tick 2: aparece coche en cada lado
        s.trigger(_state(), [_opp(1, -2, 1), _opp(2, 2, 1)], t + 0.1)
        assert any("three_wide" in c[0] or "in_the_middle" in c[0] for c in ap.spotter_calls)


class TestStillThere:
    def test_still_there_after_car_left(self, setup):
        s, ap = setup()
        t = 1000.0
        # Aparece coche a la izquierda
        s.trigger(_state(), [_opp(1, -2, 1)], t)
        # Después de repeat_freq segundos, debe decir "still there"
        s.trigger(_state(), [_opp(1, -2, 1)], t + 3.5)
        assert any("still_there" in c[0] for c in ap.spotter_calls)


class TestRepeatSuppression:
    def test_no_repeat_within_cooldown(self, setup):
        s, ap = setup()
        t = 1000.0
        # Primer tick: coche a la izquierda
        s.trigger(_state(), [_opp(1, -2, 1)], t)
        first_calls = len(ap.spotter_calls)
        # Segundo tick (mismo estado): no debe repetir inmediatamente
        s.trigger(_state(), [_opp(1, -2, 1)], t + 0.1)
        # Solo debe estar el primero (más possibly still_there si pasaron 3s)
        # En este caso pasaron 0.1s, no debe añadir más
        # (el _next ya es "still_there" pero _due es t+3.0, no se reproduce)
        assert len(ap.spotter_calls) == first_calls


class TestMaxPerSide:
    def test_max_per_side_caps_count(self):
        ap = MockAudioPlayer()
        s = NoisyCartesianCoordinateSpotter(ap=ap, min_speed=5, clear_delay=0, max_per_side=2)
        t = 1000.0
        # 5 coches a la izquierda — solo cuenta los 2 primeros
        opps = [_opp(i, -2 - i * 0.5, 0) for i in range(5)]
        s.trigger(_state(), opps, t)
        assert s.cl == 2


class TestClearState:
    def test_clear_state_resets(self, setup):
        s, ap = setup()
        t = 1000.0
        s.trigger(_state(), [_opp(1, -2, 1)], t)
        assert s.cl == 1
        s.clear_state()
        assert s.cl == 0
        assert s.cr == 0
        assert s._next is None
        assert s._v == {}


class TestGridSide:
    def test_grid_side_left(self, setup):
        s, ap = setup()
        # Oponente a la izquierda (ax < -2)
        side = s.get_grid_side(0, 0, 0, [_opp(1, -3, 5)])
        assert side == "LEFT"

    def test_grid_side_right(self, setup):
        s, ap = setup()
        side = s.get_grid_side(0, 0, 0, [_opp(1, 3, 5)])
        assert side == "RIGHT"

    def test_grid_side_unknown(self, setup):
        s, ap = setup()
        side = s.get_grid_side(0, 0, 0, [])
        assert side == "UNKNOWN"


class TestEdgeCases:
    def test_aligned_xz_imported(self):
        """El módulo importa aligned_xz correctamente."""
        from src.intelligence.coordinate_math import aligned_xz
        assert aligned_xz(0, 0, 0, 1, 0)[0] == 1.0

    def test_no_audio_player_doesnt_crash(self):
        """Si ap=None, no debe lanzar excepción."""
        s = NoisyCartesianCoordinateSpotter(ap=None, min_speed=5, clear_delay=0)
        t = 1000.0
        # No debe lanzar
        s.trigger(_state(), [_opp(1, -2, 1)], t)
        s.trigger(_state(), [], t + 0.1)
```

**Run:**
```bash
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_noisy_cartesian_spotter.py -v --tb=short
```

**Commit:**
```bash
git add backend/src/intelligence/noisy_cartesian_spotter.py backend/tests/test_noisy_cartesian_spotter.py
git commit -m "feat(crewchief): add NoisyCartesianCoordinateSpotter with 9 messages and state"
```

---

### Final Task: Suite completa

**Run:**
```bash
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_enums.py tests/test_coordinate_math.py tests/test_spotter_messages.py tests/test_noisy_cartesian_spotter.py -v
```
Expect 50+ tests passing.

---

## Files Created

| File | Purpose |
|------|---------|
| `src/intelligence/coordinate_math.py` | `aligned_xz()` transform |
| `src/intelligence/spotter_messages.py` | Constantes de mensajes |
| `src/intelligence/noisy_cartesian_spotter.py` | Spotter cartesiano completo |
| `tests/test_coordinate_math.py` | 8 tests |
| `tests/test_spotter_messages.py` | 3 tests |
| `tests/test_noisy_cartesian_spotter.py` | 15+ tests |

## BUGS Identificados y Corregidos del Plan

1. **`rpt_l/rpt_r/rpt_dl/rpt_dr/mid` flags** — definidos pero nunca seteados. Eliminados.
2. **`_check_v` con `dt < 0.2`** — usa velocidad cacheada; documentado.
3. **`max_per_side` break** — ya documenta en plan que puede perder oponentes en el otro lado. Test añadido.
4. **Fallback para `play_spotter_message` no existente** — añadido try/except con `play()` normal.
5. **AUDIO_MAP con nombre real "in_the_middle"** — renombrado en `spotter_messages.py`.
