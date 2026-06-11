"""Guard: no asignar directamente properties read-only del dominio voice/race."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

FORBIDDEN_PATTERNS = [
    (re.compile(r"\.enable_commentary_batch\s*="), "use set_enable_commentary_batch()"),
]

SCAN_FILES = [
    SRC / "main.py",
    SRC / "intelligence" / "engine.py",
    SRC / "routers" / "websocket.py",
]


def test_no_forbidden_property_assignments_in_critical_paths():
    violations: list[str] = []
    for path in SCAN_FILES:
        text = path.read_text(encoding="utf-8")
        for pattern, hint in FORBIDDEN_PATTERNS:
            for match in pattern.finditer(text):
                line_no = text[: match.start()].count("\n") + 1
                violations.append(f"{path.name}:{line_no} — {hint}")
    assert not violations, "Forbidden property assigns:\n" + "\n".join(violations)
