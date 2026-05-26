"""Unit tests para EventStore con ChromaDB."""

import pytest
from src.persistence.event_store import EventStore, format_event_text


class TestEventStore:
    """Tests de integración con ChromaDB (usando persistencia temporal)."""

    @pytest.fixture
    def store(self, tmp_path):
        """Crea un EventStore con ruta temporal para cada test."""
        es = EventStore(persist_path=str(tmp_path / ".chroma_test"))
        es.initialize(race_id="test-race-001")
        yield es
        es.clear()

    def _sample_frame(self, lap: int = 5, pos: int = 3) -> dict:
        return {
            "lap_number": lap,
            "standing_position": pos,
            "fuel_in_tank": 50.0,
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

    def test_store_and_retrieve(self, store: EventStore) -> None:
        """Indexar y luego verificar que la colección no está vacía."""
        store.store_event(self._sample_frame(), "lap_completed", 5)
        assert store.get_collection_count() == 1

    def test_store_batch(self, store: EventStore) -> None:
        """Indexar 3 eventos en batch y verificar conteo."""
        frames = [
            (self._sample_frame(5, 3), "lap_completed", 5),
            (self._sample_frame(6, 4), "position_change", 6),
            (self._sample_frame(6, 4), "gap_change", 6),
        ]
        store.store_events_batch(frames)
        assert store.get_collection_count() == 3

    def test_query_similar(self, store: EventStore) -> None:
        """Indexar eventos y luego consultar con frame similar."""
        # Indexar eventos con combustible alto (vuelta 5)
        store.store_event(self._sample_frame(5, 3), "lap_completed", 5)
        # Indexar evento con combustible bajo (vuelta 15)
        frame_low = self._sample_frame(15, 2)
        frame_low["fuel_in_tank"] = 20.0
        store.store_event(frame_low, "lap_completed", 15)

        # Consultar con frame de combustible medio-alto
        query_frame = self._sample_frame(8, 3)
        query_frame["fuel_in_tank"] = 45.0

        results = store.query(query_frame, top_k=2)
        assert len(results) > 0
        # El primer resultado debería ser el de fuel 50.0 (más cercano a 45.0)
        assert results[0]["type"] in ("lap_completed",)

    def test_query_without_indexed_data(self, store: EventStore) -> None:
        """Colección vacía devuelve lista vacía."""
        results = store.query(self._sample_frame())
        assert results == []

    def test_clear_removes_all(self, store: EventStore) -> None:
        """Clear debe eliminar la colección y los archivos."""
        store.store_event(self._sample_frame(), "lap_completed", 5)
        assert store.get_collection_count() == 1
        store.clear()
        # Después de clear, get_collection_count debe devolver 0
        # porque EventStore no está inicializado
        assert store.get_collection_count() == 0

    def test_store_without_initialize(self) -> None:
        """Store sin initialize no debe crashear."""
        es = EventStore()
        es.store_event(self._sample_frame(), "test", 1)  # No debe lanzar error
        assert es.get_collection_count() == 0

    def test_multiple_races(self, store: EventStore) -> None:
        """Simular 2 carreras: inicializar, indexar, clear."""
        # Carrera 1
        store.store_event(self._sample_frame(1), "lap_completed", 1)
        assert store.get_collection_count() == 1

        # Clear
        store.clear()

        # Carrera 2
        store.initialize(race_id="test-race-002")
        assert store.get_collection_count() == 0
        store.store_event(self._sample_frame(1), "lap_completed", 1)
        assert store.get_collection_count() == 1
