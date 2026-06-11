#!/usr/bin/env python3
"""Smoke test for packaged backend: /health + WebSocket probe."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def wait_health(port: int, timeout: float) -> dict:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                data = json.loads(resp.read().decode())
                if data.get("status") == "ok":
                    return data
        except Exception as exc:  # noqa: BLE001 — smoke poll
            last_err = exc
            time.sleep(0.5)
    raise RuntimeError(f"Health check failed after {timeout}s: {last_err}")


async def ws_probe(port: int, duration: float) -> dict:
    import websockets

    ws_url = f"ws://127.0.0.1:{port}/ws"
    binary_frames = 0
    json_events: list[str] = []
    async with websockets.connect(ws_url, open_timeout=8) as ws:
        await ws.send(
            json.dumps(
                {
                    "event": "config_update",
                    "data": {
                        "engineerEnabled": False,
                        "spotterEnabled": True,
                        "speakOnlyWhenSpokenTo": True,
                        "personalityProfileId": "default",
                    },
                }
            )
        )
        deadline = time.time() + duration
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
            except TimeoutError:
                continue
            if isinstance(msg, bytes):
                binary_frames += 1
                continue
            try:
                parsed = json.loads(msg)
            except json.JSONDecodeError:
                continue
            ev = parsed.get("event")
            if not ev and isinstance(parsed.get("data"), dict):
                ev = parsed["data"].get("event")
            if ev:
                json_events.append(str(ev))
    return {
        "binary_frames": binary_frames,
        "json_event_count": len(json_events),
        "json_events": json_events,
        "json_events_sample": json_events[:15],
    }


def check_bundle_main(bundle_main: Path) -> dict:
    text = bundle_main.read_text(encoding="utf-8", errors="replace")
    return {
        "native_telemetry_reader": "offline=not use_native" in text,
        "uses_native_flag": "native_telemetry_enabled" in text,
    }


def inject_alert_smoke(port: int) -> dict:
    """VC-R02: POST /debug/inject_alert to verify client-side eval (DEBUG only)."""
    url = f"http://127.0.0.1:{port}/debug/inject_alert"
    body = json.dumps({
        "message": "Coche a la derecha",
        "category": "proximity",
        "audio_priority": "2",
        "service": "spotter",
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return {"injected": True, "response": data}
    except Exception as exc:
        return {"injected": False, "error": str(exc)}


async def run_smoke(args: argparse.Namespace) -> dict:
    health = wait_health(args.port, args.health_timeout)

    # VC-R02: Optional alert inject for dev builds with DEBUG=1
    inject_result = None
    if args.inject_alert:
        inject_result = inject_alert_smoke(args.port)

    ws = await ws_probe(args.port, args.ws_duration)

    proactive_events = {"llm_pending", "advice_start", "advice_token", "advice_end", "commentary_end"}
    seen_proactive = [ev for ev in ws.get("json_events", []) if ev in proactive_events]

    result: dict = {
        "ok": True,
        "port": args.port,
        "health": {
            "telemetry_source": (health.get("telemetry") or {}).get("source"),
            "shared_memory_status": (health.get("shared_memory") or {}).get("status"),
            "offline_mode": (health.get("shared_memory") or {}).get("offline_mode"),
            "llm_configured": (health.get("llm") or {}).get("configured"),
        },
        "websocket": ws,
    }

    if inject_result is not None:
        result["alert_inject"] = inject_result

    if ws["binary_frames"] == 0:
        result["websocket"]["note"] = "0 binary frames (LMU closed or not on track — acceptable for smoke)"

    if seen_proactive:
        result["ok"] = False
        result["error"] = (
            "Proactive engineer LLM events without PTT: "
            + ", ".join(seen_proactive)
        )

    if args.bundle_main:
        bundle_path = Path(args.bundle_main)
        if not bundle_path.is_file():
            raise FileNotFoundError(f"Bundle main not found: {bundle_path}")
        result["bundle"] = check_bundle_main(bundle_path)
        if not result["bundle"]["native_telemetry_reader"]:
            result["ok"] = False
            result["error"] = "Bundled main.py missing native telemetry reader wiring"

    if ws["json_event_count"] == 0 and ws["binary_frames"] == 0:
        result["ok"] = False
        result["error"] = "WebSocket connected but no traffic in probe window"

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Release backend smoke probe")
    parser.add_argument("--port", type=int, default=8009)
    parser.add_argument("--health-timeout", type=float, default=60)
    parser.add_argument("--ws-duration", type=float, default=6)
    parser.add_argument("--bundle-main", type=Path, default=None)
    parser.add_argument("--inject-alert", action="store_true", help="VC-R02: inject proximity alert via /debug/inject_alert (requires DEBUG=1)")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    try:
        result = asyncio.run(run_smoke(args))
    except Exception as exc:  # noqa: BLE001 — smoke entrypoint
        result = {"ok": False, "error": str(exc)}

    payload = json.dumps(result, indent=2, ensure_ascii=False)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
