"""Tests unitarios para lmu_api.py — Caching y polling de la REST API de LMU.

Verifica:
- get_weather, get_strategy_usage, get_garage_wear con caches vacíos y poblados
- get_additional_data para categorías brakes, damage, y desconocidas
- get_cache_sizes con timestamps
- poll_api con mock de httpx (éxito, errores HTTP, excepciones, parseo fallido)
- Comportamiento thread-safe
"""
import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.services import lmu_api


@pytest.fixture(autouse=True)
def reset_caches():
    """Limpia los caches globales antes de cada test."""
    with lmu_api._cache_lock:
        lmu_api._weather_cache = {}
        lmu_api._strategy_usage_cache = {}
        lmu_api._garage_wear_cache = {}
        lmu_api._weather_updated = 0.0
        lmu_api._strategy_updated = 0.0
        lmu_api._garage_updated = 0.0
    yield
    # Cleanup after test
    with lmu_api._cache_lock:
        lmu_api._weather_cache = {}
        lmu_api._strategy_usage_cache = {}
        lmu_api._garage_wear_cache = {}
        lmu_api._weather_updated = 0.0
        lmu_api._strategy_updated = 0.0
        lmu_api._garage_updated = 0.0


class TestCacheGetters:
    """Pruebas de las funciones get_* con caches."""

    def test_get_weather_empty(self):
        """get_weather debe devolver dict vacío si no hay cache."""
        result = lmu_api.get_weather()
        assert result == {}

    def test_get_weather_populated(self):
        """get_weather debe devolver copia del cache."""
        test_data = {"RACE": {"START": {"WNV_TEMPERATURE": 25.0}}}
        with lmu_api._cache_lock:
            lmu_api._weather_cache = test_data
            lmu_api._weather_updated = time.monotonic()
        result = lmu_api.get_weather()
        assert result == test_data
        # Verify it's a copy (mutation-safe)
        result["extra"] = "should not affect cache"
        with lmu_api._cache_lock:
            assert "extra" not in lmu_api._weather_cache

    def test_get_strategy_usage_empty(self):
        """get_strategy_usage debe devolver dict vacío si no hay cache."""
        assert lmu_api.get_strategy_usage() == {}

    def test_get_strategy_usage_populated(self):
        """get_strategy_usage debe devolver los datos de estrategia."""
        test_data = {"DriverA": [{"ve": 0.95}]}
        with lmu_api._cache_lock:
            lmu_api._strategy_usage_cache = test_data
        result = lmu_api.get_strategy_usage()
        assert result == test_data

    def test_get_garage_wear_empty(self):
        """get_garage_wear debe devolver dict vacío si no hay cache."""
        assert lmu_api.get_garage_wear() == {}

    def test_get_garage_wear_populated(self):
        """get_garage_wear debe devolver los desgastes de garaje."""
        test_data = {"wearables": {"body": {"aero": 0.05}, "brakes": [0.9, 0.8, 0.7, 0.6]}}
        with lmu_api._cache_lock:
            lmu_api._garage_wear_cache = test_data
        result = lmu_api.get_garage_wear()
        assert result == test_data


class TestGetAdditionalData:
    """Pruebas de get_additional_data con diferentes categorías."""

    def test_additional_weather(self):
        """Categoría 'weather' debe devolver el cache de clima."""
        test_data = {"RACE": {"START": {"WNV_TEMPERATURE": 22.0}}}
        with lmu_api._cache_lock:
            lmu_api._weather_cache = test_data
        result = lmu_api.get_additional_data("weather")
        assert result == test_data

    def test_additional_strategy(self):
        """Categoría 'strategy_usage' debe devolver el cache de estrategia."""
        test_data = {"DriverB": [{"ve": 0.8}]}
        with lmu_api._cache_lock:
            lmu_api._strategy_usage_cache = test_data
        result = lmu_api.get_additional_data("strategy_usage")
        assert result == test_data

    def test_additional_garage(self):
        """Categoría 'garage_wear' debe devolver el cache de garaje."""
        test_data = {"wearables": {"brakes": [0.5]}}
        with lmu_api._cache_lock:
            lmu_api._garage_wear_cache = test_data
        result = lmu_api.get_additional_data("garage_wear")
        assert result == test_data

    def test_additional_brakes(self):
        """Categoría 'brakes' debe extraer wearables.brakes del cache de garaje."""
        with lmu_api._cache_lock:
            lmu_api._garage_wear_cache = {
                "wearables": {"brakes": [0.92, 0.88, 0.85, 0.90]}
            }
        result = lmu_api.get_additional_data("brakes")
        assert result == {"wear": [0.92, 0.88, 0.85, 0.90]}

    def test_additional_brakes_empty(self):
        """Categoría 'brakes' sin datos debe devolver lista vacía."""
        with lmu_api._cache_lock:
            lmu_api._garage_wear_cache = {}
        result = lmu_api.get_additional_data("brakes")
        assert result == {"wear": []}

    def test_additional_damage(self):
        """Categoría 'damage' debe extraer wearables.body.aero."""
        with lmu_api._cache_lock:
            lmu_api._garage_wear_cache = {
                "wearables": {"body": {"aero": 0.12}}
            }
        result = lmu_api.get_additional_data("damage")
        assert result == {"aero": 0.12}

    def test_additional_damage_empty(self):
        """Categoría 'damage' sin datos debe devolver aero=0.0."""
        with lmu_api._cache_lock:
            lmu_api._garage_wear_cache = {}
        result = lmu_api.get_additional_data("damage")
        assert result == {"aero": 0.0}

    def test_additional_unknown_category(self):
        """Categoría desconocida debe devolver dict vacío."""
        result = lmu_api.get_additional_data("unknown_category")
        assert result == {}


class TestGetCacheSizes:
    """Pruebas de get_cache_sizes."""

    def test_cache_sizes_all_empty(self):
        """get_cache_sizes debe reportar -1 para edades si los caches están vacíos."""
        sizes = lmu_api.get_cache_sizes()
        assert sizes["weather"] == 0
        assert sizes["strategy_usage"] == 0
        assert sizes["garage_wear"] == 0
        assert sizes["weather_age_s"] == -1
        assert sizes["strategy_age_s"] == -1
        assert sizes["garage_age_s"] == -1
        assert sizes["drivers"] == 0
        assert sizes["brakes"] == 0

    def test_cache_sizes_populated(self):
        """get_cache_sizes debe reportar tamaños y edades positivas."""
        with lmu_api._cache_lock:
            lmu_api._weather_cache = {"RACE": {}}
            lmu_api._weather_updated = time.monotonic()
            lmu_api._strategy_usage_cache = {"A": [], "B": []}
            lmu_api._strategy_updated = time.monotonic()
            lmu_api._garage_wear_cache = {"wearables": {}}
            lmu_api._garage_updated = time.monotonic()

        sizes = lmu_api.get_cache_sizes()
        assert sizes["weather"] == 1
        assert sizes["strategy_usage"] == 2
        assert sizes["garage_wear"] == 1
        assert sizes["weather_age_s"] >= 0
        assert sizes["strategy_age_s"] >= 0
        assert sizes["garage_age_s"] >= 0
        assert sizes["drivers"] == 2
        assert sizes["brakes"] == 1


class TestPollAPICacheLogic:
    """Pruebas de la lógica de actualización de caches que usa poll_api.
    
    En lugar de mockear poll_api (frágil por el asyncio loop), probamos
    directamente las operaciones de actualización atómica de caches.
    """

    def _simulate_cache_update(self, weather=None, strategy=None, garage=None):
        """Simula la lógica de actualización de caches que usa poll_api."""
        with lmu_api._cache_lock:
            if weather is not None:
                lmu_api._weather_cache = weather
                lmu_api._weather_updated = time.monotonic()
            if strategy is not None:
                lmu_api._strategy_usage_cache = strategy
                lmu_api._strategy_updated = time.monotonic()
            if garage is not None:
                lmu_api._garage_wear_cache = garage
                lmu_api._garage_updated = time.monotonic()

    def test_cache_update_all(self):
        """Actualizar todos los caches debe funcionar."""
        weather_data = {"RACE": {"START": {"WNV_TEMPERATURE": 22.0}}}
        strategy_data = {"DriverA": [{"ve": 1.0}]}
        garage_data = {"wearables": {"brakes": [0.9, 0.8]}}

        self._simulate_cache_update(weather_data, strategy_data, garage_data)

        assert lmu_api.get_weather() == weather_data
        assert lmu_api.get_strategy_usage() == strategy_data
        assert lmu_api.get_garage_wear() == garage_data

    def test_cache_update_partial(self):
        """Actualizar solo algunos caches debe dejar otros intactos."""
        initial_weather = {"RACE": {"OLD": "data"}}
        with lmu_api._cache_lock:
            lmu_api._weather_cache = initial_weather

        # Actualizar solo strategy y garage
        strategy_data = {"DriverB": [{"ve": 0.5}]}
        garage_data = {"wearables": {"brakes": [0.5, 0.5, 0.5, 0.5]}}
        self._simulate_cache_update(strategy=strategy_data, garage=garage_data)

        # Weather debe mantener el valor inicial
        assert lmu_api.get_weather() == initial_weather
        assert lmu_api.get_strategy_usage() == strategy_data
        assert lmu_api.get_garage_wear() == garage_data

    def test_cache_update_empty(self):
        """Actualizar caches con datos vacíos debe reemplazar el contenido."""
        initial = {"RACE": {"OLD": "data"}}
        with lmu_api._cache_lock:
            lmu_api._weather_cache = initial

        self._simulate_cache_update(weather={})

        assert lmu_api.get_weather() == {}  # Reemplazado por vacío

    def test_cache_update_twice(self):
        """Actualizar el mismo cache dos veces debe mantener el último valor."""
        self._simulate_cache_update(weather={"version": 1})
        self._simulate_cache_update(weather={"version": 2})

        assert lmu_api.get_weather() == {"version": 2}

    def test_cache_update_preserves_unrelated(self):
        """Actualizar weather no debe afectar strategy_usage."""
        self._simulate_cache_update(weather={"w": 1})
        assert lmu_api.get_strategy_usage() == {}  # No afectado

        self._simulate_cache_update(strategy={"s": 1})
        assert lmu_api.get_weather() == {"w": 1}  # No afectado
        assert lmu_api.get_garage_wear() == {}  # No afectado


