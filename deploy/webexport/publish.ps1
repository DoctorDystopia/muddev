# Publish the Godot web client and its model tree to the R2 bucket the site
# serves them from.
#
# The client does NOT ship with the marketing site. `index.wasm` is 37.7 MiB and
# Cloudflare caps an individual static asset at 25 MiB on every plan it sells,
# so `wrangler deploy` rejects the upload outright -- see README.md beside this
# file. Both trees live in R2 instead and are served, same-origin, by
# `playblackout-site/worker/index.ts`.
#
# KEYS MIRROR URLS. The worker maps a request path onto an R2 key by dropping
# the leading slash and nothing else, so `client/index.wasm` here is
# `/client/index.wasm` there. That is the whole routing rule; keep it true.
#
# CONTENT TYPES ARE NOT SET HERE ON PURPOSE. The worker owns them, from its own
# CONTENT_TYPES table, precisely so an upload cannot get one wrong -- a `.wasm`
# served as octet-stream fails `WebAssembly.instantiateStreaming` silently.
# Passing --content-type here would make this the second owner of that fact.
#
# Pass -DryRun to list every key that would be written without uploading.

param(
    [string]$Bucket = "playblackout-assets",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSCommandPath
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$ExportDir = Join-Path $ScriptDir "build"
$ModelDir = Join-Path $RepoRoot "blackout\web\static\webclient\models"

# Wrangler is a devDependency of the SITE repo, not this one, so it runs from
# there. Nothing else in this script needs that directory.
$SiteDir = Resolve-Path (Join-Path $RepoRoot "..\playblackout-site")

# Each pair is (local tree, R2 key prefix). The prefixes are the same two the
# worker claims in R2_ROUTE_PREFIXES and wrangler.jsonc's run_worker_first.
$Trees = @(
    @{ Path = $ExportDir; Prefix = "client" },
    @{ Path = $ModelDir;  Prefix = "static/webclient/models" }
)

if (-not (Test-Path (Join-Path $ExportDir "index.wasm"))) {
    Write-Error "No export at $ExportDir. Build it first -- see README.md beside this script."
    exit 1
}

if (-not (Test-Path $ModelDir)) {
    Write-Error "No model tree at $ModelDir."
    exit 1
}

$Uploads = @()

foreach ($Tree in $Trees) {
    $Root = Resolve-Path $Tree.Path
    foreach ($File in Get-ChildItem -LiteralPath $Root -Recurse -File) {
        $Relative = $File.FullName.Substring($Root.Path.Length).TrimStart("\", "/")
        $Key = ($Tree.Prefix + "/" + $Relative) -replace "\\", "/"

        # PSCustomObject, not a hashtable: Measure-Object below reads `Size` as a
        # property, and a hashtable key is not one under Windows PowerShell 5.1.
        $Uploads += [PSCustomObject]@{
            Key  = $Key
            File = $File.FullName
            Size = $File.Length
        }
    }
}

$TotalBytes = ($Uploads | Measure-Object -Property Size -Sum).Sum
$TotalMiB = [math]::Round($TotalBytes / 1MB, 1)

Write-Host "=== $($Uploads.Count) objects, $TotalMiB MiB -> r2://$Bucket ==="

foreach ($Upload in $Uploads) {
    $SizeMiB = [math]::Round($Upload.Size / 1MB, 2)
    Write-Host ("  {0,-48} {1,8} MiB" -f $Upload.Key, $SizeMiB)
}

if ($DryRun) {
    Write-Host "=== Dry run: nothing uploaded ==="
    exit 0
}

Set-Location -LiteralPath $SiteDir

foreach ($Upload in $Uploads) {
    Write-Host "--- put $($Upload.Key)"
    & npx wrangler r2 object put "$Bucket/$($Upload.Key)" --file $Upload.File --remote
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Upload failed at $($Upload.Key); bucket is now PARTIALLY updated"
        exit 1
    }
}

Write-Host "=== Done. Deploy the site so the worker routes are live. ==="
