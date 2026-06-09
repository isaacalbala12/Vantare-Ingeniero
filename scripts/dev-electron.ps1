param([switch]$NoBackend)
$Root = Split-Path -Parent $PSScriptRoot
Write-Host "Vantare dev — Electron hub + overlay"
if (-not $NoBackend) {
  Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; `$env:VANTARE_NATIVE_TELEMETRY='1'; python run_dev.py --no-reload"
  Start-Sleep -Seconds 2
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; npm run dev:electron"
Write-Host "Hub: Electron (1920x1080) | Overlay: A1 | Health: http://127.0.0.1:8008/health"
