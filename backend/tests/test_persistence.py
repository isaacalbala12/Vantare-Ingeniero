"""
Tests unitarios para el módulo de persistencia (HistoryStore).

Verifica:
- Guardado y carga correcta de historial.
- record_lap() añade entradas ordenadas.
- get_history() devuelve copias independientes.
- Persistencia a disco funciona (save/load).
"""
import os
import json
import tempfile
import pytest
from src.persistence.history_store import HistoryStore, SESSION_FILE


# =========================================================================
# Helpers
# =========================================================================

@pytest.fixture
def temp_history_file(monkeypatch):
    """Redirige el archivo de persistencia a un temporal para no dañar datos reales."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    tmp.close()
    tmp_path = tmp.name
    monkeypatch.setattr("src.persistence.history_store.SESSION_FILE", tmp_path)
    yield tmp_path
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


# =========================================================================
# Tests de HistoryStore
# =========================================================================

class TestHistoryStoreBasic:
    """Operaciones básicas del HistoryStore."""

    def test_init_creates_empty_history(self):
        """Un HistoryStore nuevo debe tener historial vacío."""
        store = HistoryStore(auto_load=False)
        assert store.get_history() == []

    def test_record_lap_adds_entry(self, temp_history_file):
        """record_lap debe añadir una entrada."""
        store = HistoryStore(auto_load=False)
        store.record_lap(lap=1, fuel_used=3.5, fuel_remaining=96.5, lap_time=120.5)
        history = store.get_history()
        assert len(history) == 1
        assert history[0]["lap"] == 1
        assert history[0]["consumption"] == 3.5
        assert history[0]["fuelRemaining"] == 96.5
        assert history[0]["lapTime"] == 120.5

    def test_record_lap_multiple_entries(self, temp_history_file):
        """Se pueden añadir múltiples vueltas."""
        store = HistoryStore(auto_load=False)
        for lap in range(1, 6):
            store.record_lap(
                lap=lap,
                fuel_used=3.0 + lap * 0.1,
                fuel_remaining=100.0 - lap * 3.1,
                lap_time=120.0 - lap * 0.5,
            )
        history = store.get_history()
        assert len(history) == 5
        # Deben estar ordenados por lap
        laps = [h["lap"] for h in history]
        assert laps == sorted(laps)


class TestHistoryStorePersistence:
    """Persistencia a disco del HistoryStore."""

    def test_save_creates_file(self, temp_history_file):
        """save() debe crear el archivo JSON en disco."""
        store = HistoryStore(auto_load=False)
        store.record_lap(lap=1, fuel_used=3.5, fuel_remaining=96.5, lap_time=120.5)
        store.save()
        assert os.path.exists(temp_history_file)
        with open(temp_history_file, "r") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["lap"] == 1

    def test_load_restores_history(self, temp_history_file):
        """load() debe restaurar el historial desde disco."""
        # Primero guardar datos
        store1 = HistoryStore(auto_load=False)
        store1.record_lap(lap=1, fuel_used=3.5, fuel_remaining=96.5, lap_time=120.5)
        store1.record_lap(lap=2, fuel_used=3.8, fuel_remaining=92.7, lap_time=121.0)
        store1.save()

        # Crear nueva instancia con auto_load=True
        store2 = HistoryStore(auto_load=True)
        history = store2.get_history()
        assert len(history) == 2
        assert history[0]["lap"] == 1
        assert history[1]["lap"] == 2

    def test_save_preserves_data_integrity(self, temp_history_file):
        """Los datos guardados deben tener el formato correcto."""
        store = HistoryStore(auto_load=False)
        store.record_lap(lap=1, fuel_used=3.5, fuel_remaining=96.5, lap_time=120.5)
        store.save()

        with open(temp_history_file, "r") as f:
            data = json.load(f)

        record = data[0]
        assert "lap" in record
        assert "consumption" in record
        assert "fuelRemaining" in record
        assert "lapTime" in record
        # Verificar tipos
        assert isinstance(record["lap"], int)
        assert isinstance(record["consumption"], float)
        assert isinstance(record["fuelRemaining"], float)
        assert isinstance(record["lapTime"], float)

    def test_load_from_nonexistent_file(self):
        """load() desde archivo inexistente debe dar historial vacío."""
        store = HistoryStore(auto_load=False)
        store.load()  # No hay archivo
        assert store.get_history() == []

    def test_load_from_corrupted_file(self, temp_history_file):
        """load() desde archivo corrupto debe dar historial vacío."""
        with open(temp_history_file, "w") as f:
            f.write("not valid json")
        store = HistoryStore(auto_load=False)
        store.load()
        assert store.get_history() == []


class TestHistoryStoreEdgeCases:
    """Casos límite del HistoryStore."""

    def test_record_lap_updates_existing_lap(self, temp_history_file):
        """Si se registra la misma vuelta dos veces, debe sobrescribir."""
        store = HistoryStore(auto_load=False)
        store.record_lap(lap=1, fuel_used=3.5, fuel_remaining=96.5, lap_time=120.5)
        store.record_lap(lap=1, fuel_used=4.0, fuel_remaining=96.0, lap_time=121.0)
        history = store.get_history()
        assert len(history) == 1  # Solo una entrada
        assert history[0]["consumption"] == 4.0  # Último valor

    def test_clear_empties_history(self, temp_history_file):
        """clear() debe vaciar el historial en memoria."""
        store = HistoryStore(auto_load=False)
        store.record_lap(lap=1, fuel_used=3.5, fuel_remaining=96.5, lap_time=120.5)
        store.clear()
        assert store.get_history() == []

    def test_get_history_returns_copy(self, temp_history_file):
        """get_history() debe retornar una copia, no la referencia interna."""
        store = HistoryStore(auto_load=False)
        store.record_lap(lap=1, fuel_used=3.5, fuel_remaining=96.5, lap_time=120.5)
        history_copy = store.get_history()
        history_copy.append({"lap": 99, "consumption": 0, "fuelRemaining": 0, "lapTime": 0})
        # El store original no debe verse afectado
        assert len(store.get_history()) == 1

    def test_record_lap_rounding(self, temp_history_file):
        """Los valores deben redondearse correctamente."""
        store = HistoryStore(auto_load=False)
        store.record_lap(lap=1, fuel_used=3.55555, fuel_remaining=96.44444, lap_time=120.55555)
        history = store.get_history()
        assert history[0]["consumption"] == 3.556  # 3 decimales
        assert history[0]["fuelRemaining"] == 96.44  # 2 decimales
        assert history[0]["lapTime"] == 120.56  # 2 decimales

    def test_record_lap_zero_consumption(self, temp_history_file):
        """Consumo cero también debe registrarse."""
        store = HistoryStore(auto_load=False)
        store.record_lap(lap=1, fuel_used=0.0, fuel_remaining=100.0, lap_time=120.0)
        history = store.get_history()
        assert len(history) == 1
        assert history[0]["consumption"] == 0.0
