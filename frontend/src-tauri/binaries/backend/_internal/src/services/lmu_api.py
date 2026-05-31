import asyncio
import logging
import time
from threading import Lock
import httpx

from src.config import settings

logger = logging.getLogger("vantare.lmu_api")

# Caches thread-safe compartidos
_weather_cache: dict = {}
_strategy_usage_cache: dict = {}
_garage_wear_cache: dict = {}

_weather_updated: float = 0.0
_strategy_updated: float = 0.0
_garage_updated: float = 0.0

_cache_lock = Lock()


def get_weather() -> dict:
    """Devuelve los datos climáticos cacheados. Thread-safe.
    
    Estructura esperada: JSON con PRACTICE, QUALIFY, RACE.
    Cada uno con START, NODE_25, NODE_50, NODE_75, FINISH.
    Campos por nodo: WNV_SKY, WNV_TEMPERATURE, WNV_RAIN_CHANCE, WNV_HUMIDITY, WNV_WINDDIRECTION, WNV_WINDSPEED.
    """
    with _cache_lock:
        return _weather_cache.copy()


def get_strategy_usage() -> dict:
    """Devuelve el historial de uso de energía virtual por piloto. Thread-safe.
    
    Estructura esperada: ej. {"Isaac Albala": [{"ve": 1.0}, {"ve": 0.95}, ...]}
    """
    with _cache_lock:
        return _strategy_usage_cache.copy()


def get_garage_wear() -> dict:
    """Devuelve los desgastes de garaje (aero, frenos, suspensión). Thread-safe.
    
    Estructura esperada: wearables.body.aero (float), wearables.brakes (array), wearables.suspension (array)
    """
    with _cache_lock:
        return _garage_wear_cache.copy()


def get_additional_data(category: str) -> dict:
    """Devuelve datos de cache de forma thread-safe y retrocompatible.
    
    Permite que strategy_service.py siga consultando 'brakes' y 'damage' de forma transparente.
    """
    with _cache_lock:
        if category == "weather":
            return _weather_cache.copy()
        elif category == "strategy_usage":
            return _strategy_usage_cache.copy()
        elif category == "garage_wear":
            return _garage_wear_cache.copy()
        elif category == "brakes":
            # Extrae la lista de desgaste de frenos de wearables (4 floats 0-1)
            brakes = _garage_wear_cache.get("wearables", {}).get("brakes", [])
            return {"wear": brakes}
        elif category == "damage":
            # Extrae el desgaste aerodinámico de wearables
            aero = _garage_wear_cache.get("wearables", {}).get("body", {}).get("aero", 0.0)
            return {"aero": aero}
        return {}


def get_cache_sizes() -> dict:
    """Cantidad de entradas en los caches con timestamps. Útil para diagnóstico."""
    with _cache_lock:
        return {
            "weather": len(_weather_cache),
            "strategy_usage": len(_strategy_usage_cache),
            "garage_wear": len(_garage_wear_cache),
            "weather_age_s": time.monotonic() - _weather_updated if _weather_updated else -1,
            "strategy_age_s": time.monotonic() - _strategy_updated if _strategy_updated else -1,
            "garage_age_s": time.monotonic() - _garage_updated if _garage_updated else -1,
            # Claves compatibles para no romper la API de health actual
            "drivers": len(_strategy_usage_cache),
            "brakes": len(_garage_wear_cache)
        }


async def poll_api() -> None:
    """Loop infinito asíncrono que consulta los 3 endpoints reales de LMU de forma no bloqueante.
    
    - /rest/sessions/weather: cada 120 segundos.
    - /rest/strategy/usage: cada 3 segundos.
    - /rest/garage/UIScreen/RepairAndRefuel: cada 3 segundos.
    
    Arrancado como tarea asyncio en background desde el lifespan de FastAPI.
    """
    logger.info("LMU REST API poller started")
    
    last_weather_poll = 0.0
    last_strategy_poll = 0.0
    last_garage_poll = 0.0
    
    try:
        async with httpx.AsyncClient() as client:
            while True:
                current_time = time.monotonic()
                tasks = []
                task_keys = []
                
                # 1. Weather (cada 120 segundos)
                # La primera iteración (last_weather_poll = 0.0) se ejecutará inmediatamente
                if current_time - last_weather_poll >= 120.0:
                    tasks.append(client.get(f"{settings.LMU_REST_URL}/rest/sessions/weather", timeout=2.0))
                    task_keys.append("weather")
                
                # 2. Strategy Usage (cada 3 segundos)
                if current_time - last_strategy_poll >= 3.0:
                    tasks.append(client.get(f"{settings.LMU_REST_URL}/rest/strategy/usage", timeout=2.0))
                    task_keys.append("strategy_usage")
                
                # 3. Garage Wear (cada 3 segundos)
                if current_time - last_garage_poll >= 3.0:
                    tasks.append(client.get(f"{settings.LMU_REST_URL}/rest/garage/UIScreen/RepairAndRefuel", timeout=2.0))
                    task_keys.append("garage_wear")
                
                if tasks:
                    # Ejecutar en paralelo todas las consultas agendadas
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    new_weather = None
                    new_strategy = None
                    new_garage = None
                    
                    for key, result in zip(task_keys, results):
                        if isinstance(result, Exception):
                            logger.debug(f"Fetch for {key} failed: {result}")
                            continue
                        if result.status_code != 200:
                            logger.debug(f"Fetch for {key} returned status {result.status_code}")
                            continue
                        try:
                            data = result.json()
                            if key == "weather":
                                new_weather = data
                            elif key == "strategy_usage":
                                new_strategy = data
                            elif key == "garage_wear":
                                new_garage = data
                        except Exception as e:
                            logger.debug(f"Failed to parse JSON response for {key}: {e}")
                    
                    # Swap atómico con lock para mantener la persistencia
                    global _weather_cache, _strategy_usage_cache, _garage_wear_cache, _weather_updated, _strategy_updated, _garage_updated
                    with _cache_lock:
                        if new_weather is not None:
                            _weather_cache = new_weather
                            _weather_updated = current_time
                        if new_strategy is not None:
                            _strategy_usage_cache = new_strategy
                            _strategy_updated = current_time
                        if new_garage is not None:
                            _garage_wear_cache = new_garage
                            _garage_updated = current_time
                            
                    # Actualizar timestamps de última consulta para evitar busy-waiting
                    if "weather" in task_keys:
                        last_weather_poll = current_time
                    if "strategy_usage" in task_keys:
                        last_strategy_poll = current_time
                    if "garage_wear" in task_keys:
                        last_garage_poll = current_time
                
                # Tick cada 1 segundo para verificar tiempos de refresco
                await asyncio.sleep(1.0)
                
    except asyncio.CancelledError:
        logger.info("LMU REST API poller cancelled")
        raise
    except Exception as e:
        logger.error(f"Error in LMU REST API poller loop: {e}", exc_info=True)
