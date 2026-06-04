import time, threading, json
from queue import Queue
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.routers.health import router as health_router
from src.routers.websocket import router as ws_router, manager

app = FastAPI()
app.include_router(health_router)
app.include_router(ws_router)
app.state.telemetry_reader = None
app.state.strategy_service = None
app.state.intelligence_engine = None
app.state.spotter_service = None
app.state.latest_client_frame = None
app.state.latest_strategy_frame = None
app.state._last_telemetry_t = 0.0

c = TestClient(app)

# Monkey-patch _asgi_send to log
import starlette.testclient
orig_asgi_send = starlette.testclient.WebSocketTestSession._asgi_send
async def debug_asgi_send(self, message):
    print('  >> _asgi_send called on', hex(id(self)), 'type=', message.get('type'), 'queue_size_before=', self._send_queue.qsize())
    res = await orig_asgi_send(self, message)
    print('  << _asgi_send done, queue_size_after=', self._send_queue.qsize())
    return res
starlette.testclient.WebSocketTestSession._asgi_send = debug_asgi_send

with c.websocket_connect('/ws') as ws1:
    with c.websocket_connect('/ws') as ws2:
        with c.websocket_connect('/ws') as ws3:
            print('Active:', len(manager.active_connections))

            # Try direct call to broadcast
            print('Triggering broadcast...')
            ws1.portal.call(manager.broadcast, manager.active_connections.copy().__iter__().__next__() and __import__('src.models.messages', fromlist=['AlertMessage']).AlertMessage(event='test', alert_id='1', category='c', message='m', audio_priority='LOW', payload={}))

            time.sleep(0.5)
