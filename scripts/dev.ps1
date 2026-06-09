param([switch]$NoTauri)
$Root = Split-Path -Parent $PSScriptRoot
Write-Host "Vantare dev — native telemetry (no sidecar)"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; `$env:VANTARE_NATIVE_TELEMETRY='1'; python run_dev.py --no-reload"
Start-Sleep -Seconds 2
if (-not $NoTauri) {
  Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; npm run tauri dev"
}
Write-Host "LMU must be running (borderless/windowed). Health: http://127.0.0.1:8008/health"
