import asyncio
import json
import websockets
import httpx


async def test_websocket_telemetry():
    """Verifica que el backend recibe y procesa telemetría del frontend vía WebSocket."""
    base_url = "http://127.0.0.1:8008"
    ws_url = "ws://127.0.0.1:8008/ws"

    async with websockets.connect(ws_url) as ws:
        print("[TEST] WebSocket conectado")

        telemetry_payload = {
            "event": "telemetry",
            "data": {
                "timestamp": 1234567890.0,
                "player": {
                    "speed": 250.0,
                    "fuel": 45.5,
                    "current_lap": 5,
                    "place": 3,
                    "in_pits": False,
                },
                "engine": {"rpm": 8500, "gear": 5},
                "tyres": {"wear": [0.15, 0.18, 0.12, 0.14]},
            },
        }

        await ws.send(json.dumps(telemetry_payload))
        await asyncio.sleep(0.5)

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/health")
            assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
            data = resp.json()
            ft = data.get("frontend_telemetry", {})
            assert ft.get("received") == True, (
                f"frontend_telemetry.received debería ser true, es {ft}"
            )

        print("[TEST] ✅ Pipeline WebSocket verificado")
        return True


if __name__ == "__main__":
    result = asyncio.run(test_websocket_telemetry())
    print(f"Resultado: {'✅ PASÓ' if result else '❌ FALLÓ'}")
