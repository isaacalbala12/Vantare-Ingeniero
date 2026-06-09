"""Tests unitarios de HistoryStore (persistencia)."""

import json
import os

import pytest

from src.persistence import history_store as hs_mod
from src.persistence.history_store import HistoryStore


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    session_file = data_dir / "consumption_history.json"
    monkeypatch.setattr(hs_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(hs_mod, "SESSION_FILE", str(session_file))
    return HistoryStore(auto_load=False)


def test_record_lap_autosaves_to_disk(isolated_store):
    isolated_store.record_lap(lap=1, fuel_used=3.5, fuel_remaining=96.5, lap_time=120.5)

    assert os.path.exists(hs_mod.SESSION_FILE)
    with open(hs_mod.SESSION_FILE, encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["lap"] == 1
    assert data[0]["consumption"] == 3.5


def test_record_lap_replace_updates_disk(isolated_store):
    isolated_store.record_lap(lap=2, fuel_used=3.0, fuel_remaining=90.0, lap_time=119.0)
    isolated_store.record_lap(lap=2, fuel_used=3.2, fuel_remaining=89.8, lap_time=118.5)

    with open(hs_mod.SESSION_FILE, encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["consumption"] == 3.2
