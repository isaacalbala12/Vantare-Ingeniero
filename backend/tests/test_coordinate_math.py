import math
import pytest
from src.intelligence.coordinate_math import aligned_xz


class TestAlignedXz:
    def test_facing_forward_right(self):
        """Piloto mirando +Z mundial (yaw=0), oponente a la derecha mundial."""
        ax, az = aligned_xz(yaw=0, px=0, pz=0, ox=10, oz=0)
        assert abs(ax - 10) < 0.001
        assert abs(az) < 0.001

    def test_opponent_ahead(self):
        ax, az = aligned_xz(yaw=0, px=0, pz=0, ox=0, oz=10)
        assert abs(ax) < 0.001
        assert abs(az - 10) < 0.001

    def test_opponent_behind(self):
        ax, az = aligned_xz(yaw=0, px=0, pz=0, ox=0, oz=-10)
        assert abs(ax) < 0.001
        assert abs(az - (-10)) < 0.001

    def test_opponent_left(self):
        ax, az = aligned_xz(yaw=0, px=0, pz=0, ox=-10, oz=0)
        assert abs(ax - (-10)) < 0.001
        assert abs(az) < 0.001

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
        ax, az = aligned_xz(yaw=0, px=0, pz=0, ox=5, oz=5)
        assert abs(ax - 5) < 0.001
        assert abs(az - 5) < 0.001

    def test_returns_floats(self):
        ax, az = aligned_xz(0, 0, 0, 1, 0)
        assert isinstance(ax, float)
        assert isinstance(az, float)
