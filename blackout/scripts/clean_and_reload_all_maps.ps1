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
#
# Without a scope flag this rebuilds every map in the manifest, which is what
# it always did. -Map and -Tile narrow it:
#
#   .\scripts\clean_and_reload_all_maps.ps1 -Map oasis
#   .\scripts\clean_and_reload_all_maps.ps1 -Tile "oasis:12,4","oasis:12,5"
#
# Both take a list. world/maps/scope.py owns their format and the rule that a
# map named by both flags is rebuilt whole.

param(
    [switch]$DryRun,
    [string[]]$Map = @(),
    [string[]]$Tile = @()
)

$ScriptDir = Split-Path -Parent $PSCommandPath
$GameDir = Split-Path -Parent $ScriptDir
$EvenvDir = Resolve-Path (Join-Path $GameDir "..\evenv")
$Python = Join-Path $EvenvDir "Scripts\python.exe"
$Evennia = Join-Path $EvenvDir "Scripts\evennia.exe"
$MapSync = Join-Path $ScriptDir "map_sync.py"

Set-Location -LiteralPath $GameDir

# Flatten both lists into the flags map_sync.py reads. Each value gets its own
# flag, because both flags repeat there rather than taking a list.
$SyncArgs = @()
foreach ($Zcoord in $Map) {
    $SyncArgs += "--map"
    $SyncArgs += $Zcoord
}
foreach ($Coordinate in $Tile) {
    $SyncArgs += "--tile"
    $SyncArgs += $Coordinate
}

# A dry run only reads, so it neither stops the server nor spawns afterwards.
if ($DryRun) {
    & $Python $MapSync --dry-run @SyncArgs
    exit $LASTEXITCODE
}

Write-Host "=== Stopping Evennia ==="
& $Evennia stop

Write-Host "=== Syncing grid to map manifest ==="
& $Python $MapSync @SyncArgs
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
