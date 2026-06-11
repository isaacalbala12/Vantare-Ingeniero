# Release verification gate - tests, artifacts, bundled backend smoke.
# Usage:
#   powershell -File scripts/verify-release.ps1              # tests + smoke (existing build)
#   powershell -File scripts/verify-release.ps1 -Build       # full build + verify
#   powershell -File scripts/verify-release.ps1 -SkipTests   # artifacts + smoke only
param(
    [switch]$Build,
    [switch]$SkipTests,
    [switch]$SkipSmoke,
    [int]$SmokePort = 8009
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Join-MultiPath([string]$Root, [string[]]$Parts) {
    $p = $Root
    foreach ($part in $Parts) { $p = Join-Path $p $part }
    return $p
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Frontend = Join-Path $RepoRoot "frontend"
$Backend = Join-Path $RepoRoot "backend"
$ReleaseDir = Join-Path $Frontend "release"
$EvidenceDir = Join-MultiPath $RepoRoot @(".omo", "evidence")
$ResultPath = Join-Path $EvidenceDir "verify-release-latest.json"

$startedAt = Get-Date
$steps = [ordered]@{}

function Write-Step($name, $status, $detail) {
    $steps[$name] = @{ status = $status; detail = $detail }
    $icon = if ($status -eq "PASS") { "[OK]" } elseif ($status -eq "WARN") { "[!!]" } else { "[FAIL]" }
    Write-Host "$icon $name - $detail"
}

function Fail($name, $detail) {
    Write-Step $name "FAIL" $detail
    Save-Result "FAIL"
    exit 1
}

function Save-Result($overall) {
    $payload = @{
        overall = $overall
        started_at = $startedAt.ToString("o")
        finished_at = (Get-Date).ToString("o")
        version = (Get-Content (Join-Path $Frontend "package.json") -Raw | ConvertFrom-Json).version
        steps = $steps
    }
    New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
    $payload | ConvertTo-Json -Depth 6 | Set-Content -Path $ResultPath -Encoding UTF8
    Write-Host ""
    Write-Host "Report: $ResultPath"
}

Write-Host "=== Vantare verify-release ==="
Write-Host "Repo: $RepoRoot"
Write-Host ""

# --- 1. Beta gate (voice + full pytest + frontend) ---
if (-not $SkipTests) {
    & (Join-Path $PSScriptRoot "verify_beta_gate.ps1")
    if ($LASTEXITCODE -ne 0) { Fail "beta_gate" "verify_beta_gate.ps1 failed" }
    Write-Step "beta_gate" "PASS" "verify_beta_gate.ps1"
} else {
    Write-Step "beta_gate" "WARN" "skipped"
}

# --- 1c. Legacy critical subset (ws integration smoke) ---
if (-not $SkipTests) {
    Push-Location $Backend
    try {
        & python -m pytest tests/test_ws_integration.py -q --tb=line
        if ($LASTEXITCODE -ne 0) { Fail "ws_integration" "pytest failed" }
        Write-Step "ws_integration" "PASS" "msgpack WS integration"
    } finally {
        Pop-Location
    }
} else {
    Write-Step "ws_integration" "WARN" "skipped"
}

# --- REMOVED: duplicate partial pytest/voice_contract (now in verify_beta_gate) ---

# --- 2. Build (optional) ---
if ($Build) {
    Push-Location $RepoRoot
    try {
        & (Join-Path $PSScriptRoot "build-desktop.ps1")
        if ($LASTEXITCODE -ne 0) { Fail "build_desktop" "build-desktop.ps1 failed" }
        Write-Step "build_desktop" "PASS" "backend + electron NSIS"
    } finally {
        Pop-Location
    }

    & (Join-Path $PSScriptRoot "verify_bundle_startup.ps1")
    if ($LASTEXITCODE -ne 0) { Fail "bundle_startup" "verify_bundle_startup.ps1 failed" }
    Write-Step "bundle_startup" "PASS" "backend.exe lifespan + /health"
} else {
    Write-Step "build_desktop" "WARN" "skipped (use -Build to rebuild)"
}

# --- 3. Artifact checks ---
$setupExe = Get-ChildItem -Path $ReleaseDir -Filter "vantare-ingeniero-*-setup.exe" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1

$expectedVersion = (Get-Content (Join-Path $Frontend "package.json") -Raw | ConvertFrom-Json).version
$unpackedBackend = Join-MultiPath $ReleaseDir @("win-unpacked", "resources", "backend", "backend.exe")
$distBackend = Join-MultiPath $Backend @("dist", "backend", "backend.exe")

if ($setupExe) {
    if ($setupExe.Name -notlike "*-$expectedVersion-setup.exe") {
        Write-Step "desktop_artifacts" "WARN" "newest installer is $($setupExe.Name) but package.json is $expectedVersion (run -Build)"
    }
    try {
        & (Join-Path $PSScriptRoot "verify-desktop-artifacts.ps1") -ReleaseDir $ReleaseDir
        Write-Step "desktop_artifacts" "PASS" $setupExe.Name
    } catch {
        Fail "desktop_artifacts" $_.Exception.Message
    }
} else {
    Write-Step "desktop_artifacts" "WARN" "no setup.exe in release/ (run with -Build)"
}

$bundleMain = Join-MultiPath $Backend @("dist", "backend", "_internal", "src", "main.py")
if (-not (Test-Path $bundleMain)) {
    $bundleMain = Join-MultiPath $Frontend @("src-tauri", "binaries", "backend", "_internal", "src", "main.py")
}

if (Test-Path $bundleMain) {
    $mainText = Get-Content $bundleMain -Raw
    if ($mainText -notmatch "set_enable_commentary_batch\(False\)") {
        Fail "bundle_main_contract" "bundled main.py missing set_enable_commentary_batch(False)"
    }
    if ($mainText -match '\.enable_commentary_batch\s*=\s*False') {
        Fail "bundle_main_contract" "bundled main.py has forbidden property assign"
    }
    if ($mainText -match "spotter_eval_loop") {
        Fail "bundle_main_contract" "bundled main.py still references spotter_eval_loop"
    }
    if ($mainText -match "offline=not use_native") {
        Write-Step "bundle_native_telemetry" "PASS" $bundleMain
    } else {
        Fail "bundle_native_telemetry" "main.py missing native telemetry wiring"
    }
    Write-Step "bundle_main_contract" "PASS" "lifespan contracts OK"
} else {
    Fail "bundle_native_telemetry" "bundled main.py not found (run build_backend.py)"
}

# --- 3b. Bundle freshness (D2: source vs bundle parity) ---
$bundleSrcRoot = Split-Path $bundleMain -Parent
$freshCheckFiles = @(
    @{ src = (Join-Path $Backend "src\main.py"); bundle = $bundleMain },
    @{ src = (Join-Path $Backend "src\voice\bridge.py"); bundle = (Join-Path $bundleSrcRoot "voice\bridge.py") },
    @{ src = (Join-Path $Backend "src\race\tick_loop.py"); bundle = (Join-Path $bundleSrcRoot "race\tick_loop.py") }
)
$allFresh = $true
foreach ($entry in $freshCheckFiles) {
    $srcFile = $entry.src
    $bundleFile = $entry.bundle
    $leaf = Split-Path $srcFile -Leaf
    if ((Test-Path $srcFile) -and (Test-Path $bundleFile)) {
        $srcMtime = (Get-Item $srcFile).LastWriteTime
        $bundleMtime = (Get-Item $bundleFile).LastWriteTime
        if ($srcMtime -gt $bundleMtime) {
            Write-Step "bundle_freshness" "WARN" "$leaf source newer than bundle - run -Build"
            $allFresh = $false
        }
    }
    elseif (Test-Path $srcFile) {
        Write-Step "bundle_freshness" "WARN" "$leaf missing in bundle at $bundleFile"
        $allFresh = $false
    }
}
if ($allFresh) {
    Write-Step "bundle_freshness" "PASS" "source vs bundle mtime OK (main, bridge, tick_loop)"
}

# Resolve backend.exe for smoke
$backendExe = $null
$backendCwd = $null
foreach ($candidate in @(
        @{ exe = $unpackedBackend; cwd = (Split-Path $unpackedBackend -Parent) },
        @{ exe = $distBackend; cwd = (Split-Path $distBackend -Parent) }
    )) {
    if (Test-Path $candidate.exe) {
        $backendExe = $candidate.exe
        $backendCwd = $candidate.cwd
        break
    }
}

if (-not $backendExe) {
    Fail "backend_smoke" "backend.exe not found (run -Build or python backend/build_backend.py)"
}

# --- 4. Backend smoke (spawn + health + WS) ---
if (-not $SkipSmoke) {
    if (Test-Path $backendExe) {
        & (Join-Path $PSScriptRoot "verify_bundle_startup.ps1") -Port $SmokePort
        if ($LASTEXITCODE -ne 0) { Fail "bundle_startup" "verify_bundle_startup.ps1 failed" }
        Write-Step "bundle_startup" "PASS" "lifespan + /health contract"
    }

    $smokeProc = $null
    try {
        # Free smoke port if a stale process holds it
        Get-NetTCPConnection -LocalPort $SmokePort -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $backendExe
        $psi.WorkingDirectory = $backendCwd
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.Environment["HOST"] = "127.0.0.1"
        $psi.Environment["PORT"] = "$SmokePort"
        $psi.Environment["VANTARE_NATIVE_TELEMETRY"] = "1"
        $smokeProc = [System.Diagnostics.Process]::Start($psi)

        $smokeOut = Join-Path $EvidenceDir "release-smoke-latest.json"
        Push-Location $Backend
        try {
            python scripts/release_smoke.py --port $SmokePort --bundle-main $bundleMain --output $smokeOut
            if ($LASTEXITCODE -ne 0) { Fail "backend_smoke" "release_smoke.py failed - see $smokeOut" }
        } finally {
            Pop-Location
        }

        $smokeJson = Get-Content $smokeOut -Raw | ConvertFrom-Json
        $detail = "telemetry=$($smokeJson.health.telemetry_source) binary=$($smokeJson.websocket.binary_frames) json=$($smokeJson.websocket.json_event_count)"
        if ($smokeJson.health.telemetry_source -eq "native" -and $smokeJson.health.shared_memory_status -eq "connected") {
            Write-Step "backend_smoke" "PASS" "$detail (LMU detected)"
        } else {
            Write-Step "backend_smoke" "PASS" "$detail (LMU not required for smoke pass)"
        }
    } finally {
        if ($smokeProc -and -not $smokeProc.HasExited) {
            Stop-Process -Id $smokeProc.Id -Force -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Step "backend_smoke" "WARN" "skipped"
}

# --- 5. Trace replay (optional, no LMU) ---
$tracePath = Join-MultiPath $Backend @("tests", "fixtures", "replay", "minimal_race.trace")
if (Test-Path $tracePath) {
    Push-Location $Backend
    try {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            python scripts/replay_trace.py $tracePath --hz 20 2>&1 | Out-Null
            $traceRc = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prevEap
        }
        if ($traceRc -ne 0) {
            Write-Step "trace_replay" "WARN" "replay_trace.py failed (exit $traceRc)"
        } else {
            Write-Step "trace_replay" "PASS" "minimal_race.trace"
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Step "trace_replay" "WARN" "fixture missing"
}

Save-Result "PASS"
Write-Host ""
Write-Host "=== ALL GATES PASSED ==="
