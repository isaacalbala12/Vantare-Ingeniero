import pytest
import math
from src.services.lmu_reader import (
    calculate_rotation,
    orientation_to_dict,
    decode_name,
)

def test_rotation_identity():
    r = calculate_rotation({
        "row_x": {"x": 1, "y": 0, "z": 0},
        "row_y": {"x": 0, "y": 1, "z": 0},
        "row_z": {"x": 0, "y": 0, "z": 1},
    })
    assert abs(r["yaw"]) < 0.001

def test_rotation_45deg():
    c = math.cos(math.pi / 4)
    s = math.sin(math.pi / 4)
    r = calculate_rotation({
        "row_x": {"x": c, "y": 0, "z": -s},
        "row_y": {"x": 0, "y": 1, "z": 0},
        "row_z": {"x": s, "y": 0, "z": c},
    })
    assert abs(r["yaw"] - math.pi / 4) < 0.01

def test_rotation_nan_handling():
    r = calculate_rotation({
        "row_x": {"x": float("nan"), "y": 0, "z": 0},
        "row_y": {"x": 0, "y": 1, "z": 0},
        "row_z": {"x": 0, "y": 0, "z": 1},
    })
    assert abs(r["yaw"]) < 0.001

def test_rotation_inf_handling():
    r = calculate_rotation({
        "row_x": {"x": float("inf"), "y": 0, "z": 0},
        "row_y": {"x": 0, "y": 1, "z": 0},
        "row_z": {"x": 0, "y": 0, "z": 1},
    })
    assert abs(r["yaw"]) < 0.001

def test_decode_name_leading_null():
    assert decode_name(b"\x00Hello") == "Hello"

def test_decode_name_null_terminated():
    assert decode_name(b"Test\x00extra") == "Test"

def test_decode_name_empty():
    assert decode_name(b"") == ""

def test_decode_name_none():
    assert decode_name(None) == ""

def test_orientation_to_dict_struct():
    class MockVec:
        def __init__(self, x, y, z):
            self.x = x; self.y = y; self.z = z
    class MockOrient:
        row_x = MockVec(1, 0, 0)
        row_y = MockVec(0, 1, 0)
        row_z = MockVec(0, 0, 1)
    d = orientation_to_dict(MockOrient())
    assert d["row_x"]["x"] == 1.0
    assert d["row_z"]["z"] == 1.0

def test_orientation_to_dict_array_style():
    class MockVec:
        def __init__(self, x, y, z):
            self.x = x; self.y = y; self.z = z
    class MockArray:
        def __getitem__(self, i):
            return [MockVec(1,0,0), MockVec(0,1,0), MockVec(0,0,1)][i]
        def __len__(self):
            return 3
    d = orientation_to_dict(MockArray())
    assert d["row_x"]["x"] == 1.0
