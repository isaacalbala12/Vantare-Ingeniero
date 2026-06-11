# scripts/build-duck-lmu.ps1
# Build duck_lmu native binary for LMU audio ducking.
# Requires Rust toolchain (rustup + cargo).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\build-duck-lmu.ps1
#
# Output: native/duck_lmu/target/release/duck_lmu.exe
# The electron-builder WARN "file source doesn't exist" is acceptable
# if this binary is not yet compiled (Hito 8 known debt).

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent
$projectDir = Join-Path (Join-Path $repoRoot "native") "duck_lmu"

Write-Host "=== Building duck_lmu (Rust) ==="
Write-Host "Project: $projectDir"

Push-Location $projectDir
try {
    # Check if cargo is available
    $cargo = Get-Command "cargo" -ErrorAction SilentlyContinue
    if (-not $cargo) {
        Write-Error "cargo not found — install Rust toolchain from https://rustup.rs"
    }

    Write-Host "[i] Running cargo build --release ..."
    cargo build --release
    if ($LASTEXITCODE -ne 0) {
        Write-Error "cargo build failed with exit code $LASTEXITCODE"
    }

    $binary = Join-Path $projectDir "target" "release" "duck_lmu.exe"
    if (Test-Path $binary) {
        Write-Host "[OK] duck_lmu.exe built: $binary"
        Write-Host "[OK] Size: $((Get-Item $binary).Length / 1KB) KB"
    } else {
        Write-Error "Binary not found at expected path: $binary"
    }
} finally {
    Pop-Location
}

Write-Host "=== duck_lmu build complete ==="
