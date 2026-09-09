# Backs up the live Evennia database to server/backups/, pruning older
# backups beyond the retention count. Thin wrapper around backup_db.py so
# Windows Task Scheduler has a single, argument-free-by-default target.
#
# Usage:
#   .\scripts\backup_db.ps1                  # defaults: keep 14, server/backups
#   .\scripts\backup_db.ps1 -Keep 30
#   .\scripts\backup_db.ps1 -Dest D:\backups\blackout

param(
    [int]$Keep = 14,
    [string]$Dest = ""
)

$ScriptDir = Split-Path -Parent $PSCommandPath
$GameDir = Split-Path -Parent $ScriptDir
$EvenvDir = Resolve-Path (Join-Path $GameDir "..\evenv")
$Python = Join-Path $EvenvDir "Scripts\python.exe"
$BackupScript = Join-Path $ScriptDir "backup_db.py"

Set-Location -LiteralPath $GameDir

$PythonArgs = @($BackupScript, "--keep", $Keep)
if ($Dest -ne "") {
    $PythonArgs += @("--dest", $Dest)
}

& $Python @PythonArgs
exit $LASTEXITCODE
