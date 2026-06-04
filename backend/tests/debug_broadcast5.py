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

with c.websocket_connect('/ws') as ws1:
    with c.websocket_connect('/ws') as ws2:
        with c.websocket_connect('/ws') as ws3:
            print('Active:', len(manager.active_connections))
            print('ws1 _send_queue id:', hex(id(ws1._send_queue)))
            print('ws2 _send_queue id:', hex(id(ws2._send_queue)))
            print('ws3 _send_queue id:', hex(id(ws3._send_queue)))

            msg = AlertMessage(event='test', alert_id='1', category='c',
                               message='m', audio_priority='LOW', payload={})
            print('Triggering broadcast...')
            ws1.portal.call(manager.broadcast, msg)
            print('Broadcast done')

            time.sleep(0.3)
            print('After broadcast:')
            print('  ws1 _send_queue size:', ws1._send_queue.qsize())
            print('  ws2 _send_queue size:', ws2._send_queue.qsize())
            print('  ws3 _send_queue size:', ws3._send_queue.qsize())
