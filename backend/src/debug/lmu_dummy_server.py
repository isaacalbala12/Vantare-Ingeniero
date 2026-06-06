"""Servidor HTTP dummy que emula la REST API de LMU (puerto 6397)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

WEATHER_FIXTURE = {
    "PRACTICE": {
        "START": {
            "WNV_SKY": 0,
            "WNV_TEMPERATURE": 22.0,
            "WNV_RAIN_CHANCE": 5.0,
            "WNV_HUMIDITY": 55.0,
            "WNV_WINDDIRECTION": 180.0,
            "WNV_WINDSPEED": 3.5,
        },
        "NODE_25": {
            "WNV_SKY": 0,
            "WNV_TEMPERATURE": 23.0,
            "WNV_RAIN_CHANCE": 10.0,
            "WNV_HUMIDITY": 58.0,
            "WNV_WINDDIRECTION": 190.0,
            "WNV_WINDSPEED": 4.0,
        },
    },
    "QUALIFY": {
        "START": {
            "WNV_SKY": 1,
            "WNV_TEMPERATURE": 20.0,
            "WNV_RAIN_CHANCE": 15.0,
            "WNV_HUMIDITY": 62.0,
            "WNV_WINDDIRECTION": 200.0,
            "WNV_WINDSPEED": 5.0,
        }
    },
    "RACE": {
        "START": {
            "WNV_SKY": 0,
            "WNV_TEMPERATURE": 24.0,
            "WNV_RAIN_CHANCE": 8.0,
            "WNV_HUMIDITY": 50.0,
            "WNV_WINDDIRECTION": 170.0,
            "WNV_WINDSPEED": 2.5,
        },
        "NODE_25": {
            "WNV_SKY": 2,
            "WNV_TEMPERATURE": 21.0,
            "WNV_RAIN_CHANCE": 35.0,
            "WNV_HUMIDITY": 70.0,
            "WNV_WINDDIRECTION": 210.0,
            "WNV_WINDSPEED": 6.0,
        },
        "NODE_50": {
            "WNV_SKY": 3,
            "WNV_TEMPERATURE": 19.0,
            "WNV_RAIN_CHANCE": 55.0,
            "WNV_HUMIDITY": 78.0,
            "WNV_WINDDIRECTION": 220.0,
            "WNV_WINDSPEED": 7.5,
        },
        "FINISH": {
            "WNV_SKY": 1,
            "WNV_TEMPERATURE": 18.0,
            "WNV_RAIN_CHANCE": 20.0,
            "WNV_HUMIDITY": 65.0,
            "WNV_WINDDIRECTION": 180.0,
            "WNV_WINDSPEED": 4.0,
        },
    },
}

STRATEGY_USAGE_FIXTURE = {
    "Isaac Albala": [{"ve": 1.0}, {"ve": 0.98}, {"ve": 0.96}, {"ve": 0.94}],
    "Fernando Alonso": [{"ve": 1.0}, {"ve": 0.99}, {"ve": 0.97}],
}

GARAGE_WEAR_FIXTURE = {
    "wearables": {
        "body": {"aero": 0.04},
        "brakes": [0.88, 0.86, 0.84, 0.82],
        "suspension": [0.95, 0.94, 0.93, 0.92],
    }
}


def create_app() -> FastAPI:
    app = FastAPI(title="LMU REST Dummy Server", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/rest/sessions/weather")
    async def sessions_weather():
        return WEATHER_FIXTURE

    @app.get("/rest/strategy/usage")
    async def strategy_usage():
        return STRATEGY_USAGE_FIXTURE

    @app.get("/rest/garage/UIScreen/RepairAndRefuel")
    async def garage_repair_and_refuel():
        return GARAGE_WEAR_FIXTURE

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "lmu-dummy", "port": 6397}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.debug.lmu_dummy_server:app", host="127.0.0.1", port=6397, reload=False)
