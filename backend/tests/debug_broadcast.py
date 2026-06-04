import time, threading, json
from queue import Queue, Empty
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.routers.health import router as health_router
from src.routers.websocket import router as ws_router, manager
from src.models.messages import AlertMessage

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

# Monkey-patch send_json to log
import starlette.websockets
orig_send_json = starlette.websockets.WebSocket.send_json
def debug_send_json(self, data, mode='text'):
    print('  >> send_json called on', hex(id(self)), 'app_state=', self.application_state.name, 'event=', data.get('event'))
    return orig_send_json(self, data, mode)
starlette.websockets.WebSocket.send_json = debug_send_json

def reader(ws, q, name):
    try:
        while True:
            msg = ws.receive()
            if msg.get('type') == 'websocket.receive' and 'text' in msg:
                text = msg['text']
                q.put(json.loads(text))
                print('  [', name, '] got:', text[:80])
            elif msg.get('type') in ('websocket.disconnect', 'websocket.close'):
                q.put(None)
                return
    except Exception as e:
        print('  [', name, '] reader error:', e)

with c.websocket_connect('/ws') as ws1:
    with c.websocket_connect('/ws') as ws2:
        with c.websocket_connect('/ws') as ws3:
            print('Active connections:', len(manager.active_connections))
            for conn in manager.active_connections:
                print('  conn id=', hex(id(conn)))

            q1, q2, q3 = Queue(), Queue(), Queue()
            t1 = threading.Thread(target=reader, args=(ws1, q1, 'ws1'), daemon=True)
            t2 = threading.Thread(target=reader, args=(ws2, q2, 'ws2'), daemon=True)
            t3 = threading.Thread(target=reader, args=(ws3, q3, 'ws3'), daemon=True)
            t1.start(); t2.start(); t3.start()

            time.sleep(0.2)

            msg = AlertMessage(event='test', alert_id='1', category='c',
                               message='m', audio_priority='LOW', payload={})
            print('Triggering broadcast...')
            ws1.portal.call(manager.broadcast, msg)
            print('Broadcast done')

            time.sleep(0.5)
            print('q1 size:', q1.qsize())
            print('q2 size:', q2.qsize())
            print('q3 size:', q3.qsize())
