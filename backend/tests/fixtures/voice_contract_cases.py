"""Voice contract backend test cases — mirrors docs/voice-contract.md §4.5.

Used by test_voice_contract_backend.py.
"""

from __future__ import annotations

VC_B_CASES = [
    {
        "id": "VC-B01",
        "engineer": False,
        "speakOnly": True,
        "action": "proactive_cycle",
        "expect_emits_ws": False,
        "description": "Proactive cycle blocked when engineer off + speakOnly",
    },
    {
        "id": "VC-B02",
        "engineer": False,
        "speakOnly": True,
        "action": "ptt",
        "expect_emits_ws": True,
        "description": "PTT still emits voice_response regardless of config",
    },
    {
        "id": "VC-B03",
        "engineer": True,
        "speakOnly": True,
        "action": "fuel_trigger",
        "expect_emits_ws": False,
        "description": "Fuel trigger suppressed by speakOnly backend",
    },
    {
        "id": "VC-B04",
        "engineer": True,
        "speakOnly": False,
        "action": "fuel_trigger",
        "expect_emits_ws": True,
        "description": "Fuel trigger emitted when engineer on + speakOnly off",
    },
    {
        "id": "VC-B05",
        "engineer": "any",
        "speakOnly": "any",
        "action": "spotter_proximity",
        "expect_emits_ws": True,
        "description": "Spotter proximity always emits (frontend filters by toggle)",
    },
]
