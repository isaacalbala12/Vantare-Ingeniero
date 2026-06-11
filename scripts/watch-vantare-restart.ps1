# Reinicia Vantare Ingeniero IA cuando el usuario cierra todas las ventanas.
$app = Join-Path $env:LOCALAPPDATA "Programs\Vantare Ingeniero IA\Vantare Ingeniero IA.exe"
$log = Join-Path $env:APPDATA "Vantare Ingeniero IA\watch-restart.log"

function Write-Log([string]$msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Add-Content -Path $log -Value $line -ErrorAction SilentlyContinue
}

if (-not (Test-Path $app)) {
    Write-Log "ERROR: no se encuentra $app"
    exit 1
}

Write-Log "Watcher iniciado. Esperando cierre de la app..."

while ($true) {
    $procs = Get-Process -Name "Vantare Ingeniero IA" -ErrorAction SilentlyContinue
    if (-not $procs) {
        Write-Log "App cerrada. Reiniciando en 2s..."
        Start-Sleep -Seconds 2
        Start-Process $app
        Write-Log "App relanzada."
        # Esperar a que arranque al menos un proceso antes de volver a vigilar
        $deadline = (Get-Date).AddSeconds(120)
        while ((Get-Date) -lt $deadline) {
            if (Get-Process -Name "Vantare Ingeniero IA" -ErrorAction SilentlyContinue) { break }
            Start-Sleep -Seconds 1
        }
    }
    Start-Sleep -Seconds 2
}
