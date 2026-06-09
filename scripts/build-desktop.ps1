$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== Building backend ==="
Set-Location backend
python build_backend.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== Building desktop (Electron NSIS) ==="
Set-Location ..\frontend
npm run build:desktop
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== Output ==="
Get-ChildItem .\release\*.exe
