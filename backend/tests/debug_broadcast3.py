import asyncio
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

# Monkey-patch the bound _asgi_send on the sessions
import starlette.websockets
orig_send = starlette.websockets.WebSocket.send
async def debug_send(self, message):
    print('  send() called on', hex(id(self)), 'state=', self.application_state.name, 'msg.type=', message.get('type'))
    print('    self._send =', self._send, 'type:', type(self._send).__name__)
    try:
        result = await orig_send(self, message)
        print('  send() done on', hex(id(self)))
        return result
    except Exception as e:
        print('  send() RAISED on', hex(id(self)), ':', repr(e))
        raise
starlette.websockets.WebSocket.send = debug_send

# Patch _asgi_send
import starlette.testclient
orig_asgi_send = starlette.testclient.WebSocketTestSession._asgi_send
async def debug_asgi_send(self, message):
    print('  _asgi_send() on', hex(id(self)), 'msg.type=', message.get('type'))
    res = await orig_asgi_send(self, message)
    print('  _asgi_send() done on', hex(id(self)))
    return res
starlette.testclient.WebSocketTestSession._asgi_send = debug_asgi_send

with c.websocket_connect('/ws') as ws1:
    with c.websocket_connect('/ws') as ws2:
        with c.websocket_connect('/ws') as ws3:
            print('Active:', len(manager.active_connections))

            print('Triggering broadcast...')
            ws1.portal.call(manager.broadcast, manager.active_connections.copy().__iter__().__next__() and __import__('src.models.messages', fromlist=['AlertMessage']).AlertMessage(event='test', alert_id='1', category='c', message='m', audio_priority='LOW', payload={}))
            time.sleep(0.3)
