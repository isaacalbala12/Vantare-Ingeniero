"""Tests del LMUReader y helpers de extracción.

Cobertura:
- decode_name: bytes normales, leading null, null terminator, vacío, None
- calculate_rotation: matriz identidad, rotación 45°, NaN, Inf
- orientation_to_dict: struct-style y array-style
- LMUReader: lectura de shared memory (con mocks)
- Bug verificado: slot_id del rival, no índice de lista filtrada
"""
import math
import pytest
from src.services.lmu_reader import (
    calculate_rotation,
    orientation_to_dict,
    decode_name,
)


# =========================================================
# decode_name
# =========================================================
class TestDecodeName:
    def test_leading_null_byte_stripped(self):
        """Algunos campos de LMU tienen un null byte inicial (CrewChief bug fix)."""
        assert decode_name(b"\x00Hello") == "Hello"

    def test_null_terminated_string(self):
        assert decode_name(b"Test\x00extra") == "Test"

    def test_multiple_nulls_terminated_at_first(self):
        assert decode_name(b"Name\x00\x00more") == "Name"

    def test_empty_bytes(self):
        assert decode_name(b"") == ""

    def test_none_input(self):
        assert decode_name(None) == ""

    def test_string_preserved(self):
        assert decode_name(b"PlainName") == "PlainName"

    def test_latin1_decoded_fallback(self):
        # Caracteres no-UTF8 (acentos) deben caer a latin-1
        result = decode_name(b"Jos\xe9")  # 'é' en latin-1
        assert "Jos" in result

    def test_trailing_spaces_stripped(self):
        assert decode_name(b"  Name  ") == "Name"

    def test_only_null_byte(self):
        assert decode_name(b"\x00") == ""


# =========================================================
# calculate_rotation
# =========================================================
class TestCalculateRotation:
    def test_identity_matrix_zero_yaw(self):
        r = calculate_rotation({
            "row_x": {"x": 1, "y": 0, "z": 0},
            "row_y": {"x": 0, "y": 1, "z": 0},
            "row_z": {"x": 0, "y": 0, "z": 1},
        })
        assert abs(r["yaw"]) < 0.001
        assert abs(r["pitch"]) < 0.001
        assert abs(r["roll"]) < 0.001

    def test_45_degrees_yaw(self):
        c = math.cos(math.pi / 4)
        s = math.sin(math.pi / 4)
        r = calculate_rotation({
            "row_x": {"x": c, "y": 0, "z": -s},
            "row_y": {"x": 0, "y": 1, "z": 0},
            "row_z": {"x": s, "y": 0, "z": c},
        })
        assert abs(r["yaw"] - math.pi / 4) < 0.01

    def test_90_degrees_yaw(self):
        # Rotación 90° en Y: row_z apunta a +X, row_x apunta a -Z
        r = calculate_rotation({
            "row_x": {"x": 0, "y": 0, "z": -1},
            "row_y": {"x": 0, "y": 1, "z": 0},
            "row_z": {"x": 1, "y": 0, "z": 0},
        })
        assert abs(r["yaw"] - math.pi / 2) < 0.01

    def test_nan_input_returns_zeros(self):
        """Si la matriz tiene NaN, devolvemos (0,0,0)."""
        r = calculate_rotation({
            "row_x": {"x": float("nan"), "y": 0, "z": 0},
            "row_y": {"x": 0, "y": 1, "z": 0},
            "row_z": {"x": 0, "y": 0, "z": 1},
        })
        assert r["yaw"] == 0.0
        assert r["pitch"] == 0.0
        assert r["roll"] == 0.0

    def test_inf_input_returns_zeros(self):
        r = calculate_rotation({
            "row_x": {"x": float("inf"), "y": 0, "z": 0},
            "row_y": {"x": 0, "y": 1, "z": 0},
            "row_z": {"x": 0, "y": 0, "z": 1},
        })
        assert r["yaw"] == 0.0
        assert r["pitch"] == 0.0
        assert r["roll"] == 0.0

    def test_negative_inf_returns_zeros(self):
        r = calculate_rotation({
            "row_x": {"x": 0, "y": 0, "z": float("-inf")},
            "row_y": {"x": 0, "y": 1, "z": 0},
            "row_z": {"x": 0, "y": 0, "z": 1},
        })
        assert r["yaw"] == 0.0


# =========================================================
# orientation_to_dict
# =========================================================
class TestOrientationToDict:
    def test_struct_style_with_row_x(self):
        class MockVec:
            def __init__(self, x, y, z):
                self.x = x; self.y = y; self.z = z
        class MockOrient:
            row_x = MockVec(1, 0, 0)
            row_y = MockVec(0, 1, 0)
            row_z = MockVec(0, 0, 1)
        d = orientation_to_dict(MockOrient())
        assert d["row_x"]["x"] == 1.0
        assert d["row_y"]["y"] == 1.0
        assert d["row_z"]["z"] == 1.0

    def test_array_style_with_getitem(self):
        class MockVec:
            def __init__(self, x, y, z):
                self.x = x; self.y = y; self.z = z
        class MockArray:
            def __getitem__(self, i):
                return [MockVec(1, 0, 0), MockVec(0, 1, 0), MockVec(0, 0, 1)][i]
            def __len__(self):
                return 3
        d = orientation_to_dict(MockArray())
        assert d["row_x"]["x"] == 1.0
        assert d["row_z"]["z"] == 1.0

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown orientation format"):
            orientation_to_dict("not a valid input")

    def test_too_short_array_raises(self):
        class MockArray:
            def __getitem__(self, i):
                raise IndexError
            def __len__(self):
                return 2
        with pytest.raises(ValueError, match="Unknown orientation format"):
            orientation_to_dict(MockArray())


# =========================================================
# LMUReader - Slot ID bug verificado
# =========================================================
class TestRivalsTelemetrySlotId:
    """Verifica que el bug de telemInfo index mismatch está corregido."""

    def test_rivals_telemetry_index_uses_slot_id(self):
        """El primer rival debe recibir telemetría de SU slot, no del slot 0 (jugador)."""
        rivals = [
            {"_slot_id": 1, "name": "Alice"},
            {"_slot_id": 2, "name": "Bob"},
        ]
        telem_info = [
            {"speed": 50.0, "name": "Player"},  # slot 0
            {"speed": 49.0, "name": "Alice_real"},
            {"speed": 48.0, "name": "Bob_real"},
        ]
        speeds = {}
        for rival in rivals:
            slot = rival.pop("_slot_id")
            speeds[rival["name"]] = telem_info[slot]["speed"]
        # Sin el fix, Alice recibía telem_info[0] (jugador)
        assert speeds["Alice"] == 49.0
        assert speeds["Bob"] == 48.0

    def test_no_player_telemetry_leaks_to_rival(self):
        """Ningún rival debe tener la velocidad del jugador."""
        rivals = [
            {"_slot_id": 1, "name": "Alice"},
            {"_slot_id": 2, "name": "Bob"},
            {"_slot_id": 3, "name": "Charlie"},
        ]
        player_speed = 50.0
        telem_info = [
            {"speed": player_speed},  # slot 0
            {"speed": 49.0},
            {"speed": 48.0},
            {"speed": 47.0},
        ]
        assigned = {}
        for rival in rivals:
            slot = rival.pop("_slot_id")
            assigned[rival["name"]] = telem_info[slot]["speed"]
        for name, speed in assigned.items():
            assert speed != player_speed, f"{name} tiene velocidad del jugador"


# =========================================================
# LMUReader - Integración con mocks
# =========================================================
class MockVec3:
    def __init__(self, x=0, y=0, z=0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class MockWheel:
    def __init__(self):
        self.mSuspensionDeflection = 0.0
        self.mRideHeight = 0.0
        self.mSuspForce = 0.0
        self.mBrakeTemp = 0.0
        self.mBrakePressure = 0.0
        self.mRotation = 0.0
        self.mLateralPatchVel = 0.0
        self.mLongitudinalPatchVel = 0.0
        self.mTemperature = (MockVec3(0, 0, 0), MockVec3(75, 0, 0), MockVec3(0, 0, 0))  # (left, center, right)
        self.mPressure = 100.0
        self.mWear = 0.0


class MockVehicleScoring:
    def __init__(self, name="", place=1, sector=1, in_pits=False, lap=0):
        self.mDriverName = name.encode("utf-8")
        self.mPlace = place
        self.mSector = sector
        self.mInPits = in_pits
        self.mTotalLaps = lap
        self.mLapDist = 0.0
        self.mTimeBehindLeader = 0.0
        self.mLastLapTime = 0.0
        self.mBestLapTime = 0.0
        self.mVehicleClass = b"Hypercar"
        self.mID = 1
        # Orientation: 3 vectores (row_x, row_y, row_z)
        self.mOri = [MockVec3(1, 0, 0), MockVec3(0, 1, 0), MockVec3(0, 0, 1)]
        self.mFuelFraction = 0
        self.mDRSState = 0


class MockVehicleTelemetry:
    def __init__(self, speed=0.0, x=0.0, y=0.0, z=0.0, fuel=0.0):
        self.mPos = MockVec3(x, y, z)
        self.mLocalVel = MockVec3(speed, 0, 0)
        self.mEngineRPM = 0.0
        self.mGear = 1
        self.mEngineWaterTemp = 80.0
        self.mEngineOilTemp = 90.0
        self.mFuel = fuel
        self.mWheels = [MockWheel() for _ in range(4)]
        self.mFrontTireCompoundName = b"Soft"
        self.mRearTireCompoundName = b"Soft"
        self.mVirtualEnergy = 0.0
        self.mStateOfCharge = 0.0
        self.mBatteryChargeFraction = 0.0
        self.mFuelCapacity = 100.0


class MockScoringInfo:
    def __init__(self, session=0, phase=5, num_vehicles=0):
        self.mSession = session
        self.mGamePhase = phase
        self.mCurrentET = 0.0
        self.mEndET = 3600.0
        self.mLapDist = 5000.0
        self.mNumVehicles = num_vehicles


class MockScoringData:
    def __init__(self, num_vehicles, vehicles, scoring_info):
        self.scoringInfo = scoring_info
        self.vehScoringInfo = vehicles
        self.mNumVehicles = num_vehicles


class MockTelemetryData:
    def __init__(self, player_idx, vehicles):
        self.playerVehicleIdx = player_idx
        self.telemInfo = vehicles


class MockLMUObject:
    def __init__(self, scoring, telemetry):
        self.scoring = scoring
        self.telemetry = telemetry


class MockMMap:
    def __init__(self, data):
        self.data = data

    def update(self):
        pass


class TestLMUReader:
    def test_get_flat_dict_returns_minimal_dict_when_not_initialized(self):
        """Sin mmap inicializado, devuelve dict mínimo (no crash)."""
        from src.services.lmu_reader import LMUReader
        reader = LMUReader()
        result = reader.get_flat_dict()
        assert "session_running_time" in result

    def test_get_flat_dict_extracts_session_info(self):
        """Verifica que get_flat_dict() extrae correctamente los campos de sesión."""
        from src.services.lmu_reader import LMUReader
        import shared_telemetry
        from shared_telemetry.pyLMUSharedMemory.lmu_mmap import MMapControl
        from unittest.mock import patch

        vehicles = [MockVehicleScoring(name="Player", place=1, lap=5)]
        scoring = MockScoringData(num_vehicles=1, vehicles=vehicles, scoring_info=MockScoringInfo(session=3, phase=5))
        telemetry = MockTelemetryData(player_idx=0, vehicles=[MockVehicleTelemetry(speed=50.0, x=100, y=0, z=200, fuel=75.0)])
        data = MockLMUObject(scoring=scoring, telemetry=telemetry)

        reader = LMUReader()
        reader._shmm = MockMMap(data)
        reader._is_initialized = True

        result = reader.get_flat_dict()
        assert result["session_type"] == 3  # RACE
        assert result["session_phase"] == 5  # GREEN
        assert result["place"] == 1
        assert result["lap_number"] == 5
        assert result["speed_ms"] == 50.0
        assert result["world_x"] == 100.0
        assert result["world_z"] == 200.0
        assert result["fuel_left"] == 75.0
        assert result["driver_name"] == "Player"

    def test_get_flat_dict_calculates_gap_relative_to_player(self):
        """P1 fix: gap_to_player es la diferencia respecto al jugador, no al líder."""
        from src.services.lmu_reader import LMUReader

        player = MockVehicleScoring(name="Player", place=1, lap=5)
        player.mTimeBehindLeader = 10.0  # Jugador a 10s del líder
        rival = MockVehicleScoring(name="Rival", place=2, lap=5)
        rival.mTimeBehindLeader = 15.0  # Rival a 15s del líder

        vehicles = [player, rival]
        scoring = MockScoringData(num_vehicles=2, vehicles=vehicles, scoring_info=MockScoringInfo())
        telemetry = MockTelemetryData(player_idx=0, vehicles=[
            MockVehicleTelemetry(speed=50.0),
            MockVehicleTelemetry(speed=49.0, x=120, z=210),
        ])
        data = MockLMUObject(scoring=scoring, telemetry=telemetry)

        reader = LMUReader()
        reader._shmm = MockMMap(data)
        reader._is_initialized = True

        result = reader.get_flat_dict()
        # Rival gap = rival.mTimeBehindLeader - player.mTimeBehindLeader = 15 - 10 = 5
        rival_data = next(r for r in result["rivals"] if r["driver_raw_name"] == "Rival")
        assert rival_data["gap_to_player"] == 5.0
        # Y debe tener la telemetría del slot 1, no del slot 0
        assert rival_data["speed"] == 49.0
        assert rival_data["world_x"] == 120.0

    def test_get_flat_dict_skips_transparent_trainer(self):
        """El ghost car 'transparent trainer' debe excluirse de la lista de rivales."""
        from src.services.lmu_reader import LMUReader

        player = MockVehicleScoring(name="Player", place=1, lap=5)
        trainer = MockVehicleScoring(name="transparent trainer", place=99, lap=0)
        rival = MockVehicleScoring(name="Rival", place=2, lap=5)

        vehicles = [player, trainer, rival]
        scoring = MockScoringData(num_vehicles=3, vehicles=vehicles, scoring_info=MockScoringInfo())
        telemetry = MockTelemetryData(player_idx=0, vehicles=[
            MockVehicleTelemetry(speed=50.0),
            MockVehicleTelemetry(speed=0.0),
            MockVehicleTelemetry(speed=49.0, x=120, z=210),
        ])
        data = MockLMUObject(scoring=scoring, telemetry=telemetry)

        reader = LMUReader()
        reader._shmm = MockMMap(data)
        reader._is_initialized = True

        result = reader.get_flat_dict()
        names = [r["driver_raw_name"] for r in result["rivals"]]
        assert "transparent trainer" not in names
        assert "Rival" in names
        assert len(result["rivals"]) == 1
        # Rival debe tener telemetría del slot 2 (su slot real)
        assert result["rivals"][0]["world_x"] == 120.0
