"""Tests PhraseStore — merge defaults + overrides AppData."""

from __future__ import annotations

import json

import pytest

from src.intelligence.phrase_catalog import PhraseCatalog
from src.intelligence.phrase_picker import get_picker, reload_picker
from src.persistence.phrase_store import (
    PhraseStore,
    merge_user_overrides,
    user_phrases_path,
    validate_user_phrases,
)


def test_user_override_replaces_default_variant(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    store = PhraseStore()
    store.save_user({"spotter": {"standard": {"clear_left": "Custom izquierda"}}})
    merged = store.load_merged()
    assert merged["spotter"]["standard"]["clear_left"] == "Custom izquierda"


def test_save_user_merge_preserves_other_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    store = PhraseStore()
    store.save_user(
        {
            "spotter": {"standard": {"clear_left": "Custom izquierda"}},
            "triggers": {"fuel_critical": {"standard": "Gasolina custom"}},
        },
        replace=True,
    )
    store.save_user({"spotter": {"standard": {"clear_right": "Custom derecha"}}})
    user = store.load_user()
    assert user["spotter"]["standard"]["clear_left"] == "Custom izquierda"
    assert user["spotter"]["standard"]["clear_right"] == "Custom derecha"
    assert user["triggers"]["fuel_critical"]["standard"] == "Gasolina custom"


def test_reset_user_restores_bundle_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    store = PhraseStore()
    store.save_user({"spotter": {"standard": {"clear_left": "Custom izquierda"}}})
    store.reset_user()
    merged = store.load_merged()
    assert "Custom izquierda" not in merged["spotter"]["standard"]["clear_left"]


def test_invalid_json_rejected():
    with pytest.raises(ValueError, match="Perfil spotter inválido"):
        validate_user_phrases({"spotter": {"bad_profile": {"clear_left": "Hola"}}})


def test_banned_prefix_rejected_at_start():
    with pytest.raises(ValueError, match="Prefijo robótico"):
        validate_user_phrases({"spotter": {"standard": {"clear_left": "Atención: peligro"}}})


def test_banned_prefix_allowed_in_middle_of_phrase():
    validated = validate_user_phrases(
        {"spotter": {"standard": {"clear_left": "Cuidado con la atención lateral"}}}
    )
    assert validated["spotter"]["standard"]["clear_left"] == "Cuidado con la atención lateral"


def test_corrupt_user_file_surfaces_error(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    store = PhraseStore()
    user_phrases_path().write_text("{bad json", encoding="utf-8")
    assert store.load_user() == {}
    assert store.last_user_load_error is not None
    assert "JSON inválido" in store.last_user_load_error


def test_save_user_repairs_corrupt_file(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    store = PhraseStore()
    user_phrases_path().write_text("{bad json", encoding="utf-8")
    store.load_user()
    store.save_user({"spotter": {"standard": {"clear_left": "Reparado"}}})
    assert store.last_user_load_error is None
    assert store.load_user()["spotter"]["standard"]["clear_left"] == "Reparado"


def test_reload_picker_picks_up_user_override(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    PhraseStore().save_user({"spotter": {"standard": {"clear_left": "Mi clear custom"}}})
    reload_picker()
    msg = get_picker().spotter_phrase("clear_left", profile_id="standard", seed=0)
    assert msg == "Mi clear custom"


def test_persist_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    PhraseStore().save_user({"triggers": {"fuel_critical": {"standard": "Gasolina custom"}}})
    store2 = PhraseStore()
    assert store2.load_user()["triggers"]["fuel_critical"]["standard"] == "Gasolina custom"
    assert user_phrases_path().is_file()


def test_export_user_only_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    payload = {"spotter": {"aggressive": {"hold_line": "Aguanta custom"}}}
    PhraseStore().save_user(payload, replace=True)
    assert PhraseStore().export_user() == payload


def test_catalog_load_merged(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    PhraseStore().save_user({"spotter": {"standard": {"clear_right": "Derecha custom"}}})
    cat = PhraseCatalog.load_merged()
    assert cat.spotter["standard"]["clear_right"] == "Derecha custom"


def test_empty_override_deletes_user_file(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTARE_PHRASES_DIR", str(tmp_path))
    store = PhraseStore()
    store.save_user({"spotter": {"standard": {"clear_left": "Custom"}}}, replace=True)
    store.save_user({"spotter": {"standard": {"clear_left": "   "}}})
    assert store.load_user() == {}
    assert not user_phrases_path().exists()


def test_merge_user_overrides_clears_section_when_empty():
    existing = {
        "spotter": {"standard": {"clear_left": "A"}},
        "triggers": {"fuel_critical": {"standard": "B"}},
    }
    merged = merge_user_overrides(existing, {"triggers": {}})
    assert "triggers" not in merged
    assert merged["spotter"]["standard"]["clear_left"] == "A"
