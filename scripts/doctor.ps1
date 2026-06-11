# scripts/doctor.ps1
# Post-install health check for Vantare Ingeniero IA backend.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\doctor.ps1

$ErrorActionPreference = "Stop"
$log = Join-Path $env:TEMP "vantare-doctor-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

function Log($msg) {
    $timestamp = Get-Date -Format "HH:mm:ss"
    "$timestamp $msg" | Tee-Object -FilePath $log -Append
}

$repoRoot = Split-Path $PSScriptRoot -Parent
$backendRoot = Join-Path $repoRoot "frontend\src-tauri\binaries\backend"
if (-not (Test-Path $backendRoot)) {
    $backendRoot = Join-Path $repoRoot "backend\dist\backend"
}

Log "=== Vantare Doctor ==="
Log "Backend root: $backendRoot"

# 1. _internal check
$internalPath = Join-Path $backendRoot "_internal"
if (-not (Test-Path $internalPath)) {
    Log "FAIL: _internal missing at $internalPath"
    Log "Doctor aborted: $log"
    exit 1
}
Log "OK: _internal ($internalPath)"

# 1b. Bundled main.py contract (catch property-assign / dead loop before runtime)
$mainPy = Join-Path $internalPath "src\main.py"
if (Test-Path $mainPy) {
    $mainText = Get-Content $mainPy -Raw
    if ($mainText -notmatch "set_enable_commentary_batch\(False\)") {
        Log "FAIL: bundled main.py missing set_enable_commentary_batch(False)"
        Log "Doctor aborted: $log"
        exit 1
    }
    if ($mainText -match '\.enable_commentary_batch\s*=\s*False') {
        Log "FAIL: bundled main.py has forbidden property assign"
        Log "Doctor aborted: $log"
        exit 1
    }
    if ($mainText -match "spotter_eval_loop") {
        Log "FAIL: bundled main.py still references spotter_eval_loop"
        Log "Doctor aborted: $log"
        exit 1
    }
    Log "OK: bundled main.py contract"
}
else {
    Log "WARN: bundled main.py not found at $mainPy"
}

# 2. Python + pygame check
$pyPath = Join-Path $internalPath "python.exe"
$py = Get-ChildItem $pyPath -ErrorAction SilentlyContinue
if ($py) {
    try {
        $result = & $py.FullName -c "import pygame; pygame.mixer.init(); print('OK')" 2>&1
        Log "OK: bundled python + pygame -- $result"
    }
    catch {
        Log "WARN: bundled python, but pygame init failed: $_"
    }
}
else {
    Log "WARN: bundled python.exe not found -- dev mode"
    try {
        $result = python -c "import pygame; pygame.mixer.init(); print('OK')" 2>&1
        Log "OK: system python + pygame -- $result"
    }
    catch {
        Log "WARN: system python pygame init failed -- audio may not work: $_"
    }
}

# 3. Health endpoint
$port = 8008
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 5
    Log "OK: /health status=$($h.status)"

    $tickCount = $h.race_loop.tick_count
    Log "race_loop tick_count=$tickCount"
    if ($tickCount -eq 0) {
        Log "WARN: tick_count is 0 -- backend may have just started"
    }

    $player = $h.voice.player
    $cacheSize = $h.voice.cache_size
    $backendPlayback = $h.voice.backend_playback
    Log "voice player=$player cache=$cacheSize playback=$backendPlayback"

    if ($player -ne "PygameAudioPlayer") {
        Log "WARN: expected PygameAudioPlayer, got $player"
    }
    if ($cacheSize -lt 10) {
        Log "WARN: cache_size=$cacheSize below 10 -- spotter phrases not fully cached"
    }
    if ($backendPlayback -ne $true) {
        Log "WARN: backend_playback is not true"
    }
}
catch {
    $errMsg = $_.Exception.Message
    Log "FAIL: /health -- $errMsg (is the backend running on port $port?)"
    Log "Doctor aborted: $log"
    exit 1
}

Log "Doctor complete: $log"
exit 0
