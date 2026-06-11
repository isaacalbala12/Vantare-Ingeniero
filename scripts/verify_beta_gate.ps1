# scripts/verify_beta_gate.ps1
# Beta gate: encadena verify_voice_contract + pytest subset + frontend tests minimos.
#   -WithDoctor: ejecuta doctor.ps1 (requiere backend :8008)
# Exit 0 = beta gate OK

param([switch]$WithDoctor)

$ErrorActionPreference = "Continue"
$log = Join-Path $env:TEMP "vantare-beta-gate-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

function Log($msg) {
    $timestamp = Get-Date -Format "HH:mm:ss"
    "$timestamp $msg" | Tee-Object -FilePath $log -Append
}

function RunAndLog($desc, $cmd) {
    Log "[$desc] $cmd"
    $result = Invoke-Expression $cmd 2>&1
    Log "[$desc] exit=$LASTEXITCODE"
    $result | ForEach-Object { Log "  $_" }
    if ($LASTEXITCODE -ne 0) {
        Log "FAIL: $desc"
        Log "Beta gate aborted: $log"
        exit 1
    }
    Log "OK: $desc"
}

Log "=== Vantare Beta Gate ==="
Log "Started at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

$repoRoot = Split-Path $PSScriptRoot -Parent

# 1. verify_voice_contract.py
$py = "python"
RunAndLog "verify_voice_contract" "cd '$repoRoot'; $py scripts/verify_voice_contract.py"

# 2. pytest subset
$pytestTests = @(
    "tests/test_spotter_to_voice_queue.py",
    "tests/test_acceptance_v2_v5.py",
    "tests/test_beta_slim.py",
    "tests/test_main_lifecycle_contract.py",
    "tests/test_property_assign_guard.py",
    "tests/test_voice_bridge_sync_context.py",
    "tests/test_build_hidden_imports.py",
    "tests/test_config_sync_ws.py",
    "tests/test_lifespan_integration.py",
    "tests/test_voice_bridge.py",
    "tests/test_voice_playback_notify.py",
    "tests/test_config_update_ack_ws.py",
    "tests/test_health_voice.py",
    "tests/test_race_tick_loop.py",
    "tests/test_race_loop_no_ws.py"
)
$pytestArgs = $pytestTests -join " "
RunAndLog "pytest subset" "cd '$repoRoot\backend'; $py -m pytest $pytestArgs -q --tb=line"

# 3. Frontend voice tests
$npm = "npm.cmd"
RunAndLog "frontend voice tests" "cd '$repoRoot\frontend'; $npm test -- --run voiceContractMatrix.test.ts ttsPlaybackGate.backend.test.ts useWebSocket.backendPlayback.test.ts backendVoiceOverlay.test.ts configTab.testAudio.test.ts configMigration.voice.test.ts"

# 4. Full backend suite (beta gate requires green)
RunAndLog "pytest full backend" "cd '$repoRoot\backend'; $py -m pytest -q --tb=line"

# 5. Frontend full suite
RunAndLog "frontend full" "cd '$repoRoot\frontend'; $npm test -- --run"

# 6. Optional doctor
if ($WithDoctor) {
    RunAndLog "doctor.ps1" "cd '$repoRoot'; powershell -ExecutionPolicy Bypass -File scripts\doctor.ps1"
}
else {
    Log "SKIP: doctor.ps1 (use -WithDoctor if backend is running on :8008)"
}

Log "=== Beta gate PASSED ==="
Log "Log: $log"
exit 0
