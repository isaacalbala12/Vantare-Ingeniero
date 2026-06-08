#!/usr/bin/env python3

"""Gate CI: pipelines de audio + triggers (sin LMU).



Uso desde la raíz del repo:

  python scripts/verify_audio_pipeline.py

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

    print("=== Verificación pipeline audio + triggers ===\n")



    print("[1/3] Backend pytest (matriz + contrato spotter + engine + alpha parity)...")

    run(

        [

            sys.executable,

            "-m",

            "pytest",

            "tests/test_audio_trigger_matrix.py",

            "tests/test_spotter_audio_contract.py",

            "tests/test_preemption.py",

            "tests/test_commentary_orchestrator.py",

            "tests/test_commentary_llm_formatter.py",

            "tests/test_personality_pack.py",

            "tests/test_verbosity_controller.py",

            "tests/test_engine_commentary.py",

            "tests/test_engine_runtime_config.py",

            "tests/test_engine_proactive_cycle.py",

            "tests/test_config_sync_ws.py",

            "tests/test_spotter_runtime_config.py",

            "tests/test_proactive_monitors.py",

            "tests/test_proactive_monitors_extended.py",

            "tests/test_pit_prediction.py",

            "tests/test_fuel_percentile.py",

            "tests/test_pearls_voice.py",

            "tests/test_braking_zones_mute.py",

            "-v",

            "--tb=short",

        ],

        BACKEND,

    )



    print("\n[2/3] Frontend vitest (matriz + pipeline integración)...")

    run(

        [

            NPM,

            "test",

            "--",

            "audioTriggerMatrix.test.ts",

            "audioPipeline.integration.test.ts",

            "alertVoice.test.ts",

            "configUpdatePayload.test.ts",

            "priorityAudioQueue.test.ts",

            "ttsCache.test.ts",

            "useWebSocket.spotter.test.ts",

            "spotterPipeline.integration.test.ts",

            "--run",

        ],

        FRONTEND,

    )



    print("\n[3/3] Spotter pipeline smoke...")

    run([sys.executable, str(ROOT / "scripts" / "verify_spotter_pipeline.py")], ROOT)



    print("\n=== Pipeline audio OK ===")

    print("Checklist manual LMU: .omo/evidence/audio-lmu-validation.md")

    print("Alpha parity smoke: python scripts/verify_alpha_parity.py")





if __name__ == "__main__":

    main()

