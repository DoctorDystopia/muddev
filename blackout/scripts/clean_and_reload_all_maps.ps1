$ScriptDir = Split-Path -Parent $PSCommandPath
$GameDir = Split-Path -Parent $ScriptDir
$EvenvDir = Resolve-Path (Join-Path $GameDir "..\evenv")
$Python = Join-Path $EvenvDir "Scripts\python.exe"
$Evennia = Join-Path $EvenvDir "Scripts\evennia.exe"

Set-Location -LiteralPath $GameDir

Write-Host "=== Stopping Evennia ==="
& $Evennia stop

Write-Host "=== Cleaning up old map data ==="
& $Python $ScriptDir\xyz_cleanup.py
if (-not $?) { Write-Error "Cleanup failed"; exit 1 }

Write-Host "=== Adding maps ==="
& $Evennia xyzgrid add world.maps.test_neo_cairo
& $Evennia xyzgrid add world.maps.test_oasis

Write-Host "=== Spawning maps ==="
& $Evennia xyzgrid spawn

Write-Host "=== Reloading Evennia ==="
& $Evennia reload

Write-Host "=== Done ==="
