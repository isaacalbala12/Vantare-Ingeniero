# scripts/verify_bundle_startup.ps1
# Spawn bundled backend.exe, wait for /health, verify voice+raca_loop. Exit 0 = OK.
param(
    [int]$Port = 8009,
    [int]$TimeoutSec = 45
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent

$candidates = @(
    (Join-Path $repoRoot "backend\dist\backend\backend.exe"),
    (Join-Path $repoRoot "frontend\release\win-unpacked\resources\backend\backend.exe")
)

$backendExe = $null
$backendCwd = $null
foreach ($c in $candidates) {
    if (Test-Path $c) {
        $backendExe = $c
        $backendCwd = Split-Path $c -Parent
        break
    }
}

if (-not $backendExe) {
    Write-Error "backend.exe not found - run: python backend/build_backend.py"
}

$mainPy = Join-Path $backendCwd "_internal\src\main.py"
if (-not (Test-Path $mainPy)) {
    Write-Error "bundled main.py missing at $mainPy"
}

$mainText = Get-Content $mainPy -Raw
if ($mainText -notmatch "set_enable_commentary_batch\(False\)") {
    Write-Error "bundled main.py missing set_enable_commentary_batch(False)"
}
if ($mainText -match '\.enable_commentary_batch\s*=\s*False') {
    Write-Error "bundled main.py has forbidden property assign"
}
if ($mainText -match "spotter_eval_loop") {
    Write-Error "bundled main.py still references spotter_eval_loop"
}

Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $backendExe
$psi.WorkingDirectory = $backendCwd
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.Environment["HOST"] = "127.0.0.1"
$psi.Environment["PORT"] = "$Port"
$psi.Environment["VANTARE_NATIVE_TELEMETRY"] = "1"
$proc = [System.Diagnostics.Process]::Start($psi)

try {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $health = $null
    while ((Get-Date) -lt $deadline) {
        if ($proc.HasExited) {
            Write-Error "backend.exe exited early with code $($proc.ExitCode)"
        }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3
            if ($health.status -eq "ok") { break }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $health) {
        Write-Error "/health timeout after ${TimeoutSec}s"
    }

    Write-Host "[OK] status=$($health.status) player=$($health.voice.player) cache=$($health.voice.cache_size) ticks=$($health.race_loop.tick_count)"
    if ($health.voice.player -ne "PygameAudioPlayer") {
        Write-Error "expected PygameAudioPlayer, got $($health.voice.player)"
    }
    if ($health.voice.backend_playback -ne $true) {
        Write-Error "voice.backend_playback is not true"
    }
    if ($health.race_loop.tick_count -lt 1) {
        Write-Error "race_loop.tick_count is 0 after startup"
    }
    Write-Host "=== bundle startup OK ==="
    exit 0
}
finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}
