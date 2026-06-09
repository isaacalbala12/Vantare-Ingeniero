"""Tests de coerce_state_dict."""

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from src.intelligence.state_coercion import coerce_state_dict


class SampleModel(BaseModel):
    speed: int = 180
    lap_number: int = 3


def test_coerce_none_returns_empty_dict():
    assert coerce_state_dict(None) == {}


def test_coerce_dict_returns_same_mapping():
    data = {"speed": 200}
    assert coerce_state_dict(data) is data


def test_coerce_pydantic_model():
    model = SampleModel()
    result = coerce_state_dict(model)
    assert result == {"speed": 180, "lap_number": 3}


def test_coerce_mock_for_tests():
    mock = MagicMock()
    mock.speed = 150
    mock.lap_number = 2
    mock.foo = MagicMock()
    result = coerce_state_dict(mock, allow_mock=True)
    assert result["speed"] == 150
    assert result["lap_number"] == 2
    assert "foo" not in result
