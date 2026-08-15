#!/usr/bin/env bash
#
# Full map rebuild, driven entirely by scripts/map_manifest.json:
# stop -> sync grid to manifest -> spawn -> reload.
#
# Pass --dry-run to report what a rebuild would add and remove without
# touching the database or the running server.

set -u

# Resolve the directory of this script, then the game directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
GAME_DIR="$(dirname "$SCRIPT_DIR")"

# Resolve the virtual environment directory (one level up from GAME_DIR)
EVENV_DIR="$(cd "$GAME_DIR/../evenv" && pwd)"

# Detect if we are on Windows (Git Bash) or Linux/macOS to find the correct venv paths
if [ -f "$EVENV_DIR/Scripts/python.exe" ]; then
    PYTHON="$EVENV_DIR/Scripts/python.exe"
    EVENNIA="$EVENV_DIR/Scripts/evennia.exe"
else
    PYTHON="$EVENV_DIR/bin/python"
    EVENNIA="$EVENV_DIR/bin/evennia"
fi

# Change to the game directory
cd "$GAME_DIR" || exit 1

MAP_SYNC="$SCRIPT_DIR/map_sync.py"

DRY_RUN=0
for ARG in "$@"; do
    if [ "$ARG" = "--dry-run" ]; then
        DRY_RUN=1
    fi
done

# A dry run only reads, so it neither stops the server nor spawns afterwards.
if [ "$DRY_RUN" -eq 1 ]; then
    "$PYTHON" "$MAP_SYNC" --dry-run
    exit $?
fi

echo "=== Stopping Evennia ==="
"$EVENNIA" stop

echo "=== Syncing grid to map manifest ==="
if ! "$PYTHON" "$MAP_SYNC"; then
    echo "Error: map sync failed; grid not spawned" >&2
    exit 1
fi

echo "=== Spawning maps ==="
"$EVENNIA" xyzgrid spawn

echo "=== Reloading Evennia ==="
"$EVENNIA" reload

echo "=== Done ==="
