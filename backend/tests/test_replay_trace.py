import json
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "replay" / "minimal_race.trace"


def test_replay_trace_outputs_timeline_json():
    script = Path(__file__).resolve().parents[1] / "scripts" / "replay_trace.py"
    out = subprocess.check_output(
        [sys.executable, str(script), str(FIXTURE), "--hz", "20"],
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    timeline = json.loads(out)
    assert isinstance(timeline, list)
    assert any(entry.get("event_id") for entry in timeline)
