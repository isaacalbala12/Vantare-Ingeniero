# Verifica artefactos desktop tras build:desktop (CI o local)
param(
  [string]$ReleaseDir = (Join-Path $PSScriptRoot "..\frontend\release")
)

$ErrorActionPreference = "Stop"

Write-Host "=== Verificando artefactos en $ReleaseDir ==="

$exe = Get-ChildItem -Path $ReleaseDir -Filter "vantare-ingeniero-*-setup.exe" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $exe) {
  Write-Error "No se encontro vantare-ingeniero-*-setup.exe en $ReleaseDir"
}

$latestYml = Join-Path $ReleaseDir "latest.yml"
if (-not (Test-Path $latestYml)) {
  Write-Error "Falta latest.yml (requerido por electron-updater)"
}

$distIndex = Join-Path $PSScriptRoot "..\frontend\dist\index.html"
if (Test-Path $distIndex) {
  $html = Get-Content $distIndex -Raw
  if ($html -like '*src="/assets/*') {
    Write-Error "dist/index.html usa rutas absolutas /assets (Hub negro en produccion). Usa base: './' en vite.config.ts"
  }
  if ($html -notlike '*./assets/*') {
    Write-Error "dist/index.html no contiene rutas relativas ./assets/"
  }
  Write-Host "[OK] dist/index.html usa rutas relativas"
}

$sizeMb = [math]::Round($exe.Length / 1MB, 1)
Write-Host "[OK] $($exe.Name) ($sizeMb MB)"
Write-Host "[OK] latest.yml"
Write-Host "=== Verificacion completada ==="
