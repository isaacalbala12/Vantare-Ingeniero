"""Tests para ProfileStore."""

import json
import os
import tempfile

import pytest

from src.persistence.profile_store import ProfileStore


@pytest.fixture
def profile_dir(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setattr("src.persistence.profile_store.PROFILES_DIR", tmp)
    yield tmp


class TestProfileStore:
    def test_save_load_delete_list(self, profile_dir):
        store = ProfileStore()
        cfg = {"vllmIP": "localhost", "serverPort": 8008, "swearyMessages": True}
        store.save_profile("endurance", cfg)

        assert store.list_profiles() == ["endurance"]
        loaded = store.load_profile("endurance")
        assert loaded["serverPort"] == 8008

        store.delete_profile("endurance")
        assert store.list_profiles() == []

    def test_invalid_name_rejected(self, profile_dir):
        store = ProfileStore()
        with pytest.raises(ValueError):
            store.save_profile("../escape", {})

    def test_load_missing_raises(self, profile_dir):
        store = ProfileStore()
        with pytest.raises(FileNotFoundError):
            store.load_profile("missing")

    def test_persists_to_disk(self, profile_dir):
        store = ProfileStore()
        store.save_profile("race", {"serverPort": 9000})
        path = os.path.join(profile_dir, "race.json")
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["config"]["serverPort"] == 9000
