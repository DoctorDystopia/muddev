# Full map rebuild, driven entirely by scripts/map_manifest.json:
# stop -> sync grid to manifest (prune, purge, register, spawn) -> reload.
#
# The spawn is inside map_sync.py, not a separate `evennia xyzgrid spawn` step.
# That command asks for confirmation on stdin and has no way to decline the
# question, so a rebuild could not run unattended -- and its exit code was
# never checked here, so a failed spawn still reached "Done".
#
# Pass -DryRun to report what a rebuild would add and remove without touching
# the database or the running server.

param(
    [switch]$DryRun
)

$ScriptDir = Split-Path -Parent $PSCommandPath
$GameDir = Split-Path -Parent $ScriptDir
$EvenvDir = Resolve-Path (Join-Path $GameDir "..\evenv")
$Python = Join-Path $EvenvDir "Scripts\python.exe"
$Evennia = Join-Path $EvenvDir "Scripts\evennia.exe"
$MapSync = Join-Path $ScriptDir "map_sync.py"

Set-Location -LiteralPath $GameDir

# A dry run only reads, so it neither stops the server nor spawns afterwards.
if ($DryRun) {
    & $Python $MapSync --dry-run
    exit $LASTEXITCODE
}

Write-Host "=== Stopping Evennia ==="
& $Evennia stop

Write-Host "=== Syncing grid to map manifest ==="
& $Python $MapSync
if ($LASTEXITCODE -ne 0) {
    Write-Error "Map sync failed; server left stopped"
    exit 1
}

Write-Host "=== Reloading Evennia ==="
& $Evennia reload
if ($LASTEXITCODE -ne 0) {
    Write-Error "Reload failed; the grid is rebuilt but the server is down"
    exit 1
}

Write-Host "=== Done ==="
