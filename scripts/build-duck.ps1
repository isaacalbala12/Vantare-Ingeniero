param(
  [string]$Root = (Split-Path -Parent $PSScriptRoot)
)
Push-Location "$Root\native\duck_lmu"
cargo build --release
Pop-Location
Write-Host "Built: $Root\native\duck_lmu\target\release\duck_lmu.exe"
