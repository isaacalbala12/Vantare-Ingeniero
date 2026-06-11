#!/usr/bin/env python3
"""Fast gate: voice contract tests only (~30-60s).

Usage from repo root:
  python scripts/verify_voice_contract.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
NPM = "npm.cmd" if sys.platform == "win32" else "npm"


def run(cmd: list[str], cwd: Path) -> None:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main() -> None:
    print("=== verify_voice_contract ===\n")

    print("[1/2] Backend voice contract tests (VC-B*)...")
    run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_voice_contract_backend.py",
            "-q",
            "--tb=line",
        ],
        BACKEND,
    )

    print("\n[2/2] Frontend voice contract tests (VC-A*, VC-P*, VC-C*, VC-Q*, VC-R*)...")
    run(
        [
            NPM,
            "test",
            "--",
            "--run",
            "voiceContractMatrix.test.ts",
            "voiceContractPtt.test.ts",
            "ttsQueue.contract.test.ts",
            "configMigration.voice.test.ts",
        ],
        FRONTEND,
    )

    print("\n=== voice contract OK ===")


if __name__ == "__main__":
    main()
