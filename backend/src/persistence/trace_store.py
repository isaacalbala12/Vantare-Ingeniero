"""Grabación y reproducción de traces de telemetría (.trace JSONL)."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
TRACES_DIR = os.path.join(DATA_DIR, "traces")

FrameCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class TraceStore:
    """Graba frames de telemetría y los reproduce a velocidad configurable."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recording = False
        self._current_trace_id: str | None = None
        self._current_path: str | None = None
        self._started_at: float = 0.0
        self._record_origin: float = 0.0
        os.makedirs(TRACES_DIR, exist_ok=True)

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    @property
    def current_trace_id(self) -> str | None:
        with self._lock:
            return self._current_trace_id

    def start_recording(self, trace_id: str | None = None) -> str:
        with self._lock:
            if self._recording:
                raise RuntimeError("Ya hay una grabación en curso")
            tid = trace_id or time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
            path = os.path.join(TRACES_DIR, f"{tid}.trace")
            self._recording = True
            self._current_trace_id = tid
            self._current_path = path
            self._started_at = time.time()
            self._record_origin = time.monotonic()
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            return tid

    def stop_recording(self) -> str | None:
        with self._lock:
            if not self._recording:
                return None
            tid = self._current_trace_id
            self._recording = False
            self._current_trace_id = None
            self._current_path = None
            return tid

    def append_frame(self, frame: dict[str, Any]) -> None:
        if not frame:
            return
        with self._lock:
            if not self._recording or not self._current_path:
                return
            rel_t = time.monotonic() - self._record_origin
            line = json.dumps({"t": round(rel_t, 4), "frame": frame}, ensure_ascii=False)
            with open(self._current_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def list_traces(self) -> list[dict[str, Any]]:
        traces: list[dict[str, Any]] = []
        if not os.path.isdir(TRACES_DIR):
            return traces
        for entry in sorted(os.listdir(TRACES_DIR)):
            if not entry.endswith(".trace"):
                continue
            path = os.path.join(TRACES_DIR, entry)
            meta = self._trace_meta(path, entry[:-6])
            traces.append(meta)
        return sorted(traces, key=lambda t: t.get("started_at", 0), reverse=True)

    def _trace_meta(self, path: str, trace_id: str) -> dict[str, Any]:
        frame_count = 0
        duration = 0.0
        last_t = 0.0
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    frame_count += 1
                    last_t = float(row.get("t", 0.0))
            duration = last_t
        except (OSError, json.JSONDecodeError):
            pass
        stat = os.stat(path)
        return {
            "id": trace_id,
            "path": path,
            "frames": frame_count,
            "duration_s": round(duration, 2),
            "size_bytes": stat.st_size,
            "started_at": int(stat.st_mtime - duration) if duration else int(stat.st_mtime),
        }

    def _load_entries(self, trace_id: str) -> list[dict[str, Any]]:
        path = os.path.join(TRACES_DIR, f"{trace_id}.trace")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Trace no encontrado: {trace_id}")
        entries: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
        return entries

    async def playback(
        self,
        trace_id: str,
        callback: FrameCallback,
        speed: float = 1.0,
    ) -> int:
        if speed <= 0:
            raise ValueError("speed debe ser > 0")
        entries = self._load_entries(trace_id)
        if not entries:
            return 0

        start = time.monotonic()
        t0 = float(entries[0].get("t", 0.0))
        count = 0
        for entry in entries:
            rel = float(entry.get("t", 0.0)) - t0
            target = start + (rel / speed)
            wait = target - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            frame = entry.get("frame") or {}
            result = callback(frame)
            if asyncio.iscoroutine(result):
                await result
            count += 1
        return count
