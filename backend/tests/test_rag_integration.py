"""Integration tests for RAG pipeline: Engine -> EventStore -> ContextBuilder."""

from unittest.mock import MagicMock
import pytest

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.context_builder import (
    _build_rag_context,
    _snapshot_to_frame,
)
from src.persistence.event_store import EventStore


class TestEngineEventStoreIntegration:
    """Engine debe recibir y propagar event_store a context_builder."""

    def test_engine_accepts_event_store(self) -> None:
        """Engine.__init__ guarda event_store."""
        mock_store = MagicMock(spec=EventStore)
        engine = IntelligenceEngine(event_store=mock_store)
        assert engine._get_event_store() is mock_store

    def test_engine_without_event_store(self) -> None:
        """Engine sin event_store devuelve None."""
        engine = IntelligenceEngine()
        assert engine._get_event_store() is None

    def test_engine_returns_same_event_store(self) -> None:
        """_get_event_store() devuelve el mismo store inyectado."""
        mock_store = MagicMock(spec=EventStore)
        engine = IntelligenceEngine(event_store=mock_store)
        assert engine._get_event_store() is mock_store
        assert engine._get_event_store() is not None


class TestEventStoreRealIntegration:
    """Tests de integracion real entre EventStore y context_builder."""

    def test_event_store_query_via_build_rag_context(self, tmp_path) -> None:
        """Pipeline completo: EventStore.store_event -> _build_rag_context returns results."""
        store = EventStore(persist_path=str(tmp_path / ".chroma_test"))
        store.initialize(race_id="test-integration-001")

        frame = {
            "lap_number": 5,
            "standing_position": 3,
            "fuel_in_tank": 45.0,
            "tyre_wear_fl": 60.0,
            "tyre_wear_fr": 55.0,
            "tyre_wear_rl": 50.0,
            "tyre_wear_rr": 45.0,
            "safety_car_active": False,
            "yellow_flag_active": False,
            "full_course_yellow_active": False,
            "time_gap_place_ahead": 2.0,
            "time_gap_place_behind": 0.0,
            "speed": 180.0,
            "cloud_coverage": 2,
            "raining": 0.0,
            "avg_path_wetness": 0.0,
            "ambient_temp": 22.0,
            "track_temp": 35.0,
            "drs_state": False,
            "rear_flap_activated": False,
            "pit_state": 0,
            "battery_charge": 80.0,
            "dent_severity_avg": 3.0,
            "session_type": "race",
        }

        store.store_event(frame, "lap_completed", 5)
        low_fuel_frame = dict(frame)
        low_fuel_frame["fuel_in_tank"] = 15.0
        store.store_event(low_fuel_frame, "pit_entry", 8)

        snapshot = {"lap": 6, "fuel_in_tank": 40.0, "position": 3, "speed": 175.0}
        result = _build_rag_context(snapshot, event_store=store, top_k=2)
        assert result is not None
        assert "## RECORDATORIO" in result
        assert "V5" in result
        assert "Vuelta completada" in result

        store.clear()

    def test_build_rag_context_no_store(self) -> None:
        """Sin EventStore, _build_rag_context devuelve None."""
        result = _build_rag_context({"lap": 1})
        assert result is None

    def test_build_rag_context_empty_results(self, tmp_path) -> None:
        """EventStore vacio -> _build_rag_context devuelve None."""
        store = EventStore(persist_path=str(tmp_path / ".chroma_empty"))
        store.initialize(race_id="empty-test")
        result = _build_rag_context({"lap": 1}, event_store=store)
        assert result is None
        store.clear()

    def test_build_rag_context_with_rear_flap(self, tmp_path) -> None:
        """Verificar que rear_flap se mapea correctamente en la query."""
        store = EventStore(persist_path=str(tmp_path / ".chroma_drs"))
        store.initialize(race_id="drs-test")

        frame = {
            "lap_number": 10,
            "standing_position": 2,
            "fuel_in_tank": 60.0,
            "tyre_wear_fl": 50.0,
            "tyre_wear_fr": 45.0,
            "tyre_wear_rl": 40.0,
            "tyre_wear_rr": 35.0,
            "safety_car_active": False,
            "yellow_flag_active": False,
            "full_course_yellow_active": False,
            "time_gap_place_ahead": 1.5,
            "time_gap_place_behind": 0.0,
            "speed": 200.0,
            "cloud_coverage": 1,
            "raining": 0.0,
            "avg_path_wetness": 0.0,
            "ambient_temp": 25.0,
            "track_temp": 40.0,
            "drs_state": True,
            "rear_flap_activated": True,
            "pit_state": 0,
            "battery_charge": 90.0,
            "dent_severity_avg": 2.0,
            "session_type": "race",
        }
        store.store_event(frame, "lap_completed", 10)

        snapshot = {
            "lap": 12,
            "fuel_in_tank": 55.0,
            "position": 2,
            "speed": 195.0,
            "drs_state": True,
        }
        result = _build_rag_context(snapshot, event_store=store, top_k=1)
        assert result is not None
        assert "V10" in result
        store.clear()


class TestSnapshotToFrameEdgeCases:
    """Casos borde en snapshot_to_frame."""

    def test_fuel_as_string(self) -> None:
        """fuel_in_tank como string debe convertirse a float."""
        frame = _snapshot_to_frame({"lap": 5, "fuel_in_tank": "42.5"})
        assert frame is not None
        assert frame["fuel_in_tank"] == 42.5

    def test_fuel_as_invalid_string(self) -> None:
        """fuel_in_tank string invalido -> default 0.0."""
        frame = _snapshot_to_frame({"lap": 5, "fuel_in_tank": "abc"})
        assert frame is not None
        assert frame["fuel_in_tank"] == 0.0

    def test_position_from_place(self) -> None:
        """Usar 'place' si 'position' no esta."""
        frame = _snapshot_to_frame({"lap": 5, "place": 3})
        assert frame is not None
        assert frame["standing_position"] == 3

    def test_tyre_wear_from_wear_fl(self) -> None:
        """Usar wear_fl como fallback si tyre_wear_fl no esta."""
        frame = _snapshot_to_frame({"lap": 5, "wear_fl": 50.0})
        assert frame is not None
        assert frame["tyre_wear_fl"] == 50.0
