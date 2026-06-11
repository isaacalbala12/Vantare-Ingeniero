"""Tests REST /phrases y hot-reload spotter cache."""

from __future__ import annotations

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.intelligence.phrase_picker import get_picker, reload_picker
from src.persistence.phrase_store import PhraseStore
from src.routers.phrases import router as phrases_router
from src.voice.spotter_cache import default_spotter_phrases


@pytest.fixture
def phrases_app(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("VANTARE_PHRASES_DIR", tmp)

    app = FastAPI()
    app.include_router(phrases_router)
    app.state.phrase_store = PhraseStore()
    app.state.spotter_cache = MagicMock()
    app.state.spotter_cache.invalidate_all = MagicMock()
    app.state.spotter_cache.warm = AsyncMock()
    app.state.spotter_cache.size = 0
    app.state.edge_tts_service = MagicMock()
    app.state.tts_routing = MagicMock(edge_voice_spotter="es-ES-AlvaroNeural")
    return app


class TestPhrasesRouter:
    def test_get_merged_and_defaults(self, phrases_app):
        with TestClient(phrases_app) as client:
            merged = client.get("/phrases").json()
            defaults = client.get("/phrases/defaults").json()
            assert "spotter" in merged and "triggers" in merged
            assert merged["spotter"]["standard"]["clear_left"]
            assert defaults["spotter"]["standard"]["clear_left"]

    def test_get_meta_reports_corrupt_user_file(self, phrases_app):
        from src.persistence.phrase_store import user_phrases_path

        user_phrases_path().write_text("{bad", encoding="utf-8")
        with TestClient(phrases_app) as client:
            meta = client.get("/phrases/meta").json()
            assert meta["user_load_error"]

    def test_put_valid_override(self, phrases_app):
        with TestClient(phrases_app) as client:
            payload = {"spotter": {"standard": {"clear_left": "Mi frase custom"}}}
            res = client.put("/phrases", json=payload)
            assert res.status_code == 200
            merged = client.get("/phrases").json()
            assert merged["spotter"]["standard"]["clear_left"] == "Mi frase custom"
            exported = client.get("/phrases/export").json()
            assert exported["spotter"]["standard"]["clear_left"] == "Mi frase custom"

    def test_put_merge_preserves_existing_overrides(self, phrases_app):
        with TestClient(phrases_app) as client:
            client.put(
                "/phrases",
                json={
                    "spotter": {"standard": {"clear_left": "Uno"}},
                    "triggers": {"fuel_critical": {"standard": "Dos"}},
                },
            )
            client.put("/phrases", json={"spotter": {"standard": {"clear_right": "Tres"}}})
            exported = client.get("/phrases/export").json()
            assert exported["spotter"]["standard"]["clear_left"] == "Uno"
            assert exported["spotter"]["standard"]["clear_right"] == "Tres"
            assert exported["triggers"]["fuel_critical"]["standard"] == "Dos"

    def test_put_invalid_profile_returns_422(self, phrases_app):
        with TestClient(phrases_app) as client:
            res = client.put("/phrases", json={"spotter": {"unknown": {"clear_left": "Hola"}}})
            assert res.status_code == 422

    def test_reset_restores_defaults(self, phrases_app):
        with TestClient(phrases_app) as client:
            client.put("/phrases", json={"spotter": {"standard": {"clear_left": "Custom"}}})
            assert client.post("/phrases/reset").status_code == 200
            merged = client.get("/phrases").json()
            defaults = client.get("/phrases/defaults").json()
            assert merged["spotter"]["standard"]["clear_left"] == defaults["spotter"]["standard"]["clear_left"]
            assert client.get("/phrases/export").json() == {}

    def test_import_merges_by_default(self, phrases_app):
        with TestClient(phrases_app) as client:
            client.put("/phrases", json={"spotter": {"standard": {"clear_left": "Previo"}}})
            payload = {"triggers": {"fuel_critical": {"standard": "Gasolina custom"}}}
            res = client.post("/phrases/import", json=payload)
            assert res.status_code == 200
            exported = client.get("/phrases/export").json()
            assert exported["spotter"]["standard"]["clear_left"] == "Previo"
            assert exported["triggers"]["fuel_critical"]["standard"] == "Gasolina custom"

    def test_import_replace_wipes_previous(self, phrases_app):
        with TestClient(phrases_app) as client:
            client.put("/phrases", json={"spotter": {"standard": {"clear_left": "Previo"}}})
            payload = {"triggers": {"fuel_critical": {"standard": "Solo triggers"}}}
            res = client.post("/phrases/import?replace=true", json=payload)
            assert res.status_code == 200
            exported = client.get("/phrases/export").json()
            assert "spotter" not in exported
            assert exported["triggers"]["fuel_critical"]["standard"] == "Solo triggers"

    def test_put_triggers_cache_reload(self, phrases_app):
        with TestClient(phrases_app) as client:
            with patch("src.routers.phrases.reload_picker", wraps=reload_picker) as reload_mock:
                client.put("/phrases", json={"spotter": {"standard": {"clear_left": "Reload test"}}})
                reload_mock.assert_called_once()
        cache = phrases_app.state.spotter_cache
        cache.invalidate_all.assert_called_once()
        cache.warm.assert_awaited()


def test_put_updates_picker_immediately(phrases_app):
    with TestClient(phrases_app) as client:
        client.put("/phrases", json={"spotter": {"standard": {"clear_left": "Sync picker test"}}})
    reload_picker()
    assert get_picker().spotter_phrase("clear_left", profile_id="standard", seed=0) == "Sync picker test"


@pytest.mark.asyncio
async def test_spotter_cache_invalidate_clears_entries():
    from src.voice.spotter_cache import SpotterPhraseCache

    tts = MagicMock()
    tts.synthesize = AsyncMock(return_value=b"mp3")
    cache = SpotterPhraseCache(tts)
    await cache.warm({"clear_left": "Despejado"})
    assert cache.size == 1
    cache.invalidate_all()
    assert cache.size == 0
    assert cache.get("clear_left") is None


def test_default_spotter_phrases_uses_custom_clear_left(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    PhraseStore().save_user({"spotter": {"standard": {"clear_left": "Custom cache izquierda"}}})
    reload_picker()
    phrases = default_spotter_phrases(profile_id="standard")
    assert phrases["clear_left"] == "Custom cache izquierda"
