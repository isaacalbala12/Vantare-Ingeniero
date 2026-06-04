"""
E2E tests for WebSocket multi-client behavior.

Verifies (no mocks — real FastAPI TestClient + real WebSocket):
  1. TestThreeClientsAllReceive    — 3 simultaneous clients all receive the same broadcast
  2. TestDisconnectMidBroadcast    — 1 of 3 disconnects; remaining 2 still receive; no crash
  3. TestMalformedJSON             — garbage payloads are handled; other clients unaffected
  4. TestReconnectAfterDisconnect  — a new connection after disconnect receives subsequent broadcasts

Run: pytest tests/test_ws_multi_client_e2e.py -v
"""
import json
import threading
import time
from queue import Empty, Queue
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

from src.models.messages import AlertMessage, BaseMessage
from src.routers.health import router as health_router
from src.routers.websocket import manager, router as ws_router


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def ws_app():
    """Minimal FastAPI app — WS + health, with no telemetry/strategy services.

    telemetry_reader=None and strategy_service=None cause the sender loops
    to early-return, so the only messages that ever hit a client are the ones
    WE trigger via manager.broadcast(). That keeps the assertions sharp.
    """
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
    return app


@pytest.fixture
def ws_client(ws_app):
    """Real TestClient (no mocks)."""
    return TestClient(ws_app)


@pytest.fixture(autouse=True)
def _reset_manager():
    """The manager is a module-level singleton — clear it before/after every test."""
    manager.active_connections.clear()
    yield
    manager.active_connections.clear()


# =============================================================================
# Helpers
# =============================================================================

# Sentinels pushed into the reader-thread queue when a WS closes or errors.
_SENTINEL_DISCONNECT = "__DISCONNECT__"
_SENTINEL_ERROR = "__ERROR__"


def _reader_loop(ws_session, q: "Queue") -> None:
    """Read text/close messages from a WS session and push them into q.

    Runs in a daemon thread. Exits cleanly on disconnect, putting a sentinel
    into q so the main test thread can wake up its `q.get(timeout=...)`.
    """
    try:
        while True:
            msg = ws_session.receive()
            mtype = msg.get("type")
            # starlette WebSocketTestSession.receive() returns ASGI events.
            # Server-to-client messages have type "websocket.send" (the
            # server sends them); client-to-server messages have type
            # "websocket.receive". We only care about server→client here.
            if mtype == "websocket.send" and "text" in msg:
                raw = msg["text"]
                try:
                    q.put(json.loads(raw))
                except json.JSONDecodeError:
                    # Push the raw string so the test can still see it.
                    q.put({"_raw": raw, "_non_json": True})
            elif mtype in ("websocket.disconnect", "websocket.close"):
                q.put(_SENTINEL_DISCONNECT)
                return
            # Binary websocket.send frames from the backend are ignored here
            # (we don't expect any in this test — sender loops are disabled).
    except WebSocketDisconnect:
        q.put(_SENTINEL_DISCONNECT)
    except Exception as exc:  # noqa: BLE001 — surface any unexpected reader failure
        q.put(_SENTINEL_ERROR)
        q.put(repr(exc))


def start_reader(ws_session) -> tuple:
    """Start a daemon reader thread. Returns (queue, thread)."""
    q: "Queue" = Queue()
    t = threading.Thread(target=_reader_loop, args=(ws_session, q), daemon=True)
    t.start()
    # Tiny yield so the thread actually starts and reaches _send_queue.get().
    time.sleep(0.02)
    return q, t


def drain_until_event(q: "Queue", event_name: str, timeout: float = 3.0) -> Optional[dict]:
    """Pop messages from q until we see one with the given `event` field, or time out.

    Messages whose `event` doesn't match are discarded (e.g. the `_raw` sentinel
    from a malformed payload). Returns the matching dict, or None on timeout /
    disconnect / error.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            item = q.get(timeout=0.05)
        except Empty:
            continue
        if item is _SENTINEL_DISCONNECT:
            return None
        if item is _SENTINEL_ERROR:
            return None
        if isinstance(item, dict) and item.get("event") == event_name:
            return item
        # Otherwise: not the event we want — keep draining.
    return None


def wait_for_connection_count(target: int, timeout: float = 3.0) -> bool:
    """Wait until manager.active_connections has exactly `target` connections.

    Disconnect handling runs on the event loop; polling absorbs the small
    window between `ws.close()` and the handler's `finally: manager.disconnect()`.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if len(manager.active_connections) == target:
            return True
        time.sleep(0.02)
    return False


def make_test_broadcast(event: str = "test_broadcast", msg_id: str = "1") -> AlertMessage:
    """Deterministic AlertMessage payload — easy to assert against."""
    return AlertMessage(
        event=event,
        alert_id=msg_id,
        category="fuel",
        message=f"test-{msg_id}",
        audio_priority="LOW",
        payload={"id": msg_id, "value": 42},
    )


def trigger_broadcast(ws_session, msg: BaseMessage) -> None:
    """Run `manager.broadcast(msg)` on the session's event-loop thread.

    `WebSocketTestSession.portal` is the anyio BlockingPortal that drives
    the ASGI app. `portal.call(coro_fn, *args)` invokes the function in
    the event-loop thread; if the return value is a coroutine it's awaited.
    Since `manager.broadcast` is `async def`, it returns a coroutine —
    the portal awaits it. This is the ONLY way to safely call the
    broadcast without crossing event-loop boundaries.
    """
    ws_session.portal.call(manager.broadcast, msg)


# =============================================================================
# Test classes
# =============================================================================

class TestThreeClientsAllReceive:
    """3 simultaneous WS clients must all receive the same broadcast."""

    def test_three_clients_get_identical_broadcast(self, ws_client):
        with ws_client.websocket_connect("/ws") as ws1:
            with ws_client.websocket_connect("/ws") as ws2:
                with ws_client.websocket_connect("/ws") as ws3:
                    q1, _ = start_reader(ws1)
                    q2, _ = start_reader(ws2)
                    q3, _ = start_reader(ws3)

                    assert wait_for_connection_count(3, timeout=2.0), (
                        f"Expected 3 active connections, got {len(manager.active_connections)}"
                    )

                    msg = make_test_broadcast(msg_id="hello-1")
                    trigger_broadcast(ws1, msg)

                    m1 = drain_until_event(q1, "test_broadcast", timeout=2.0)
                    m2 = drain_until_event(q2, "test_broadcast", timeout=2.0)
                    m3 = drain_until_event(q3, "test_broadcast", timeout=2.0)

                    assert m1 is not None, "Client 1 did not receive broadcast"
                    assert m2 is not None, "Client 2 did not receive broadcast"
                    assert m3 is not None, "Client 3 did not receive broadcast"

                    # All three must see the IDENTICAL payload — including
                    # the per-message `alert_id` and `data.value`.
                    assert m1 == m2 == m3, (
                        f"Clients got different messages:\n  m1={m1}\n  m2={m2}\n  m3={m3}"
                    )
                    assert m1["event"] == "test_broadcast"
                    assert m1["data"]["alert_id"] == "hello-1"
                    assert m1["data"]["payload"]["value"] == 42

    def test_sequential_broadcasts_received_in_order(self, ws_client):
        """3 broadcasts back-to-back — each client sees all 3, in order."""
        with ws_client.websocket_connect("/ws") as ws1:
            with ws_client.websocket_connect("/ws") as ws2:
                q1, _ = start_reader(ws1)
                q2, _ = start_reader(ws2)
                assert wait_for_connection_count(2, timeout=2.0)

                for i in range(3):
                    trigger_broadcast(ws1, make_test_broadcast(msg_id=f"seq-{i}"))

                ids1 = []
                ids2 = []
                for _ in range(3):
                    m1 = drain_until_event(q1, "test_broadcast", timeout=2.0)
                    m2 = drain_until_event(q2, "test_broadcast", timeout=2.0)
                    assert m1 is not None and m2 is not None
                    ids1.append(m1["data"]["alert_id"])
                    ids2.append(m2["data"]["alert_id"])

                assert ids1 == ["seq-0", "seq-1", "seq-2"]
                assert ids2 == ["seq-0", "seq-1", "seq-2"]

    def test_broadcast_after_late_joiner(self, ws_client):
        """Client 3 connects AFTER clients 1 and 2 — it should also receive broadcasts."""
        with ws_client.websocket_connect("/ws") as ws1:
            with ws_client.websocket_connect("/ws") as ws2:
                q1, _ = start_reader(ws1)
                q2, _ = start_reader(ws2)
                assert wait_for_connection_count(2, timeout=2.0)

                # Broadcast with only 2 clients
                trigger_broadcast(ws1, make_test_broadcast(msg_id="two-only"))
                m1 = drain_until_event(q1, "test_broadcast", timeout=2.0)
                m2 = drain_until_event(q2, "test_broadcast", timeout=2.0)
                assert m1 is not None and m2 is not None
                assert m1["data"]["alert_id"] == "two-only"

                # Now client 3 joins
                with ws_client.websocket_connect("/ws") as ws3:
                    q3, _ = start_reader(ws3)
                    assert wait_for_connection_count(3, timeout=2.0)

                    # Broadcast reaches all 3
                    trigger_broadcast(ws2, make_test_broadcast(msg_id="all-three"))
                    m1 = drain_until_event(q1, "test_broadcast", timeout=2.0)
                    m2 = drain_until_event(q2, "test_broadcast", timeout=2.0)
                    m3 = drain_until_event(q3, "test_broadcast", timeout=2.0)
                    assert m1 is not None and m2 is not None and m3 is not None
                    assert m1 == m2 == m3
                    assert m3["data"]["alert_id"] == "all-three"


class TestDisconnectMidBroadcast:
    """Client disconnect mid-broadcast must NOT crash the backend or starve other clients."""

    def test_one_disconnect_two_still_receive(self, ws_client):
        """1 of 3 disconnects explicitly; the 2 remaining receive the next broadcast.

        This is the most common production failure — one Tauri window crashes
        or the user closes one of the dashboards. The other dashboards must
        keep getting data and the backend must keep running.
        """
        with ws_client.websocket_connect("/ws") as ws1:
            with ws_client.websocket_connect("/ws") as ws2:
                with ws_client.websocket_connect("/ws") as ws3:
                    q1, _ = start_reader(ws1)
                    q2, _ = start_reader(ws2)
                    q3, _ = start_reader(ws3)
                    assert wait_for_connection_count(3, timeout=2.0)

                    # Sanity: pre-disconnect broadcast reaches all 3
                    trigger_broadcast(ws1, make_test_broadcast(msg_id="pre-disconnect"))
                    assert drain_until_event(q1, "test_broadcast", timeout=2.0) is not None
                    assert drain_until_event(q2, "test_broadcast", timeout=2.0) is not None
                    assert drain_until_event(q3, "test_broadcast", timeout=2.0) is not None

                    # Disconnect client 2 mid-flight
                    ws2.close()

                    # The handler's finally block removes it from the manager
                    assert wait_for_connection_count(2, timeout=3.0), (
                        f"manager did not shrink: still {len(manager.active_connections)} active"
                    )

                    # Now broadcast — must reach clients 1 and 3, backend must not raise
                    msg = make_test_broadcast(msg_id="after-disconnect")
                    trigger_broadcast(ws1, msg)

                    m1 = drain_until_event(q1, "test_broadcast", timeout=2.0)
                    m3 = drain_until_event(q3, "test_broadcast", timeout=2.0)

                    assert m1 is not None, "Client 1 (still connected) did not receive"
                    assert m3 is not None, "Client 3 (still connected) did not receive"
                    assert m1 == m3
                    assert m1["data"]["alert_id"] == "after-disconnect"

                    # Backend didn't crash: /health still responds
                    resp = ws_client.get("/health")
                    assert resp.status_code == 200

    def test_broadcast_during_disconnect_window(self, ws_client):
        """Fire a broadcast IMMEDIATELY after close() — backend must absorb it gracefully.

        This is the tightest race: the handler's finally block is still running
        (cancelling subtasks, awaiting gather) when the next broadcast arrives.
        ConnectionManager.broadcast uses `asyncio.gather(..., return_exceptions=True)`
        so a failure to write to the dead socket is swallowed.
        """
        with ws_client.websocket_connect("/ws") as ws1:
            with ws_client.websocket_connect("/ws") as ws2:
                with ws_client.websocket_connect("/ws") as ws3:
                    q1, _ = start_reader(ws1)
                    q3, _ = start_reader(ws3)
                    assert wait_for_connection_count(3, timeout=2.0)

                    # Disconnect + immediate broadcast — no sleep in between.
                    ws2.close()
                    trigger_broadcast(ws1, make_test_broadcast(msg_id="racy"))

                    # The broadcast itself must not raise
                    m1 = drain_until_event(q1, "test_broadcast", timeout=2.0)
                    m3 = drain_until_event(q3, "test_broadcast", timeout=2.0)
                    assert m1 is not None, "Client 1 lost the racy broadcast"
                    assert m3 is not None, "Client 3 lost the racy broadcast"
                    assert m1 == m3

        # All three must be cleaned up
        assert wait_for_connection_count(0, timeout=3.0), (
            f"Lingering connections: {len(manager.active_connections)}"
        )

    def test_all_clients_disconnect_manager_clears(self, ws_client):
        """When the last `with` block exits, manager.active_connections goes to 0."""
        with ws_client.websocket_connect("/ws") as ws1:
            with ws_client.websocket_connect("/ws") as ws2:
                with ws_client.websocket_connect("/ws") as ws3:
                    assert wait_for_connection_count(3, timeout=2.0)

        # All three `with` blocks have exited by now → all disconnects processed
        assert wait_for_connection_count(0, timeout=3.0), (
            f"Manager leaked connections: {len(manager.active_connections)}"
        )


class TestMalformedJSON:
    """Garbage payloads from a client must NOT crash the backend or affect other clients."""

    def test_garbage_text_does_not_crash_backend(self, ws_client):
        """ws_bad sends `not json {{{` — other clients keep getting broadcasts."""
        with ws_client.websocket_connect("/ws") as ws_bad:
            with ws_client.websocket_connect("/ws") as ws_good1:
                with ws_client.websocket_connect("/ws") as ws_good2:
                    q_bad, _ = start_reader(ws_bad)
                    q_good1, _ = start_reader(ws_good1)
                    q_good2, _ = start_reader(ws_good2)

                    assert wait_for_connection_count(3, timeout=2.0)

                    # Send malformed JSON on the bad client
                    ws_bad.send_text("not json {{{")
                    time.sleep(0.1)

                    # Backend must still be alive and well
                    assert len(manager.active_connections) == 3, (
                        f"Backend dropped a connection on garbage: {len(manager.active_connections)} active"
                    )
                    resp = ws_client.get("/health")
                    assert resp.status_code == 200

                    # Broadcast must still reach all 3 (the bad one is still connected!)
                    trigger_broadcast(ws_bad, make_test_broadcast(msg_id="post-garbage"))
                    m_bad = drain_until_event(q_bad, "test_broadcast", timeout=2.0)
                    m_g1 = drain_until_event(q_good1, "test_broadcast", timeout=2.0)
                    m_g2 = drain_until_event(q_good2, "test_broadcast", timeout=2.0)

                    assert m_bad is not None, "Bad client dead after sending garbage"
                    assert m_g1 is not None, "Good client 1 lost the post-garbage broadcast"
                    assert m_g2 is not None, "Good client 2 lost the post-garbage broadcast"
                    assert m_bad == m_g1 == m_g2

    def test_barrage_of_malformed_messages(self, ws_client):
        """A rapid succession of garbage payloads must not degrade the connection."""
        with ws_client.websocket_connect("/ws") as ws1:
            with ws_client.websocket_connect("/ws") as ws2:
                q1, _ = start_reader(ws1)
                q2, _ = start_reader(ws2)
                assert wait_for_connection_count(2, timeout=2.0)

                garbage_payloads = [
                    "{",
                    "}",
                    "{{{",
                    "null,",
                    "::::",
                    '"unterminated',
                    "[1, 2, 3,",        # truncated array
                    '{"key": undefined}',  # JS-ism, not valid JSON
                    "True",              # Python bool, not JSON
                    "None",              # Python None, not JSON
                ]
                for garbage in garbage_payloads:
                    ws1.send_text(garbage)
                time.sleep(0.2)

                # Both connections must still be tracked
                assert len(manager.active_connections) == 2
                # /health must still respond
                assert ws_client.get("/health").status_code == 200

                # Broadcast must still work
                trigger_broadcast(ws1, make_test_broadcast(msg_id="post-barrage"))
                m1 = drain_until_event(q1, "test_broadcast", timeout=2.0)
                m2 = drain_until_event(q2, "test_broadcast", timeout=2.0)
                assert m1 is not None, "Client 1 dead after malformed barrage"
                assert m2 is not None, "Client 2 didn't receive post-barrage broadcast"
                assert m1 == m2
                assert m1["data"]["alert_id"] == "post-barrage"

    def test_garbage_on_one_does_not_affect_others_ability_to_send(self, ws_client):
        """The clean clients must still be able to send VALID JSON while the bad one spams garbage."""
        with ws_client.websocket_connect("/ws") as ws_bad:
            with ws_client.websocket_connect("/ws") as ws_clean:
                q_bad, _ = start_reader(ws_bad)
                q_clean, _ = start_reader(ws_clean)
                assert wait_for_connection_count(2, timeout=2.0)

                # Spam garbage from the bad client
                for _ in range(5):
                    ws_bad.send_text("not valid json @#$%")
                time.sleep(0.1)

                # The clean client sends a valid pilot_question — the handler
                # logs a warning ("IntelligenceEngine no disponible") but
                # does NOT raise, and the WS stays open.
                ws_clean.send_json({
                    "event": "pilot_question",
                    "data": {"question": "What tire strategy should I use?"}
                })
                time.sleep(0.1)

                # Both connections still tracked
                assert len(manager.active_connections) == 2

                # Both still receive broadcasts
                trigger_broadcast(ws_clean, make_test_broadcast(msg_id="clean-survived"))
                m_bad = drain_until_event(q_bad, "test_broadcast", timeout=2.0)
                m_clean = drain_until_event(q_clean, "test_broadcast", timeout=2.0)
                assert m_bad is not None
                assert m_clean is not None
                assert m_bad == m_clean


class TestReconnectAfterDisconnect:
    """A fresh WS connection after a previous one disconnected must receive subsequent broadcasts."""

    def test_single_client_disconnect_then_reconnect(self, ws_client):
        """Client 1 connects, receives, disconnects; client 2 (new) connects and receives."""
        # Phase 1: connect, receive, disconnect
        with ws_client.websocket_connect("/ws") as ws1:
            q1, _ = start_reader(ws1)
            assert wait_for_connection_count(1, timeout=2.0)

            trigger_broadcast(ws1, make_test_broadcast(msg_id="phase1"))
            m1 = drain_until_event(q1, "test_broadcast", timeout=2.0)
            assert m1 is not None
            assert m1["data"]["alert_id"] == "phase1"

            ws1.close()
            assert wait_for_connection_count(0, timeout=3.0)

        # Phase 2: NEW connection, fresh broadcast
        with ws_client.websocket_connect("/ws") as ws2:
            q2, _ = start_reader(ws2)
            assert wait_for_connection_count(1, timeout=2.0)

            trigger_broadcast(ws2, make_test_broadcast(msg_id="phase2"))
            m2 = drain_until_event(q2, "test_broadcast", timeout=2.0)
            assert m2 is not None, "Reconnected client did not receive broadcast"
            assert m2["data"]["alert_id"] == "phase2"

    def test_replacement_client_takes_over(self, ws_client):
        """After disconnect, two new clients can connect and both receive broadcasts."""
        with ws_client.websocket_connect("/ws") as ws_old:
            q_old, _ = start_reader(ws_old)
            assert wait_for_connection_count(1, timeout=2.0)
            ws_old.close()
            assert wait_for_connection_count(0, timeout=3.0)

        with ws_client.websocket_connect("/ws") as ws_new1:
            with ws_client.websocket_connect("/ws") as ws_new2:
                q_n1, _ = start_reader(ws_new1)
                q_n2, _ = start_reader(ws_new2)
                assert wait_for_connection_count(2, timeout=2.0)

                trigger_broadcast(ws_new1, make_test_broadcast(msg_id="replacement"))

                m1 = drain_until_event(q_n1, "test_broadcast", timeout=2.0)
                m2 = drain_until_event(q_n2, "test_broadcast", timeout=2.0)
                assert m1 is not None and m2 is not None
                assert m1 == m2
                assert m1["data"]["alert_id"] == "replacement"

    def test_repeated_disconnect_reconnect_cycles(self, ws_client):
        """Three disconnect/reconnect cycles — the manager must not leak state."""
        for cycle in range(3):
            with ws_client.websocket_connect("/ws") as ws:
                q, _ = start_reader(ws)
                assert wait_for_connection_count(1, timeout=2.0), (
                    f"Cycle {cycle}: expected 1 active, got {len(manager.active_connections)}"
                )

                trigger_broadcast(ws, make_test_broadcast(msg_id=f"cycle-{cycle}"))
                m = drain_until_event(q, "test_broadcast", timeout=2.0)
                assert m is not None, f"Cycle {cycle}: no broadcast received"
                assert m["data"]["alert_id"] == f"cycle-{cycle}"

            # After each cycle, the manager must be empty (no leak)
            assert wait_for_connection_count(0, timeout=3.0), (
                f"Cycle {cycle}: leaked {len(manager.active_connections)} connections"
            )
