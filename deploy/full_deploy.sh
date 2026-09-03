#!/usr/bin/env bash
#
# deploy/full_deploy.sh — one command for the pipeline in deploy/README.md.
#
# Order: check/regenerate client constants -> either a map rebuild (which
# reloads Evennia itself) or a plain evennia reload/reboot -> Godot export ->
# publish to R2 -> deploy the site -> verify both origins answer.
#
# Read deploy/README.md before changing this. This script is the terse,
# runnable version of that doc's "full pipeline" section, not a replacement
# for the reasoning in it.
#
# Usage:
#   deploy/full_deploy.sh [--maps] [--reboot] [--skip-godot] [--dry-run]
#
#   --maps          rebuild the grid from scripts/map_manifest.json instead of
#                    a plain reload (the map script reloads Evennia itself)
#   --reboot        evennia reboot instead of reload -- use when a
#                    PORTAL_SERVICES_PLUGIN_MODULES entry changed; this
#                    restarts the Portal too and briefly drops connections
#   --skip-godot    skip export/publish/wrangler deploy -- server-only deploy
#   --dry-run       print every command instead of running it; still performs
#                    the read-only constants --check

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
SITE_DIR="$( cd "$REPO_ROOT/../playblackout-site" 2>/dev/null && pwd )" || SITE_DIR=""

PYTHON="$REPO_ROOT/evenv/Scripts/python.exe"
EVENNIA="$REPO_ROOT/evenv/Scripts/evennia.exe"
GODOT_BIN="${GODOT_BIN:-/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe}"

DO_MAPS=0
DO_GODOT=1
DO_REBOOT=0
DRY_RUN=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --maps)       DO_MAPS=1 ;;
        --skip-godot) DO_GODOT=0 ;;
        --reboot)     DO_REBOOT=1 ;;
        --dry-run)    DRY_RUN=1 ;;
        -h|--help)
            sed -n '2,23p' "$0" | sed 's/^#//'
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2
           echo "Usage: full_deploy.sh [--maps] [--reboot] [--skip-godot] [--dry-run]" >&2
           exit 2 ;;
    esac
    shift
done

run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] $*"
    else
        echo "+ $*"
        "$@"
    fi
}

step() { echo; echo "=== $* ==="; }

# --- 1. Client constants -----------------------------------------------------
step "1/4 Client constants"
if ( cd "$REPO_ROOT/blackout" && "$PYTHON" scripts/export_client_constants.py --check ); then
    echo "up to date"
else
    echo "stale -- regenerating"
    ( cd "$REPO_ROOT/blackout" && run "$PYTHON" scripts/export_client_constants.py )
    echo "regenerated -- review and commit:"
    git -C "$REPO_ROOT" diff --stat -- godot/autoload/blackout_constants.gd
fi

# --- 2. Server: map rebuild or plain reload ----------------------------------
if [ "$DO_MAPS" -eq 1 ]; then
    step "2/4 Map rebuild (stops/reloads Evennia itself)"
    if [ "$DRY_RUN" -eq 1 ]; then
        run bash "$REPO_ROOT/blackout/scripts/clean_and_reload_all_maps.sh" --dry-run
    else
        run bash "$REPO_ROOT/blackout/scripts/clean_and_reload_all_maps.sh"
    fi
else
    step "2/4 Reload game server"
    ACTION="reload"
    if [ "$DO_REBOOT" -eq 1 ]; then
        ACTION="reboot"
    fi
    ( cd "$REPO_ROOT/blackout" && run "$EVENNIA" "$ACTION" )
fi

# --- 3. Godot client: export -> publish -> site deploy -----------------------
if [ "$DO_GODOT" -eq 1 ]; then
    step "3/4 Godot client: export -> publish -> site deploy"

    if [ -z "$SITE_DIR" ]; then
        echo "No playblackout-site checkout beside $REPO_ROOT -- skipping." >&2
    else
        run "$GODOT_BIN" --headless --path "$REPO_ROOT/godot" --export-release "Web" \
            "$REPO_ROOT/deploy/webexport/build/index.html"

        if [ "$DRY_RUN" -eq 1 ]; then
            run bash "$REPO_ROOT/deploy/webexport/publish.sh" --dry-run
        else
            run bash "$REPO_ROOT/deploy/webexport/publish.sh"
        fi

        ( cd "$SITE_DIR" && run npx wrangler deploy )
    fi
else
    step "3/4 Godot client -- skipped (--skip-godot)"
fi

# --- 4. Verify -----------------------------------------------------------------
step "4/4 Verify"
if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] skipped verification requests"
else
    CODE="$( curl -sS -o /dev/null -w '%{http_code}' https://game.playblackout.io/ || true )"
    echo "game.playblackout.io -> $CODE"
    if [ "$CODE" != "200" ]; then
        echo "  not 200 -- see deploy/cloudflared/README.md ('Is it actually up?')" >&2
    fi

    if [ "$DO_GODOT" -eq 1 ] && [ -n "$SITE_DIR" ]; then
        WASM_CODE="$( curl -sS -o /dev/null -w '%{http_code}' https://playblackout.io/client/index.wasm || true )"
        echo "playblackout.io/client/index.wasm -> $WASM_CODE"
    fi
fi

echo
echo "Done."
