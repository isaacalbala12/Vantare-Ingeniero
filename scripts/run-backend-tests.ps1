#!/usr/bin/env pwsh
# Suite backend equivalente a CI (sin benchmarks externos).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Push-Location (Join-Path $PSScriptRoot ".." "backend")
try {
    python -m pytest tests/ -v --cov=src/ --cov-report=term --cov-fail-under=70
} finally {
    Pop-Location
}
