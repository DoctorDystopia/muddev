#!/usr/bin/env bash
#
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
# BASH, NOT POWERSHELL, and that is the whole reason this file replaced
# `publish.ps1` on 08/27/2026: the shell in front of this repo is git bash, this
# machine has no `pwsh`, and the README's answer was a
# `powershell -ExecutionPolicy Bypass -File` incantation for a script nobody was
# going to run from a PowerShell prompt anyway. One script for the shell that
# exists beats two that can drift.
#
# Pass --dry-run to list every key that would be written without uploading.

set -u

BUCKET="playblackout-assets"
DRY_RUN=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --bucket)  shift; BUCKET="${1:-}" ;;
        *) echo "Unknown argument: $1" >&2
           echo "Usage: publish.sh [--dry-run] [--bucket NAME]" >&2
           exit 2 ;;
    esac
    shift
done

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
EXPORT_DIR="$SCRIPT_DIR/build"
MODEL_DIR="$REPO_ROOT/blackout/web/static/webclient/models"

# Wrangler is a devDependency of the SITE repo, not this one, so it runs from
# there. Nothing else in this script needs that directory.
SITE_DIR="$( cd "$REPO_ROOT/../playblackout-site" 2>/dev/null && pwd )" || SITE_DIR=""

if [ ! -f "$EXPORT_DIR/index.wasm" ]; then
    echo "No export at $EXPORT_DIR. Build it first -- see README.md beside this script." >&2
    exit 1
fi

if [ ! -d "$MODEL_DIR" ]; then
    echo "No model tree at $MODEL_DIR." >&2
    exit 1
fi

if [ -z "$SITE_DIR" ]; then
    echo "No site repo beside $REPO_ROOT; wrangler lives in playblackout-site." >&2
    exit 1
fi

# `wrangler` is a native Windows binary under git bash, and a POSIX path is not
# something it can open. cygpath is the translation; on a real POSIX box there
# is nothing to translate and the path passes through unchanged.
to_native_path() {
    if command -v cygpath > /dev/null 2>&1; then
        cygpath -w "$1"
    else
        printf '%s' "$1"
    fi
}

# Each pair is (local tree, R2 key prefix). The prefixes are the same two the
# worker claims in R2_ROUTE_PREFIXES and wrangler.jsonc's run_worker_first.
TREES=(
    "$EXPORT_DIR:client"
    "$MODEL_DIR:static/webclient/models"
)

KEYS=()
FILES=()
SIZES=()
TOTAL_BYTES=0

for TREE in "${TREES[@]}"; do
    ROOT="${TREE%%:*}"
    PREFIX="${TREE#*:}"

    # Sorted, so two runs list the same keys in the same order and a diff of two
    # publish logs is about what changed rather than about directory order.
    while IFS= read -r FILE; do
        RELATIVE="${FILE#"$ROOT"/}"
        SIZE="$( stat -c %s "$FILE" )"

        KEYS+=( "$PREFIX/$RELATIVE" )
        FILES+=( "$FILE" )
        SIZES+=( "$SIZE" )
        TOTAL_BYTES=$(( TOTAL_BYTES + SIZE ))
    done < <( find "$ROOT" -type f | sort )
done

COUNT="${#KEYS[@]}"
TOTAL_MIB="$( awk -v b="$TOTAL_BYTES" 'BEGIN { printf "%.1f", b / 1048576 }' )"

echo "=== $COUNT objects, $TOTAL_MIB MiB -> r2://$BUCKET ==="

for INDEX in "${!KEYS[@]}"; do
    SIZE_MIB="$( awk -v b="${SIZES[$INDEX]}" 'BEGIN { printf "%.2f", b / 1048576 }' )"
    printf '  %-48s %8s MiB\n' "${KEYS[$INDEX]}" "$SIZE_MIB"
done

if [ "$DRY_RUN" -eq 1 ]; then
    echo "=== Dry run: nothing uploaded ==="
    exit 0
fi

cd "$SITE_DIR" || exit 1

for INDEX in "${!KEYS[@]}"; do
    echo "--- put ${KEYS[$INDEX]}"
    if ! npx wrangler r2 object put "$BUCKET/${KEYS[$INDEX]}" \
            --file "$( to_native_path "${FILES[$INDEX]}" )" --remote; then
        echo "Upload failed at ${KEYS[$INDEX]}; bucket is now PARTIALLY updated" >&2
        exit 1
    fi
done

echo "=== Done. Deploy the site so the worker routes are live. ==="
