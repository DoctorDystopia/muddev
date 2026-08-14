[CmdletBinding()]
param(
    # Optional toggle to trigger the full reset. 
    # Usage: .\reload_characters.ps1 -Reset
    [switch]$Reset
)

$ScriptDir = Split-Path -Parent $PSCommandPath
$GameDir = Split-Path -Parent $ScriptDir
$EvenvDir = Resolve-Path (Join-Path $GameDir "..\.venv")
$Python = Join-Path $EvenvDir "Scripts\python.exe"

Set-Location -LiteralPath $GameDir

Write-Host "=== Reloading Characters ==="

if ($Reset) {
    Write-Host "WARNING: Complete reset flag activated!"
    # Passes the --reset argument to the python script
    & $Python $ScriptDir\reload_characters.py --reset
} else {
    & $Python $ScriptDir\reload_characters.py
}

if (-not $?) { Write-Error "Character reload script failed"; exit 1 }

Write-Host "=== Done ==="