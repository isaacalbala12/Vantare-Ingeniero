import time, threading, json
from queue import Queue
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

def reader(ws, q, name):
    print('  [', name, '] reader started, queue id:', hex(id(q)))
    while True:
        print('  [', name, '] calling ws.receive()')
        msg = ws.receive()
        print('  [', name, '] ws.receive() returned:', msg.get('type'))
        if msg.get('type') == 'websocket.receive' and 'text' in msg:
            text = msg['text']
            q.put(json.loads(text))
            print('  [', name, '] got message, q.size=', q.qsize(), 'q.id=', hex(id(q)))
        elif msg.get('type') in ('websocket.disconnect', 'websocket.close'):
            q.put(None)
            return

with c.websocket_connect('/ws') as ws1:
    with c.websocket_connect('/ws') as ws2:
        with c.websocket_connect('/ws') as ws3:
            print('Active:', len(manager.active_connections))

            q1, q2, q3 = Queue(), Queue(), Queue()
            t1 = threading.Thread(target=reader, args=(ws1, q1, 'ws1'), daemon=True)
            t2 = threading.Thread(target=reader, args=(ws2, q2, 'ws2'), daemon=True)
            t3 = threading.Thread(target=reader, args=(ws3, q3, 'ws3'), daemon=True)
            t1.start(); t2.start(); t3.start()
            time.sleep(0.3)

            msg = AlertMessage(event='test', alert_id='1', category='c',
                               message='m', audio_priority='LOW', payload={})
            print('Triggering broadcast...')
            ws1.portal.call(manager.broadcast, msg)
            print('Broadcast done, sleeping 0.5s')
            time.sleep(0.5)
            print('q1 size:', q1.qsize(), 'q2 size:', q2.qsize(), 'q3 size:', q3.qsize())
